/**
 * IP-to-Timezone lookup backed by the downloadable `ip2tz` release asset.
 *
 * IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0.
 *
 * The asset is built offline by `packages/geoip/build_ip2tz.py` from DB-IP City
 * Lite and published to GitHub Releases. At runtime this module downloads it
 * once (SHA-256 verified, cached next to the browser build), then answers
 * IP -> IANA timezone with a binary search over the raw record bytes — no
 * per-call network round trip.
 *
 *   import { lookupTimezone, resolveTimezone } from "chromiumfish";
 *   await lookupTimezone("8.8.8.8");   // -> "America/Los_Angeles"
 *   await resolveTimezone();           // probe own egress IP -> its timezone
 *
 * Binary format is documented in build_ip2tz.py; reader and builder must stay
 * in lock-step.
 */
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as https from "node:https";
import * as path from "node:path";
import { cacheRoot } from "./fetch.js";
import { GEOIP_FALLBACK_VERSION, geoipBaseUrl, geoipLatestManifestUrl, geoipVersion } from "./version.js";

const MAGIC = Buffer.from("IP2TZ\x01", "latin1");
const V4_REC = 6; // uint32 start + uint16 tz_idx
const V6_REC = 18; // 16-byte start + uint16 tz_idx
const EGRESS_PROBE = "https://ipinfo.io/json";

const LATEST = "latest";
// Seconds a resolved "latest" pointer is trusted before re-checking the
// manifest. Override with CHROMIUMFISH_GEOIP_TTL.
const LATEST_TTL = Number(process.env.CHROMIUMFISH_GEOIP_TTL) || 7 * 24 * 3600;

function geoipDir(): string {
  return path.join(cacheRoot(), "geoip");
}

function pointerPath(): string {
  return path.join(geoipDir(), "latest.json");
}

function readPointer(): { version?: string } | null {
  try {
    return JSON.parse(fs.readFileSync(pointerPath(), "utf8"));
  } catch {
    return null;
  }
}

function pointerFresh(): boolean {
  try {
    return Date.now() - fs.statSync(pointerPath()).mtimeMs < LATEST_TTL * 1000;
  } catch {
    return false;
  }
}

/** Best-effort resolution with NO network: fresh cached pointer, else floor. */
function resolveVersionSync(version = geoipVersion()): string {
  if (version !== LATEST) return version;
  const p = readPointer();
  if (p?.version && pointerFresh()) return p.version;
  return p?.version || GEOIP_FALLBACK_VERSION;
}

/**
 * Resolve a configured version (possibly the `"latest"` sentinel) to a concrete
 * version like `"2026.06"`. Uses a cached pointer while fresh (< TTL); otherwise
 * fetches the geoip-latest manifest. Falls back to a stale pointer, then to the
 * compiled-in floor, so resolution never hard-fails offline.
 */
export async function resolveVersion(version = geoipVersion(), download = true): Promise<string> {
  if (version !== LATEST) return version;
  const cached = readPointer();
  if (cached?.version && pointerFresh()) return cached.version;
  if (download) {
    try {
      const manifest = JSON.parse((await get(geoipLatestManifestUrl())).toString("utf8"));
      if (manifest?.version) {
        fs.mkdirSync(geoipDir(), { recursive: true });
        fs.writeFileSync(pointerPath(), JSON.stringify(manifest));
        return manifest.version;
      }
    } catch (e: any) {
      process.stderr.write(`[chromiumfish] could not resolve latest ip2tz version: ${e?.message || e}\n`);
    }
  }
  return cached?.version || GEOIP_FALLBACK_VERSION;
}

export function assetName(version = geoipVersion()): string {
  return `ip2tz-${resolveVersionSync(version)}.bin`;
}

export function dbPath(version = geoipVersion()): string {
  return path.join(geoipDir(), `ip2tz-${resolveVersionSync(version)}.bin`);
}

