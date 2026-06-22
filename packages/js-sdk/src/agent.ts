/**
 * Native in-browser AI agent client (TypeScript port of the Python SDK's
 * ``chromiumfish.agent``).
 *
 * Drives the fork's native ``Browser.agentRunTask`` CDP command on a running
 * ChromiumFish (launched with ``--remote-debugging-port`` and the ``--agent-*``
 * switches). Talks raw CDP over a WebSocket — the same path the Python client
 * uses — which avoids Playwright's ``connectOverCDP`` context setup that this
 * fork's CDP surface doesn't fully support.
 *
 *   import { launchAgent } from "chromiumfish";
 *
 *   const { agent, close } = await launchAgent({ typing: "fast" });
 *   try {
 *     const r = await agent.runTask("search for 'automation' and open the first result",
 *                                   { url: "http://127.0.0.1:8000/search" });
 *     console.log(r.success, r.finalText);
 *   } finally {
 *     await close();
 *   }
 *
 * Needs a WebSocket implementation: the Node 22+ global ``WebSocket`` is used if
 * present, otherwise the optional ``ws`` package (``npm install ws``) on Node <22.
 */
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { binaryPath } from "./fetch.js";

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// The agent's master/system prompt, sent per task as Browser.agentRunTask's
// `systemPrompt` param. NOTE: current shipped builds use the prompt baked into
// the binary (C++ `kSystemPrompt`) and ignore this param — so it is effectively
// a no-op against them; kept for parity with the Python SDK and to declare the
// intended contract (the final `done` answer is ONLY the value the task asked
// for — no prose, no labels — so callers get a clean result).
export const AGENT_SYSTEM_PROMPT =
  "You are an autonomous web-browsing agent operating directly inside the " +
  "browser. Each turn you receive the interactive elements currently visible " +
  "on the page, one per line:\n" +
  "  [<index>]<role>label\n" +
  "Roles: a (link), button, input, textarea, select, checkbox. Each input " +
  'shows its STATE in brackets: [EMPTY; placeholder hint "..."] = empty, the ' +
  'hint is NOT a value, type into it; [value: "..."] = already contains that ' +
  "text; [filled]/[empty] = a password field; [checked]/[unchecked] = a " +
  'checkbox; [selected: "..."]/[no selection] = a select (its choices follow ' +
  "as opts:[value=text, ...] — use one exact value). Disabled controls are " +
  "marked (disabled). You also get a one-line note saying whether the page " +
  "changed since your last action.\n\n" +
  "Respond with ONLY a JSON object (no prose, no markdown):\n" +
  "{\n" +
  '  "thought": "brief reasoning",\n' +
  '  "actions": [ <one or more action steps, run in order, in one shot> ]\n' +
  "}\n" +
  'Each step is an object: {"action": ' +
  '"click|type|scroll|navigate|select|read|wait|done", "index": <element ' +
  'index>, "text": "to type", "enter": true (type: press Enter), ' +
  '"url": "https://..." (navigate), "value": "exact option value" ' +
  '(select), "direction": "down|up|left|right" (scroll), "seconds": 1 ' +
  '(wait), "success": true and "final": "<answer>" (done)}.\n' +
  "Put MULTIPLE steps in the array to do them in ONE shot (strongly preferred " +
  "for speed): whenever you know the values, fill ALL fields AND click submit " +
  "in a single response. Use a single step only when the next step truly " +
  "depends on this one's result.\n\n" +
  "Rules:\n" +
  "- If a cookie/consent dialog or modal is open — its elements are marked " +
  '(modal), or you see text like "Accept all" / "Reject all" / ' +
  '"consent" / "Before you continue" — DISMISS it FIRST by clicking its ' +
  "accept/agree/continue button, before attempting anything else. Elements " +
  "behind a modal are still listed but are visually covered and cannot be " +
  "used until it is gone.\n" +
  "- Use only indices in the CURRENT list; they are renumbered every step.\n" +
  '- Link items (role a) show their destination URL after " -> ". To report ' +
  "or use a link's URL, READ it from the list — do not click/navigate to the " +
  "link just to find its address.\n" +
  "- The element list shows only INTERACTIVE controls, NOT the article/body " +
  "text. To read or summarize page CONTENT (article, blog post, paragraphs), " +
  'issue {"action":"read"} by itself; the page\'s text appears in your NEXT ' +
  "observation as PAGE TEXT — then answer from it.\n" +
  "- To submit a search or form, set \"enter\": true when typing, or click the " +
  "submit/Continue button. Typing alone does not submit.\n" +
  "- For a select, use action \"select\" with an exact value from its opts.\n" +
  "- AVOID LOOPS: do each step ONCE. Never re-issue the same action (or the " +
  "same type+type+click batch) just because the page still looks unfinished. " +
  "A submit/save that clears or reloads the form almost always SUCCEEDED — " +
  "treat the reset/empty form as success, NOT a reason to submit again. " +
  "Created items and counts are non-interactive and invisible here; confirm " +
  'with {"action":"read"} then finish. Repeat an action only if the task TEXT ' +
  "explicitly asks for it.\n" +
  "- RETURN ONLY WHAT WAS ASKED. When you are done, the \"final\" field must " +
  "contain EXACTLY the value the task requested and NOTHING else — no " +
  "sentences, no labels, no explanation, no quotes, no markdown. Only when the " +
  "task asks for a description/summary should \"final\" be a sentence.\n" +
  "- Finish with a {\"action\":\"done\",\"success\":true,\"final\":\"...\"} " +
  "step by itself; use success false only if the goal is genuinely impossible.";

