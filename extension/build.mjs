// Build script: bundle the three extension entry points and copy static assets
// into dist/. Run `npm run build` (or `npm run watch`). Load dist/ as an
// unpacked extension in chrome://extensions.
import { build, context } from "esbuild";
import { cp, rm, mkdir } from "node:fs/promises";

const watch = process.argv.includes("--watch");
const outdir = "dist";

const options = {
  entryPoints: {
    content: "src/content.ts",
    background: "src/background.ts",
    popup: "src/popup/main.tsx",
  },
  outdir,
  bundle: true,
  format: "iife",
  jsx: "automatic",
  target: ["chrome110"],
  sourcemap: watch,
  minify: !watch,
  logLevel: "info",
};

await rm(outdir, { recursive: true, force: true });
await mkdir(outdir, { recursive: true });
// Static assets (manifest.json, popup.html, icons) live in public/.
await cp("public", outdir, { recursive: true });

if (watch) {
  const ctx = await context(options);
  await ctx.watch();
  console.log("watching for changes…");
} else {
  await build(options);
  console.log("built → dist/");
}
