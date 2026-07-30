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

Both live in `js/three/` and MUST come from the same THREE version —
mismatched pairs break in confusing ways:

- **`three.module.min.js`** — the THREE library itself: the ES-module build
  ("module" = uses `import`/`export`, which is how all our code imports it),
  minified ("min"). The npm package also contains an unminified
  `three.module.js`, handy temporarily when debugging into THREE itself.
  (The old `three.min.js` — a UMD build creating a global `THREE` variable
  for classic `<script>` tags — was deprecated around r150 and no longer
  ships; the module build is the right and only choice for this codebase.)
- **`OrbitControls.js`** — the camera controls, from `examples/jsm/controls/`
  in the npm package, **with one local edit**: its import of the bare
  specifier `'three'` (which would need an importmap) is changed to
  `'./three.module.min.js'`. A header comment in the file records this and
  points here.

You never build these yourself: the npm package `three` is THREE.js's
canonical prebuilt distribution. Version numbering: three.js release rNNN =
npm version 0.NNN.0 (e.g. r170 = 0.170.0).

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
   needed):

   ```bash
   curl -LO https://registry.npmjs.org/three/-/three-0.NNN.0.tgz
   ```

4. From the tarball, copy into `js/three/`:
   - `package/build/three.module.min.js`
   - `package/examples/jsm/controls/OrbitControls.js`

5. Re-apply the local edit to the fresh `OrbitControls.js`: change
   `from 'three'` to `from './three.module.min.js'`, and restore the
   vendoring header comment (pointing to this document).

6. Update the version number in `docs/project-overview.md` (Key
   Implementation Details), run `npm test`, and browser-smoke a few grids:
   load them, click edges, rotate/zoom, and Check solution.
