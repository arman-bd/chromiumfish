#!/usr/bin/env node
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { binaryPath, cacheRoot, fetchBrowser } from "./fetch.js";
import { buildArgs } from "./launcher.js";
import { resolveTimezone } from "./ip2tz.js";
import { SDK_VERSION, browserVersion } from "./version.js";

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Read `--flag value` from argv, or undefined. */
function flag(argv: string[], name: string): string | undefined {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : undefined;
}

/**
 * Launch ChromiumFish as a bare CDP endpoint for external agent frameworks
 * (Hermes, OpenClaw, browser-use, ...) to attach to. Unlike `launchAgent`, this
 * adds NO `--agent-*` switches — it just exposes Chrome DevTools Protocol with
 * the persona/proxy/timezone you pick, then blocks until interrupted.
 */
async function serve(argv: string[]): Promise<number> {
  const port = Number(flag(argv, "--port") ?? 9222);
  const personaSeed = flag(argv, "--persona-seed");
  const proxy = flag(argv, "--proxy");
  const windowSize = flag(argv, "--window-size") ?? "1920x1080";
  const timezone = flag(argv, "--timezone");
  const headless = argv.includes("--headless");
  const version = flag(argv, "--browser-version");
  const extraArgsRaw = flag(argv, "--extra-args");
  const timeoutSecs = Number(flag(argv, "--timeout") ?? 30);

  // Validate up front — Python's argparse does this for us; here it's manual.
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error(`invalid --port ${flag(argv, "--port")}; expected an integer 1-65535`);
    return 1;
  }
  if (!Number.isFinite(timeoutSecs) || timeoutSecs <= 0) {
    console.error(`invalid --timeout ${flag(argv, "--timeout")}; expected a positive number of seconds`);
    return 1;
  }
  const [w, h] = windowSize.toLowerCase().split("x").map(Number);
  if (!w || !h) {
    console.error(`invalid --window-size ${windowSize}; expected WIDTHxHEIGHT, e.g. 1920x1080`);
    return 1;
  }

  const chrome = await binaryPath(version); // fetches if not cached
  const profile = mkdtempSync(path.join(tmpdir(), "cf-serve-"));
  const cleanup = () => rmSync(profile, { recursive: true, force: true });
  let proc: ReturnType<typeof spawn> | undefined;
  const killTree = (sig: NodeJS.Signals) => {
    if (!proc?.pid) return;
    try {
      process.kill(-proc.pid, sig); // negative pid = the whole process group
    } catch {
      try {
        proc.kill(sig);
      } catch {
        /* already gone */
      }
    }
  };

  // try/finally guarantees the browser tree + temp profile are torn down even
  // if resolveTimezone/spawn throws or an early return fires — matches the
  // Python handler's finally -> _teardown().
  try {
    const extra: string[] = [];
    if (headless) extra.push("--headless=new");
    if (proxy) extra.push(`--proxy-server=${proxy}`);
    if (extraArgsRaw) extra.push(...extraArgsRaw.split(",").filter(Boolean));

    const args = [
      `--remote-debugging-port=${port}`,
      // External clients send an Origin header DevTools rejects unless allowed.
      "--remote-allow-origins=*",
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      ...buildArgs({ personaSeed, windowSize: [w, h], args: extra }),
    ];

    const env = { ...process.env } as Record<string, string>;
    if (timezone) {
      const tz = timezone === "auto" ? await resolveTimezone({ proxy }) : timezone;
      if (tz) env.TZ = tz;
    }

    const base = `http://127.0.0.1:${port}`;
    // detached: own process group, so we can signal the WHOLE tree (browser +
    // GPU/renderer/network helpers) on exit instead of leaking the helpers.
    proc = spawn(chrome, args, { stdio: "ignore", env, detached: true });

    const deadline = Date.now() + timeoutSecs * 1000;
    let ver: { Browser?: string; webSocketDebuggerUrl?: string } | null = null;
    for (;;) {
      try {
        const r = await fetch(`${base}/json/version`);
        if (r.ok) {
          ver = (await r.json()) as { Browser?: string; webSocketDebuggerUrl?: string };
          break;
        }
      } catch {
        /* not up yet */
      }
      if (proc.exitCode !== null) {
        console.error("ChromiumFish exited before the CDP endpoint came up");
        return 1;
      }
      if (Date.now() > deadline) {
        console.error("ChromiumFish did not expose its CDP endpoint in time");
        return 1;
      }
      await sleep(400);
    }

    console.log(`ChromiumFish ${ver?.Browser ?? ""} ready — CDP endpoint for external agents`);
    console.log(`  HTTP : ${base}   (discovery: ${base}/json/version)`);
    if (ver?.webSocketDebuggerUrl) console.log(`  WS   : ${ver.webSocketDebuggerUrl}`);
    console.log("");
    console.log("Attach an agent, e.g.:");
    console.log(`  Hermes       ~/.hermes/config.yaml  ->  browser: { cdp_url: "${base}" }`);
    console.log(`  browser-use  BrowserSession(cdp_url="${base}")`);
    console.log(`  OpenClaw     profile  cdpUrl: "${base}"`);
    console.log("Ctrl-C to stop.");

    await new Promise<void>((resolve) => {
      const stop = () => {
        console.log("\nstopping…");
        killTree("SIGTERM");
        resolve();
      };
      process.on("SIGINT", stop);
      process.on("SIGTERM", stop);
      proc!.on("exit", () => resolve());
    });
    return 0;
  } finally {
    await sleep(300);
    killTree("SIGKILL");
    cleanup();
  }
}

async function main(argv: string[]): Promise<number> {
  const cmd = argv[2];
  switch (cmd) {
    case "fetch": {
      const force = argv.includes("--force");
      const vIdx = argv.indexOf("--browser-version");
      const version = vIdx >= 0 ? argv[vIdx + 1] : undefined;
      console.log(await fetchBrowser(version, force));
      return 0;
    }
    case "path":
      console.log(await binaryPath());
      return 0;
    case "clear": {
      const root = cacheRoot();
      if (fs.existsSync(root)) {
        fs.rmSync(root, { recursive: true, force: true });
        console.log(`removed ${root}`);
      } else {
        console.log("nothing to remove");
      }
      return 0;
    }
    case "serve":
      return await serve(argv);
    case "--version":
    case "-V":
      console.log(`chromiumfish ${SDK_VERSION} (browser ${browserVersion()})`);
      return 0;
    default:
      console.log(
        [
          "chromiumfish — fetch and manage the ChromiumFish browser build",
          "",
          "Usage:",
          "  chromiumfish fetch [--browser-version X] [--force]   download + cache",
          "  chromiumfish path                                    print binary path",
          "  chromiumfish serve [--port 9222] [--persona-seed S]  CDP endpoint for agents",
          "       [--proxy URL] [--window-size WxH] [--timezone Z] [--headless]",
          "       [--browser-version X] [--extra-args ARGS] [--timeout S]",
          "  chromiumfish clear                                   wipe the cache",
          "  chromiumfish --version",
        ].join("\n"),
      );
      return cmd ? 0 : 1;
  }
}

main(process.argv)
  .then((code) => process.exit(code))
  .catch((err) => {
    console.error(err?.message || err);
    process.exit(1);
  });
