/**
 * ChromiumFish MCP server — drive the stealth browser from any MCP client.
 *
 * Exposes ChromiumFish as a Model Context Protocol (https://modelcontextprotocol.io)
 * server so MCP-speaking agents (Claude Code/Desktop, Cursor, Windsurf, …) can
 * perceive and operate the hardened browser directly. Tools are driven over the
 * Chrome DevTools Protocol against a ChromiumFish instance the server launches and
 * holds for its lifetime — the persona/proxy/timezone you start it with stay
 * active, so the agent operates a browser that already looks like a real person.
 *
 *   npx chromiumfish mcp --persona-seed alice
 *
 * The granular tools (navigate/snapshot/get_text/screenshot/click/type_text/eval_js)
 * need no LLM on the server side — the MCP client is the brain. `run_task` delegates
 * a whole plain-language goal to the fork's native in-browser agent, which needs an
 * OpenAI-compatible LLM (OPENAI_API_* / --llm-*). TypeScript port of `chromiumfish.mcp`.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { launchAgent, CDP, type AgentClient, type AgentSession, type TypingSpeed } from "./agent.js";
import { SDK_VERSION } from "./version.js";

export interface McpConfig {
  personaSeed?: string;
  headless?: boolean;
  windowSize?: [number, number];
  proxy?: string;
  port?: number;
  typing?: TypingSpeed;
  apiKey?: string;
  apiBase?: string;
  model?: string;
}

// Builds a readable, selector-addressable list of interactive elements. The raw
// `Page.getAnnotatedPageContent` CDP command returns the index-keyed proto the
// native agent consumes — not usable directly and not selector-addressable — so
// we perceive via the DOM. The selectors it emits are what click/type_text take.
const SNAPSHOT_JS = String.raw`
(function(){
  function sel(el){
    if (el.id) return '#'+CSS.escape(el.id);
    var nm = el.getAttribute('name');
    if (nm) return el.tagName.toLowerCase()+'[name="'+nm+'"]';
    var path=[], e=el;
    while(e && e.nodeType===1 && path.length<4){
      var part=e.tagName.toLowerCase();
      if(e.parentElement){
        var sib=Array.prototype.filter.call(e.parentElement.children,function(c){return c.tagName===e.tagName;});
        if(sib.length>1) part+=':nth-of-type('+(sib.indexOf(e)+1)+')';
      }
      path.unshift(part); e=e.parentElement;
    }
    return path.join(' > ');
  }
  function label(el){
    return (el.getAttribute('aria-label')||el.value||el.placeholder||el.innerText||el.getAttribute('title')||'')
      .trim().replace(/\s+/g,' ').slice(0,80);
  }
  var els=document.querySelectorAll('a,button,input,textarea,select,[role=button],[role=link],[onclick],[contenteditable=true]');
  var out=[], n=0;
  for(var i=0;i<els.length && n<200;i++){
    var el=els[i];
    if(!el.getClientRects().length) continue;
    var role=el.tagName.toLowerCase()+(el.type?'['+el.type+']':'');
    var line='['+n+'] '+role+' "'+label(el)+'"  '+sel(el);
    if(el.href) line+=' -> '+el.href;
    out.push(line); n++;
  }
  return out.length ? out.join('\n') : '(no visible interactive elements)';
})()
`;

let _config: McpConfig = {};
let _session: AgentSession | null = null;

async function client(): Promise<AgentClient> {
  if (!_session) {
    const extra: string[] = [];
    if (_config.personaSeed) extra.push(`--persona-seed=${_config.personaSeed}`);
    if (_config.headless ?? true) extra.push("--headless=new");
    const [w, h] = _config.windowSize ?? [1920, 1080];
    extra.push(`--window-size=${w},${h}`);
    if (_config.proxy) extra.push(`--proxy-server=${_config.proxy}`);
    _session = await launchAgent({
      port: _config.port ?? 9222,
      apiKey: _config.apiKey ?? "",
      apiBase: _config.apiBase ?? "",
      model: _config.model ?? "",
      typing: _config.typing ?? "human",
      extraArgs: extra,
    });
  }
  return _session.agent;
}

async function shutdown(): Promise<void> {
  if (_session) {
    try {
      await _session.close();
    } catch {
      /* ignore */
    }
    _session = null;
  }
}

/** Run `fn` against a short-lived CDP connection to the active page target. */
async function withPage<T>(fn: (cdp: CDP, targetId: string) => Promise<T>): Promise<T> {
  const agent = await client();
  const { targetId, wsUrl } = await agent.pickPage();
  const cdp = await CDP.connect(wsUrl);
  try {
    return await fn(cdp, targetId);
  } finally {
    cdp.close();
  }
}

async function evalJs(cdp: CDP, expression: string): Promise<unknown> {
  const res = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (res.exceptionDetails) {
    throw new Error(res.exceptionDetails.exception?.description || res.exceptionDetails.text || "eval error");
  }
  return res.result?.value;
}

const textResult = (text: string) => ({ content: [{ type: "text" as const, text }] });