function get(url: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const go = (u: string) =>
      https
        .get(u, (res) => {
          if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            res.resume();
            return go(res.headers.location);
          }
          if (res.statusCode !== 200) {
            res.resume();
            return reject(new Error(`HTTP ${res.statusCode}`));
          }
          const chunks: Buffer[] = [];
          res.on("data", (c) => chunks.push(c));
          res.on("end", () => resolve(Buffer.concat(chunks)));
        })
        .on("error", reject);
    go(url);
  });
}

export async function fetchDb(version = geoipVersion(), force = false): Promise<string> {
  const v = await resolveVersion(version); // concrete, e.g. "2026.06"
  const dest = path.join(geoipDir(), `ip2tz-${v}.bin`);
  if (fs.existsSync(dest) && !force) return dest;

  const url = `${geoipBaseUrl(v)}/ip2tz-${v}.bin`;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  process.stderr.write(`[chromiumfish] downloading ${url}\n`);
  const blob = await get(url);

  try {
    const expected = (await get(`${url}.sha256`)).toString("utf8").trim().split(/\s+/)[0];
    const actual = createHash("sha256").update(blob).digest("hex");
    if (actual !== expected) throw new Error(`ip2tz checksum mismatch: ${actual} !== ${expected}`);
  } catch (e: any) {
    if (String(e?.message || e).includes("HTTP"))
      process.stderr.write("[chromiumfish] warning: no ip2tz .sha256 published, skipping verify\n");
    else throw e;
  }

  const tmp = `${dest}.part`;
  fs.writeFileSync(tmp, blob);
  fs.renameSync(tmp, dest);
  return dest;
}

export class Ip2TzDB {
  private tz: string[] = [];
  private v4: Buffer;
  private v6: Buffer;
  private v4Count: number;
  private v6Count: number;
  readonly buildEpoch: number;

  constructor(blob: Buffer) {
    if (!blob.subarray(0, MAGIC.length).equals(MAGIC))
      throw new Error("not an ip2tz database (bad magic)");
    this.buildEpoch = blob.readUInt32BE(6);
    const tzCount = blob.readUInt16BE(10);
    this.v4Count = blob.readUInt32BE(12);
    this.v6Count = blob.readUInt32BE(16);

    let off = 20;
    for (let i = 0; i < tzCount; i++) {
      const len = blob.readUInt8(off);
      off += 1;
      this.tz.push(blob.toString("utf8", off, off + len));
      off += len;
    }
    this.v4 = blob.subarray(off, off + this.v4Count * V4_REC);
    off += this.v4Count * V4_REC;
    this.v6 = blob.subarray(off, off + this.v6Count * V6_REC);
  }

  static load(file: string): Ip2TzDB {
    return new Ip2TzDB(fs.readFileSync(file));
  }

  /** Index of the rightmost record whose start <= key (fixed-width BE compare). */
  private static rightmost(block: Buffer, count: number, rec: number, keylen: number, key: Buffer): number {
    let lo = 0;
    let hi = count;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      const base = mid * rec;
      // block.compare(key, ...) returns sign(record_start - key); advance when
      // record_start <= key so we land on the rightmost such record.
      if (block.compare(key, 0, keylen, base, base + keylen) <= 0) lo = mid + 1;
      else hi = mid;
    }
    return lo - 1;
  }

  lookup(ip: string): string | null {
    const v4 = parseV4(ip);
    if (v4) {
      const i = Ip2TzDB.rightmost(this.v4, this.v4Count, V4_REC, 4, v4);
      if (i < 0) return null;
      return this.tz[this.v4.readUInt16BE(i * V4_REC + 4)] || null;
    }
    const v6 = parseV6(ip);
    if (v6) {
      // IPv4-mapped (::ffff:a.b.c.d) lives in the v4 subtree — route it there.
      const mapped =
        v6.readBigUInt64BE(0) === 0n && v6.readUInt16BE(8) === 0 && v6.readUInt16BE(10) === 0xffff;
      if (mapped) {
        const key = v6.subarray(12, 16);
        const i = Ip2TzDB.rightmost(this.v4, this.v4Count, V4_REC, 4, key);
        return i < 0 ? null : this.tz[this.v4.readUInt16BE(i * V4_REC + 4)] || null;
      }
      const i = Ip2TzDB.rightmost(this.v6, this.v6Count, V6_REC, 16, v6);
      if (i < 0) return null;
      return this.tz[this.v6.readUInt16BE(i * V6_REC + 16)] || null;
    }
    return null;
  }
}