// Per-keystroke typing cadence for the agent's incremental typing, as
// [key-down, key-up, long-text-multiplier]. The Actor framework default is
// ~25ms/25ms/0.2 (~240 WPM — superhuman); "human" slows it to ~75 WPM so the
// typing looks natural. "fast"/"instant" trade realism for speed.
export const TYPING_PROFILES: Record<string, [string, string, string]> = {
  human: ["45ms", "110ms", "0.7"], // ~75 WPM — natural, the default
  fast: ["10ms", "18ms", "0.3"], // brisk, still per-keystroke
  instant: ["0ms", "0ms", "0"], // no inter-key delay (fastest)
};

type Cadence = [string | number, string | number, string | number];
export type TypingSpeed = keyof typeof TYPING_PROFILES | (string & {}) | Cadence;

/** Build the GlicActorIncrementalTyping switch for a typing-speed setting. */
export function typingFlag(typing: TypingSpeed = "human"): string {
  let kd: string | number, ku: string | number, mult: string | number;
  if (typeof typing === "string") {
    const prof = TYPING_PROFILES[typing];
    if (!prof) {
      throw new Error(
        `unknown typing speed '${typing}'; use one of ` +
          `${Object.keys(TYPING_PROFILES).join(", ")} or a [keyDown, keyUp, multiplier] triple`,
      );
    }
    [kd, ku, mult] = prof;
  } else {
    [kd, ku, mult] = typing;
  }
  const ms = (v: string | number) => (typeof v === "string" ? v : `${v}ms`);
  return (
    "--enable-features=GlicActorIncrementalTyping:" +
    `glic-actor-incremental-typing-key-down-duration/${ms(kd)}/` +
    `glic-actor-incremental-typing-key-up-duration/${ms(ku)}/` +
    `glic-actor-incremental-typing-long-multiplier/${mult}`
  );
}

export interface AgentStep {
  action?: string;
  status?: string;
  [k: string]: unknown;
}

/** Outcome of one agent task plus the resolved step plan. */
export class AgentResult {
  constructor(
    public success: boolean,
    public finalText: string,
    public steps: AgentStep[],
    public replayed = false,
  ) {}
  /** Number of steps replayed deterministically (no LLM call). */
  get fromCache(): number {
    return this.steps.filter((s) => s.status === "replayed").length;
  }
  /** Number of steps the page had drifted on, re-resolved via the LLM. */
  get healed(): number {
    return this.steps.filter((s) => s.status === "healed").length;
  }
  /** Number of steps resolved by the LLM on a fresh run. */
  get recorded(): number {
    return this.steps.filter((s) => s.status === "recorded").length;
  }
  summary(): string {
    return (
      `${this.success ? "ok" : "fail"} | ${this.steps.length} steps ` +
      `(${this.fromCache} replayed, ${this.healed} healed, ${this.recorded} recorded)`
    );
  }
}