export function buildServer(): McpServer {
  const mcp = new McpServer({ name: "chromiumfish", version: SDK_VERSION });

  mcp.registerTool(
    "navigate",
    {
      description:
        "Open a URL in the ChromiumFish browser and wait for it to load. Returns the resolved URL and title; call `snapshot` next to see what's on the page.",
      inputSchema: { url: z.string().describe("The URL to open") },
    },
    async ({ url }) =>
      textResult(
        await withPage(async (cdp) => {
          await cdp.send("Page.enable");
          await cdp.send("Page.navigate", { url });
          await cdp.waitEvent("Page.loadEventFired", 30_000).catch(() => {});
          const title = await evalJs(cdp, "document.title");
          const href = await evalJs(cdp, "document.location.href");
          return `Loaded ${href}\nTitle: ${title}`;
        }),
      ),
  );

  mcp.registerTool(
    "snapshot",
    {
      description:
        'List the page\'s visible interactive elements, one per line, as `[i] <role> "label"  <css-selector>` (links also show `-> url`). Use the CSS selector with click/type_text. For prose use get_text; for anything else, eval_js.',
      inputSchema: {},
    },
    async () => textResult((await withPage((cdp) => evalJs(cdp, SNAPSHOT_JS) as Promise<string>)) || "(no visible interactive elements)"),
  );

  mcp.registerTool(
    "get_text",
    {
      description: "Return the visible text of the current page (`document.body.innerText`). Best for reading articles/long content.",
      inputSchema: {},
    },
    async () => textResult(((await withPage((cdp) => evalJs(cdp, "document.body && document.body.innerText || ''"))) as string) || "(empty)"),
  );

  mcp.registerTool(
    "screenshot",
    { description: "Capture a PNG screenshot of the current viewport.", inputSchema: {} },
    async () => {
      const data = (await withPage(async (cdp) => (await cdp.send("Page.captureScreenshot", { format: "png" })).data)) as string;
      return { content: [{ type: "image" as const, data, mimeType: "image/png" }] };
    },
  );

  mcp.registerTool(
    "click",
    {
      description:
        "Humanized, trusted click on the first element matching a CSS selector (cursor moves along a bezier path; `navigator.webdriver` stays false). Fails if nothing matches.",
      inputSchema: { selector: z.string().describe("CSS selector of the element to click") },
    },
    async ({ selector }) =>
      textResult(
        await withPage(async (cdp, targetId) => {
          const r = (await cdp.send("Browser.humanizedClickSelector", { targetId, selector })) ?? {};
          return `Clicked ${JSON.stringify(selector)} at (${r.x}, ${r.y})`;
        }),
      ),
  );

  mcp.registerTool(
    "type_text",
    {
      description: "Click the element matching `selector` to focus it, type `text`, and optionally press Enter (`submit=true`) to submit a search/form.",
      inputSchema: {
        selector: z.string().describe("CSS selector of the field"),
        text: z.string().describe("Text to type"),
        submit: z.boolean().optional().describe("Press Enter after typing"),
      },
    },
    async ({ selector, text, submit }) =>
      textResult(
        await withPage(async (cdp, targetId) => {
          await cdp.send("Browser.humanizedClickSelector", { targetId, selector });
          await cdp.send("Input.insertText", { text });
          if (submit) {
            for (const type of ["keyDown", "keyUp"]) {
              await cdp.send("Input.dispatchKeyEvent", { type, key: "Enter", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
            }
          }
          return `Typed into ${JSON.stringify(selector)}${submit ? " and pressed Enter" : ""}`;
        }),
      ),
  );

  mcp.registerTool(
    "eval_js",
    {
      description:
        "Evaluate a JavaScript expression in the page and return its (JSON) result. Powerful escape hatch — read anything or act on the page.",
      inputSchema: { expression: z.string().describe("JavaScript expression to evaluate") },
    },
    async ({ expression }) => {
      const value = await withPage((cdp) => evalJs(cdp, expression));
      let text: string;
      try {
        text = JSON.stringify(value);
      } catch {
        text = String(value);
      }
      return textResult(text ?? "undefined");
    },
  );

  mcp.registerTool(
    "run_task",
    {
      description:
        "Delegate a whole plain-language goal to ChromiumFish's native in-browser agent (perceive → think → act loop, humanized input). Best for multi-step flows. Requires an OpenAI-compatible LLM on the server (OPENAI_API_* / --llm-*); otherwise use the granular tools.",
      inputSchema: { task: z.string().describe("Plain-language goal"), url: z.string().optional().describe("Page to start on") },
    },
    async ({ task, url }) => {
      const agent = await client();
      const r = await agent.runTask(task, { url: url || undefined });
      const text = r.finalText || (r.success ? "(done)" : "Task did not complete. (If this needs the native agent, ensure an LLM is configured on the MCP server.)");
      return textResult(text);
    },
  );

  return mcp;
}

/** Configure and run the MCP server over stdio (blocks until the client disconnects). */
export async function runServer(config: McpConfig = {}): Promise<void> {
  _config = config;
  const server = buildServer();
  const transport = new StdioServerTransport();
  const stop = () => {
    shutdown().finally(() => process.exit(0));
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  try {
    await server.connect(transport);
    await new Promise<void>((resolve) => {
      transport.onclose = () => resolve();
    });
  } finally {
    await shutdown();
  }
}
