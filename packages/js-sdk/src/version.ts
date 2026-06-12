/**
 * Pinned browser build + release coordinates.
 *
 * The browser is built privately and published to this repo's GitHub Releases.
 * `DEFAULT_BROWSER_VERSION` is the release tag (without the leading `v`) the
 * SDK downloads by default; override it with `CHROMIUMFISH_VERSION`.
 */

/** SDK package version (kept in sync with package.json). */
export const SDK_VERSION = "0.1.4";

/** Default ChromiumFish browser build to fetch. Matches src/chrome/VERSION. */
export const DEFAULT_BROWSER_VERSION = "150.0.7844";

/** Public repo hosting the release assets. */
export const RELEASE_REPO = "arman-bd/chromiumfish";

/**
 * IP-to-Timezone database, built by `packages/geoip/build_ip2tz.py`.
 * IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0.
 *
 * Default `"latest"` auto-tracks the newest monthly build: the SDK reads a small
 * pointer (the `geoip-latest` release manifest) to discover the current concrete
 * version, so no SDK republish is needed when a new DB ships. Pin a specific
 * version with `CHROMIUMFISH_GEOIP_VERSION` (e.g. `"2026.06"`) for reproducibility.
 */
export const DEFAULT_GEOIP_VERSION = "latest";

/**
 * Concrete version used when `"latest"` cannot be resolved (offline + no cached
 * pointer). Bump occasionally so the offline floor stays recent.
 */
export const GEOIP_FALLBACK_VERSION = "2026.06";

/**
 * Reject version strings that aren't a plain build tag. Versions are
 * interpolated into filesystem cache paths and release URLs, so a crafted
 * value like `../../../etc` would escape the cache dir (path traversal).
 * Real tags are digits, dots, and hyphens (e.g. "150.0.7844", "2026.06",
 * "latest").
 */
export function assertSafeVersion(version: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(version) || version === "." || version === "..") {
    throw new Error(`invalid version string: ${JSON.stringify(version)}`);
  }
  return version;
}

export function browserVersion(): string {
  return assertSafeVersion(process.env.CHROMIUMFISH_VERSION || DEFAULT_BROWSER_VERSION);
}

export function releaseBaseUrl(version = browserVersion()): string {
  return `https://github.com/${RELEASE_REPO}/releases/download/v${version}`;
}

export function geoipVersion(): string {
  return assertSafeVersion(process.env.CHROMIUMFISH_GEOIP_VERSION || DEFAULT_GEOIP_VERSION);
}

export function geoipBaseUrl(version = geoipVersion()): string {
  return `https://github.com/${RELEASE_REPO}/releases/download/geoip-${version}`;
}

/** Stable URL of the pointer that names the current concrete DB version. */
export function geoipLatestManifestUrl(): string {
  return `https://github.com/${RELEASE_REPO}/releases/download/geoip-latest/latest.json`;
}