/** 4-byte BE buffer for a dotted IPv4, or null. */
function parseV4(ip: string): Buffer | null {
  const m = ip.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return null;
  const b = Buffer.alloc(4);
  for (let i = 0; i < 4; i++) {
    const n = Number(m[i + 1]);
    if (n > 255) return null;
    b[i] = n;
  }
  return b;
}

/** 16-byte BE buffer for an IPv6 string (handles ::, IPv4-mapped), or null. */
function parseV6(ip: string): Buffer | null {
  if (!ip.includes(":")) return null;
  // Map ::ffff:1.2.3.4 form by expanding its trailing dotted quad to hex.
  let s = ip;
  const dotted = s.match(/(.*:)(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (dotted) {
    const v4 = parseV4(`${dotted[2]}.${dotted[3]}.${dotted[4]}.${dotted[5]}`);
    if (!v4) return null;
    s = dotted[1] + v4.subarray(0, 2).toString("hex") + ":" + v4.subarray(2, 4).toString("hex");
  }
  const halves = s.split("::");
  if (halves.length > 2) return null;
  const head = halves[0] ? halves[0].split(":") : [];
  const tail = halves.length === 2 && halves[1] ? halves[1].split(":") : [];
  const fill = 8 - head.length - tail.length;
  if (fill < 0 || (halves.length === 1 && head.length !== 8)) return null;
  const groups = [...head, ...Array(halves.length === 2 ? fill : 0).fill("0"), ...tail];
  if (groups.length !== 8) return null;
  const b = Buffer.alloc(16);
  for (let i = 0; i < 8; i++) {
    const n = parseInt(groups[i] || "0", 16);
    if (Number.isNaN(n) || n > 0xffff) return null;
    b.writeUInt16BE(n, i * 2);
  }
  return b;
}

let cached: Ip2TzDB | null = null;

async function getDb(version = geoipVersion(), download = true): Promise<Ip2TzDB> {
  if (cached) return cached;
  const v = await resolveVersion(version, download);
  let p = path.join(geoipDir(), `ip2tz-${v}.bin`);
  if (!fs.existsSync(p)) {
    if (!download) throw new Error("ip2tz DB not installed. Call fetchDb().");
    p = await fetchDb(v);
  }
  cached = Ip2TzDB.load(p);
  return cached;
}

export async function lookupTimezone(ip: string, version = geoipVersion(), download = true): Promise<string | null> {
  return (await getDb(version, download)).lookup(ip);
}

export function egressIp(proxy?: string, timeoutMs = 8000): Promise<string | null> {
  // Note: proxy support for the probe would require an https-proxy agent; when
  // a proxy is configured we currently probe direct and rely on the caller to
  // pass an explicit IP if egress differs.
  void proxy;
  return new Promise((resolve) => {
    const req = https.get(EGRESS_PROBE, { headers: { "User-Agent": "chromiumfish" } }, (res) => {
      let data = "";
      res.setEncoding("utf8");
      res.on("data", (c) => (data += c));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data).ip || null);
        } catch {
          resolve(null);
        }
      });
    });
    req.on("error", () => resolve(null));
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve(null);
    });
  });
}

export async function resolveTimezone(opts: {
  ip?: string;
  proxy?: string;
  version?: string;
  download?: boolean;
} = {}): Promise<string | null> {
  const { proxy, version = geoipVersion(), download = true } = opts;
  let ip = opts.ip;
  if (!ip) {
    ip = (await egressIp(proxy)) || undefined;
    if (!ip) return null;
  }
  return lookupTimezone(ip, version, download);
}
