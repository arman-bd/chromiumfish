import { chromium, type Browser, type LaunchOptions } from "playwright-core";
import { binaryPath } from "./fetch.js";

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
  /** Integer seed for a stable, internally-consistent fingerprint persona. */
  personaSeed?: number;
  /** Run headless (SwiftShader). Defaults to true. */
  headless?: boolean;
  /** Window dimensions; defaults to [1920, 1080]. Pass null to omit. */
  windowSize?: [number, number] | null;
  /** Override the browser build version. */
  version?: string;
  /** Auto-download the build if missing. Defaults to true. */
  download?: boolean;
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
 *   const browser = await ChromiumFish({ personaSeed: 27182, headless: true });
 */
export async function ChromiumFish(opts: ChromiumFishOptions = {}): Promise<Browser> {
  const { personaSeed, headless = true, windowSize, version, download = true, args, ...launch } = opts;
  const executablePath = await binaryPath(version, download);
  return chromium.launch({
    executablePath,
    headless,
    args: buildArgs({ personaSeed, windowSize, args }),
    ...launch,
  });
}
