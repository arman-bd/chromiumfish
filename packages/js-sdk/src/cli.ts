#!/usr/bin/env node
import * as fs from "node:fs";
import { binaryPath, cacheRoot, fetchBrowser } from "./fetch.js";
import { SDK_VERSION, browserVersion } from "./version.js";

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