async function getWebSocketCtor(): Promise<any> {
  const g = (globalThis as any).WebSocket;
  if (g) return g;
  try {
    const spec = "ws"; // variable specifier: keeps tsc from requiring `ws` at build
    const mod: any = await import(spec);
    return mod.default ?? mod.WebSocket ?? mod;
  } catch {
    throw new Error(
      "the AI agent client needs a WebSocket implementation; on Node <22 install " +
        "it with `npm install ws`",
    );
  }
}

/** Minimal CDP-over-WebSocket client. */
export class CDP {
  private id = 0;
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: any) => void }>();
  private waiters: Array<{ method: string; resolve: () => void; timer: ReturnType<typeof setTimeout> }> = [];

  private constructor(private ws: any) {
    ws.addEventListener("message", (ev: any) => {
      const text = typeof ev.data === "string" ? ev.data : ev.data?.toString?.() ?? "";
      let msg: any;
      try {
        msg = JSON.parse(text);
      } catch {
        return;
      }
      if (msg.id != null && this.pending.has(msg.id)) {
        const p = this.pending.get(msg.id)!;
        this.pending.delete(msg.id);
        if (msg.error) p.reject(new Error(msg.error.message ?? JSON.stringify(msg.error)));
        else p.resolve(msg.result ?? {});
      } else if (msg.method) {
        for (let i = this.waiters.length - 1; i >= 0; i--) {
          if (this.waiters[i].method === msg.method) {
            const w = this.waiters.splice(i, 1)[0];
            clearTimeout(w.timer);
            w.resolve();
          }
        }
      }
    });
  }

  static async connect(url: string): Promise<CDP> {
    const WS = await getWebSocketCtor();
    const ws = new WS(url);
    await new Promise<void>((resolve, reject) => {
      ws.addEventListener("open", () => resolve(), { once: true });
      ws.addEventListener("error", () => reject(new Error("CDP WebSocket error")), { once: true });
    });
    return new CDP(ws);
  }

  send(method: string, params: Record<string, unknown> = {}, timeoutMs?: number): Promise<any> {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      if (timeoutMs) {
        timer = setTimeout(() => {
          this.pending.delete(id);
          reject(new Error(`${method}: timed out after ${timeoutMs}ms`));
        }, timeoutMs);
      }
      this.pending.set(id, {
        resolve: (v) => {
          if (timer) clearTimeout(timer);
          resolve(v);
        },
        reject,
      });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  waitEvent(method: string, timeoutMs: number): Promise<void> {
    return new Promise<void>((resolve) => {
      const timer = setTimeout(() => {
        const i = this.waiters.findIndex((w) => w.timer === timer);
        if (i >= 0) this.waiters.splice(i, 1);
        resolve();
      }, timeoutMs);
      this.waiters.push({ method, resolve, timer });
    });
  }

  close(): void {
    try {
      this.ws.close();
    } catch {
      /* ignore */
    }
  }
}

export interface RunTaskOptions {
  /** Navigate here before the agent loop (the agent can also navigate itself). */
  url?: string;
  /** Max perceive→act iterations. Defaults to 25. */
  maxSteps?: number;
  /** Per-task model override. */
  model?: string;
  /** A resolved plan to REPLAY (descriptor match per step, LLM only to heal). */
  plan?: AgentStep[];
  /** System prompt override (honored by builds whose agent layer reads it). */
  systemPrompt?: string | null;
}

/** Connects to a running ChromiumFish CDP endpoint and runs agent tasks. */
export class AgentClient {
  constructor(
    public port = 9222,
    private host = "localhost",
    private timeoutMs = 420_000,
  ) {}

