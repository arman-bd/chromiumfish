/**
 * Download, verify, and cache the ChromiumFish browser build.
 *
 * Resolves `version × platform` to a GitHub Release asset, verifies its
 * SHA-256, extracts it to a per-version cache dir, and returns the path to the
 * launchable binary.
 */
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as https from "node:https";
import * as os from "node:os";
import * as path from "node:path";
import { assertSafeVersion, browserVersion, releaseBaseUrl } from "./version.js";

export function cacheRoot(): string {
  const env = process.env.CHROMIUMFISH_CACHE_DIR;
  if (env) return env;
  if (process.platform === "darwin")
    return path.join(os.homedir(), "Library", "Caches", "chromiumfish");
  if (process.platform === "win32")
    return path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "chromiumfish");
  return path.join(process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache"), "chromiumfish");
}

export function platformSlug(): string {
  const arch = ({ x64: "x64", arm64: "arm64" } as Record<string, string>)[process.arch];
  if (!arch) throw new Error(`unsupported architecture: ${process.arch}`);
  if (process.platform === "linux") return `linux-${arch}`;
  if (process.platform === "darwin") return `mac-${arch}`;
  if (process.platform === "win32") return `win-${arch}`;
  throw new Error(`unsupported platform: ${process.platform}`);
}

function assetName(version: string): string {
  assertSafeVersion(version);
  const slug = platformSlug();
  const ext = slug.startsWith("win") ? "zip" : "tar.gz";
  return `chromiumfish-${version}-${slug}.${ext}`;
}

export function installDir(version = browserVersion()): string {
  return path.join(cacheRoot(), assertSafeVersion(version), platformSlug());
}

const BINARY_NAMES = ["chromiumfish", "chrome", "chromiumfish.exe", "chrome.exe", "ChromiumFish"];

export function findBinary(root: string): string | null {
  if (!fs.existsSync(root)) return null;
  for (const name of BINARY_NAMES) {
    const direct = path.join(root, name);
    // statSync can throw if the file is removed between existsSync and stat
    // (TOCTOU); treat any stat failure as "not a usable binary here".
    try {
      if (fs.statSync(direct).isFile()) return direct;
    } catch {
      /* keep looking */
    }
  }
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop()!;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else if (BINARY_NAMES.includes(entry.name)) return full;
    }
  }
  return null;
}

// Idle-timeout (ms) applied to every download/fetch socket. A stalled server
// (no bytes for this long) aborts instead of hanging the launch forever.
const DOWNLOAD_IDLE_TIMEOUT_MS = 60_000;
const FETCH_IDLE_TIMEOUT_MS = 30_000;

function download(url: string, dest: string): Promise<void> {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  return new Promise((resolve, reject) => {
    const get = (u: string) => {
      const req = https.get(u, (res) => {
        if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          res.resume();
          return get(res.headers.location);
        }
        if (res.statusCode !== 200) {
          res.resume();
          return reject(new Error(`download failed (${res.statusCode}) for ${u}`));
        }
        const total = Number(res.headers["content-length"] || 0);
        let read = 0;
        const out = fs.createWriteStream(dest);
        // On any failure: tear down both streams and remove the partial file
        // so a later run doesn't trip over a truncated/corrupt download.
        const fail = (err: Error) => {
          res.destroy();
          out.destroy();
          try { fs.rmSync(dest, { force: true }); } catch { /* best effort */ }
          reject(err);
        };
        res.on("data", (c) => {
          read += c.length;
          if (total) process.stderr.write(`\r[chromiumfish] ${Math.floor((read / total) * 100)}%`);
        });
        res.on("error", fail);
        res.pipe(out);
        out.on("finish", () => { process.stderr.write("\n"); out.close(() => resolve()); });
        out.on("error", fail);
      });
      req.on("error", reject);
      req.setTimeout(DOWNLOAD_IDLE_TIMEOUT_MS, () => {
        req.destroy(new Error(`download timed out (no data for ${DOWNLOAD_IDLE_TIMEOUT_MS}ms) for ${u}`));
      });
    };
    process.stderr.write(`[chromiumfish] downloading ${url}\n`);
    get(url);
  });
}

function fetchText(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const get = (u: string) => {
      const req = https.get(u, (res) => {
        if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          res.resume();
          return get(res.headers.location);
        }
        if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode}`)); }
        let data = "";
        res.setEncoding("utf8");
        res.on("data", (c) => (data += c));
        res.on("end", () => resolve(data));
        res.on("error", reject);
      });
      req.on("error", reject);
      req.setTimeout(FETCH_IDLE_TIMEOUT_MS, () => {
        req.destroy(new Error(`request timed out for ${u}`));
      });
    };
    get(url);
  });
}

function sha256(file: string): string {
  return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function extract(archive: string, dest: string): void {
  fs.mkdirSync(dest, { recursive: true });
  // Modern tar (incl. Windows 10+ bsdtar) extracts both .tar.gz and .zip.
  const r = spawnSync("tar", ["-xf", archive, "-C", dest], { stdio: "inherit" });
  if (r.status !== 0) throw new Error(`extraction failed for ${archive}`);
}

export async function fetchBrowser(version = browserVersion(), force = false): Promise<string> {
  const target = installDir(version);
  if (force && fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true });

  const cached = findBinary(target);
  if (cached) return cached;

  const base = releaseBaseUrl(version);
  const asset = assetName(version);
  const archive = path.join(cacheRoot(), version, asset);

  await download(`${base}/${asset}`, archive);

  try {
    const expected = (await fetchText(`${base}/${asset}.sha256`)).trim().split(/\s+/)[0];
    const actual = sha256(archive);
    if (actual !== expected) {
      fs.rmSync(archive, { force: true });
      throw new Error(`checksum mismatch for ${asset}: ${actual} !== ${expected}`);
    }
  } catch (e: any) {
    if (String(e?.message || e).includes("HTTP"))
      process.stderr.write("[chromiumfish] warning: no .sha256 published, skipping verification\n");
    else throw e;
  }

  extract(archive, target);
  fs.rmSync(archive, { force: true });
  macosPrepare(target);

  const bin = findBinary(target);
  if (!bin) throw new Error(`no browser binary found in extracted build at ${target}`);
  if (process.platform !== "win32") fs.chmodSync(bin, 0o755);
  process.stderr.write(`[chromiumfish] ready: ${bin}\n`);
  return bin;
}

/**
 * Identity-clean macOS prep: strip the download
 * quarantine flag, and ensure an ad-hoc signature so Apple Silicon will run the
 * binary — no certificate, name, or identity attached. Release builds ship
 * ad-hoc signed; this is a defensive fallback.
 */
function macosPrepare(target: string): void {
  if (process.platform !== "darwin") return;
  spawnSync("xattr", ["-dr", "com.apple.quarantine", target], { stdio: "ignore" });
  const app = fs.readdirSync(target).find((n) => n.endsWith(".app"));
  const signTarget = app ? path.join(target, app) : findBinary(target);
  if (signTarget) {
    const valid = spawnSync("codesign", ["--verify", "--quiet", signTarget]).status === 0;
    if (!valid) spawnSync("codesign", ["--force", "--deep", "--sign", "-", signTarget], { stdio: "ignore" });
  }
}

export async function binaryPath(version = browserVersion(), download = true): Promise<string> {
  const existing = findBinary(installDir(version));
  if (existing) return existing;
  if (!download) throw new Error(`ChromiumFish ${version} not installed. Run \`npx chromiumfish fetch\`.`);
  return fetchBrowser(version);
}
