/**
 * Pinned browser build + release coordinates.
 *
 * The browser is built privately and published to this repo's GitHub Releases.
 * `DEFAULT_BROWSER_VERSION` is the release tag (without the leading `v`) the
 * SDK downloads by default; override it with `CHROMIUMFISH_VERSION`.
 */

/** SDK package version (kept in sync with package.json). */
export const SDK_VERSION = "0.1.0";

/** Default ChromiumFish browser build to fetch. Matches src/chrome/VERSION. */
export const DEFAULT_BROWSER_VERSION = "150.0.7844";

/** Public repo hosting the release assets. */
export const RELEASE_REPO = "arman-bd/chromiumfish";

export function browserVersion(): string {
  return process.env.CHROMIUMFISH_VERSION || DEFAULT_BROWSER_VERSION;
}

export function releaseBaseUrl(version = browserVersion()): string {
  return `https://github.com/${RELEASE_REPO}/releases/download/v${version}`;
}