  private async httpGet(p: string): Promise<any> {
    const res = await fetch(`http://${this.host}:${this.port}${p}`);
    if (!res.ok) throw new Error(`GET ${p} -> ${res.status}`);
    return res.json();
  }

  /** Return {targetId, wsUrl}, reusing a real page or opening one. */
  async pickPage(): Promise<{ targetId: string; wsUrl: string }> {
    const targets: any[] = await this.httpGet("/json");
    const pages = targets.filter(
      (t) => t.type === "page" && !String(t.url ?? "").startsWith("chrome://") && t.webSocketDebuggerUrl,
    );
    if (pages.length) return { targetId: pages[0].id, wsUrl: pages[0].webSocketDebuggerUrl };
    // No usable page: create one via the browser endpoint. (GET /json/new 405s on
    // recent builds, so go through Target.createTarget instead.)
    const ver = await this.httpGet("/json/version");
    const browser = await CDP.connect(ver.webSocketDebuggerUrl);
    try {
      const { targetId } = await browser.send("Target.createTarget", { url: "about:blank" });
      const again: any[] = await this.httpGet("/json");
      const pg = again.find((t) => t.id === targetId);
      if (!pg?.webSocketDebuggerUrl) throw new Error("could not open a page target");
      return { targetId, wsUrl: pg.webSocketDebuggerUrl };
    } finally {
      browser.close();
    }
  }

  async runTask(goal: string, opts: RunTaskOptions = {}): Promise<AgentResult> {
    const { url, maxSteps = 25, model = "", plan, systemPrompt = AGENT_SYSTEM_PROMPT } = opts;
    const { targetId, wsUrl } = await this.pickPage();
    const cdp = await CDP.connect(wsUrl);
    try {
      await cdp.send("Page.enable");
      if (url && url !== "about:blank") {
        await cdp.send("Page.navigate", { url });
        await cdp.waitEvent("Page.loadEventFired", 20_000);
        await sleep(500);
      }
      const params: Record<string, unknown> = { targetId, goal, maxSteps };
      if (model) params.model = model;
      if (plan) params.planJson = JSON.stringify(plan);
      if (systemPrompt) params.systemPrompt = systemPrompt;
      const res = (await cdp.send("Browser.agentRunTask", params, this.timeoutMs)) ?? {};
      let steps: AgentStep[] = [];
      try {
        const parsed = JSON.parse((res.stepsJson as string) ?? "[]");
        if (Array.isArray(parsed)) steps = parsed;
      } catch {
        /* leave steps empty */
      }
      return new AgentResult(Boolean(res.success), (res.finalText as string) ?? "", steps, Boolean(plan));
    } finally {
      cdp.close();
    }
  }
}

/** Load KEY=VALUE lines from the nearest .env (cwd or a parent) without override. */
function loadDotenv(): void {
  let dir = process.cwd();
  for (;;) {
    const envFile = path.join(dir, ".env");
    if (existsSync(envFile)) {
      for (const raw of readFileSync(envFile, "utf8").split(/\r?\n/)) {
        const line = raw.trim();
        if (!line || line.startsWith("#") || !line.includes("=")) continue;
        const idx = line.indexOf("=");
        const key = line.slice(0, idx).trim();
        const val = line.slice(idx + 1).trim();
        if (!(key in process.env)) process.env[key] = val;
      }
      return;
    }
    const parent = path.dirname(dir);
    if (parent === dir) return;
    dir = parent;
  }
}

export interface LaunchAgentOptions {
  /** DevTools remote-debugging port. Defaults to 9222. */
  port?: number;
  /** Path to the ChromiumFish binary; defaults to CHROME_BIN env or the cached build. */
  chrome?: string;
  /** LLM API key (overrides OPENAI_API_KEY). */
  apiKey?: string;
  /** LLM base URL (overrides OPENAI_API_BASE). */
  apiBase?: string;
  /** Model for this session (overrides OPENAI_API_MODEL). */
  model?: string;
  /** Typing cadence: "human" (default), "fast", "instant", or a [keyDown, keyUp, multiplier] triple. */
  typing?: TypingSpeed;
  /** Load a nearby .env for OPENAI_* config. Defaults to true. */
  loadDotenv?: boolean;
  /** Extra Chromium flags. */
  extraArgs?: string[];
  /** How long to wait for the CDP endpoint to come up (ms). Defaults to 30000. */
  timeoutMs?: number;
}

