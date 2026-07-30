# Upgrading THREE.js

The app uses THREE.js for 3D rendering, as a *vendored* dependency: the
library's files are copied into this repo (under `js/three/`) and committed,
pinned at a known version, rather than fetched from a package manager or CDN
when the app builds or runs. Benefits: the app works offline, there's no
third-party service in the runtime path, and rendering can only break when we
deliberately change something — never spontaneously because an upstream
release moved. The cost is that upgrades are manual, which is what this
document is for.

## Why manual, and how often

Loading "the latest" THREE at runtime would mean the app breaks at some
arbitrary future date, for every player at once, with no commit to bisect —
THREE releases monthly and does make breaking changes (deprecations live for
roughly ten releases, then get removed). A pinned copy breaks only during an
upgrade, exactly when someone is watching.

There's little pressure to chase releases: the app uses a narrow, stable
slice of THREE's API (BufferGeometry, basic meshes/materials, Raycaster,
sprites, OrbitControls), and as a client-side renderer of our own data files
it carries little security exposure. Upgrading roughly **once a year**, or
when a specific fix or feature is wanted, is plenty. Falling behind mainly
costs performance improvements and makes the eventual jump span more
releases.

## The vendored files

All live in `js/three/` and MUST come from the same THREE version —
mismatched files break in confusing ways:

- **`three.module.min.js`** — the THREE library's ES-module build entry
  ("module" = uses `import`/`export`, which is how all our code imports it),
  minified ("min"). The npm package also contains an unminified
  `three.module.js`, handy temporarily when debugging into THREE itself.
- **`three.core.min.js`** — required companion: `three.module.min.js`
  imports the bulk of the library from it. Forgetting this file fails fast
  with `ERR_MODULE_NOT_FOUND ... three.core.min.js`. In general, check the
  top of the new `three.module.min.js` for relative imports to see which
  companion files that release needs.
- **`OrbitControls.js`** — the camera controls, from `examples/jsm/controls/`
  in the npm package, **with one local edit**: its import of the bare
  specifier `'three'` (which would need an importmap) is changed to
  `'./three.module.min.js'`. A header comment in the file records this and
  points here.

You never build these yourself: the npm package `three` is THREE.js's
canonical prebuilt distribution. Version numbering: three.js release rNNN is
published to npm as version 0.NNN.P — the middle number is the release
number, and the patch number P is usually 0 but nonzero when a hotfix was
republished after the release (e.g. npm 0.185.1 is three.js r185 plus a bug
fix; there is no "r185.1" in three.js's own naming). Use the release number
(r185) when reading the migration guide, and the full npm version string
(0.185.1) when downloading.

## Upgrade procedure

1. Find the latest stable version:

   ```bash
   curl -s https://registry.npmjs.org/three/latest
   ```

   The `"version"` field is the latest stable release (`latest` is npm's
   default dist-tag, which by convention only ever points to stable,
   non-prerelease publishes). `npm view three version` gives the same answer.

2. Skim the migration guide for breaking changes across the versions you're
   jumping: https://github.com/mrdoob/three.js/wiki/Migration-Guide

3. Download the official npm artifact (a plain tarball; no npm project
   needed), using the exact version string from step 1:

   ```bash
   curl -LO https://registry.npmjs.org/three/-/three-0.NNN.P.tgz
   ```

   (e.g. `three-0.185.1.tgz`)

4. From the tarball, copy into `js/three/`:
   - `package/build/three.module.min.js`
   - `package/build/three.core.min.js`
   - `package/examples/jsm/controls/OrbitControls.js`

   (And check the top of the new `three.module.min.js` for any other
   relative imports the release may have added.)

5. Re-apply the local edit to the fresh `OrbitControls.js`: change
   `from 'three'` to `from './three.module.min.js'`, and restore the
   vendoring header comment (pointing to this document).

6. Update the version number in `docs/project-overview.md` (Key
   Implementation Details), run `npm test`, and browser-smoke a few grids:
   load them, click edges, rotate/zoom, and Check solution.

## Notes from past upgrades

- **r170 → r185 upgrade** (July 2026): this range included the module-build
  split (~r171): `three.module.min.js` stopped being self-contained and now
  imports the bulk of the library from `./three.core.min.js` (the core is
  shared with the WebGPU build), so `three.core.min.js` became a newly
  vendored file. Historical context on build flavors: the old `three.min.js`
  — a UMD build creating a global `THREE` variable for classic `<script>`
  tags — was deprecated around r150 and no longer ships; the ES-module build
  is the right and only choice for this codebase's `import`-based code.
- **r170 → r185 migration-guide skim** (July 2026): nothing in this range breaks the API
  slice we use (geometry, materials, sprites, raycasting, renderer). One
  deprecation to plan for: **`Clock` was deprecated in r182** in favor of
  `Timer` (in the core `THREE` namespace since r179). We used `Clock` in
  SceneManager (created/started), main.js (`getDelta()` for controls), and
  ui.js (`getElapsedTime()` for the solve time). Note `Timer` doesn't pause
  on tab-hide unless you call `timer.connect(document)`. *(Migrated to
  `Timer` right after this upgrade, July 2026 — with `connect(document)`,
  so the solve timer no longer counts time while the tab is hidden.)*
  Also, r175 changed
  `Controls.connect()` to require a DOM element — irrelevant to us as long
  as we construct `OrbitControls(camera, domElement)` and never call
  `connect()` directly.
