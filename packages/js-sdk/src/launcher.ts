import { chromium, type Browser, type LaunchOptions } from "playwright-core";
import { binaryPath } from "./fetch.js";
import { resolveTimezone } from "./ip2tz.js";

/**
 * Flags that keep the GPU-less / SwiftShader path working and the persona
 * engine happy. Mirrors the production launch_lean.sh defaults (minus anything
 * baked into the build / bundled addon).
 */
export const BASE_ARGS: string[] = [
  "--no-sandbox",
  "--no-zygote",
  "--disable-dev-shm-usage",
  "--use-gl=angle",
  "--use-angle=swiftshader",
  "--enable-unsafe-swiftshader",
];

export interface ChromiumFishOptions extends Omit<LaunchOptions, "executablePath"> {
  /** String id for a stable, internally-consistent fingerprint persona. */
  personaSeed?: string;
  /** Run headless (SwiftShader). Defaults to true. */
  headless?: boolean;
  /** Window dimensions; defaults to [1920, 1080]. Pass null to omit. */
  windowSize?: [number, number] | null;
  /** Override the browser build version. */
  version?: string;
  /** Auto-download the build if missing. Defaults to true. */
  download?: boolean;
  /**
   * Timezone handling. `"auto"` probes the egress IP and resolves it against
   * the downloadable ip2tz DB; an IANA string (e.g. `"Europe/Berlin"`) is used
   * verbatim; omit to leave the timezone untouched.
   */
  timezone?: string;
}

/** Flatten a Playwright proxy option into a probe URL, or undefined. */
function proxyToUrl(proxy: LaunchOptions["proxy"]): string | undefined {
  if (!proxy?.server) return undefined;
  const { server, username, password } = proxy;
  if (username && server.includes("://")) {
    const [scheme, host] = server.split("://", 2);
    return `${scheme}://${username}:${password ?? ""}@${host}`;
  }
  return server;
}

export function buildArgs(opts: ChromiumFishOptions): string[] {
  const args = [...BASE_ARGS];
  if (opts.personaSeed !== undefined) args.push(`--persona-seed=${opts.personaSeed}`);
  const ws = opts.windowSize === undefined ? [1920, 1080] : opts.windowSize;
  if (ws) args.push(`--window-size=${ws[0]},${ws[1]}`);
  if (opts.args) args.push(...opts.args);
  return args;
}

/**
 * Launch ChromiumFish and return a standard Playwright `Browser`.
 *
 *   import { ChromiumFish } from "chromiumfish";
 *   const browser = await ChromiumFish({ personaSeed: "alpha-7", headless: true });
 */
export async function ChromiumFish(opts: ChromiumFishOptions = {}): Promise<Browser> {
  const { personaSeed, headless = true, windowSize, version, download = true, timezone, args, ...launch } = opts;
  const executablePath = await binaryPath(version, download);

  // Resolve the timezone before launch: "auto" -> egress IP via the ip2tz DB,
  // an IANA string -> used as-is. Inject as the TZ env var so Chromium's ICU
  // adopts it at process init (the production timezone source of truth).
  let tz: string | null = null;
  if (timezone) {
    tz = timezone === "auto" ? await resolveTimezone({ proxy: proxyToUrl(launch.proxy), download }) : timezone;
  }
  let env = launch.env;
  if (tz) {
    env = {
      ...(process.env as Record<string, string>),
      ...((launch.env as Record<string, string> | undefined) ?? {}),
      TZ: tz,
    };
  }

  return chromium.launch({
    executablePath,
    headless,
    args: buildArgs({ personaSeed, windowSize, args }),
    ...launch,
    ...(env ? { env } : {}),
  });
}