/** A launched agent session: the connected client plus a cleanup function. */
export interface AgentSession {
  agent: AgentClient;
  /** Shut the browser down and remove its temp profile. */
  close: () => Promise<void>;
}

/**
 * Launch a local ChromiumFish with the AI agent layer and connect to it.
 *
 * LLM config can be passed in-script (`apiKey` / `apiBase` / `model`) or left to
 * OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_API_MODEL (a nearby .env is loaded
 * automatically); an explicit option wins over the env var. Prefer {@link withAgent}
 * for automatic cleanup, or remember to call the returned `close()`.
 */
export async function launchAgent(opts: LaunchAgentOptions = {}): Promise<AgentSession> {
  const { port = 9222, apiKey = "", apiBase = "", model = "", typing = "human", loadDotenv: doDotenv = true, extraArgs = [], timeoutMs = 30_000 } = opts;
  if (doDotenv) loadDotenv();
  let chrome = opts.chrome ?? process.env.CHROME_BIN;
  if (!chrome) chrome = await binaryPath();

  const profile = mkdtempSync(path.join(tmpdir(), "cf-agent-"));
  const args = [
    `--remote-debugging-port=${port}`,
    "--remote-allow-origins=*",
    `--user-data-dir=${profile}`,
    "--disable-actor-safety-checks", // let the agent act unattended
    // Typing cadence (see TYPING_PROFILES). Default "human" ~75 WPM so the
    // agent's keystrokes look natural; "fast"/"instant" go quicker.
    typingFlag(typing),
    "--no-first-run",
    "--no-default-browser-check",
    `--agent-llm-url=${apiBase || (process.env.OPENAI_API_BASE ?? "")}`,
    `--agent-llm-key=${apiKey || (process.env.OPENAI_API_KEY ?? "")}`,
    `--agent-model=${model || (process.env.OPENAI_API_MODEL ?? "")}`,
    ...extraArgs,
  ];
  const proc: ChildProcess = spawn(chrome, args, { stdio: "ignore" });

  const cleanup = () => rmSync(profile, { recursive: true, force: true });
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    try {
      const r = await fetch(`http://localhost:${port}/json/version`);
      if (r.ok) break;
    } catch {
      /* not up yet */
    }
    if (Date.now() > deadline) {
      try {
        proc.kill("SIGKILL");
      } catch {
        /* ignore */
      }
      cleanup();
      throw new Error("ChromiumFish did not expose its CDP endpoint in time");
    }
    await sleep(500);
  }

  // Open an initial page target so runTask can find one immediately.
  try {
    const ver = await (await fetch(`http://localhost:${port}/json/version`)).json();
    const browser = await CDP.connect(ver.webSocketDebuggerUrl);
    try {
      await browser.send("Target.createTarget", { url: "about:blank" });
    } finally {
      browser.close();
    }
  } catch {
    /* runTask.pickPage will retry if needed */
  }

  const close = async () => {
    try {
      proc.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    await sleep(300);
    try {
      proc.kill("SIGKILL");
    } catch {
      /* ignore */
    }
    cleanup();
  };

  return { agent: new AgentClient(port), close };
}

/**
 * Run `fn` against a freshly launched agent, shutting the browser down and
 * cleaning up afterwards — the ergonomic equivalent of Python's
 * `with launch_agent() as agent:`.
 *
 *   const url = await withAgent({ typing: "fast" }, (agent) =>
 *     agent.runTask("...").then((r) => r.finalText));
 */
export async function withAgent<T>(opts: LaunchAgentOptions, fn: (agent: AgentClient) => Promise<T>): Promise<T> {
  const { agent, close } = await launchAgent(opts);
  try {
    return await fn(agent);
  } finally {
    await close();
  }
}
