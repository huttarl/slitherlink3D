# Project Overview

Slitherlink3D is an interactive 3D puzzle game that brings the classic Slitherlink puzzle to polyhedral surfaces. Players solve puzzles by drawing loops on the edges of 3D polyhedra (Platonic, Archimedean, and Johnson solids, among others) following traditional Slitherlink rules. The project uses Three.js for 3D rendering and is structured as a client-side web application. Python scripts are used to generate polyhedra and puzzles to be played on them.

## Development Commands

The JS side of the app runs directly in the browser with no build process:

- **Run the application**: Open `main.html` in a web browser or serve via a local web server
- **Local development server**: `util/serve.py` (http.server plus
  `Cache-Control: no-cache`, so an edit is always picked up on reload; plain
  `python3 -m http.server 8000` can serve stale modules for days).
- **No build/lint commands** for the JS code — vanilla ES modules.
- **Run JS unit tests**: `npm test` (equivalently `node --test "js/tests/*.test.js"`).
  Uses Node's built-in test runner — no npm install, no dependencies. Covers the
  headless game logic (Grid topology, solution checking, undo/redo history) and
  a few CSS conventions read straight out of `main.html`.
  Run these after changing game-logic files in `js/`.
- **Run phone-shaped tests**: `npm run test:mobile` — the real app in a real
  browser at phone size, asserting *where things land on screen* and how touch
  input sequences. Opt-in: needs a one-time `npm install --save-dev
  @playwright/test && npx playwright install chromium`. See
  `js/tests/mobile/README.md` for what each test is guarding against and what
  automation still can't tell you.

The Python utilities under `util/` have a pytest suite:

- **Run Python tests**: `pytest util/tests` from the repo root. That runs
  everything, including the `slow`-marked data/ puzzle-uniqueness sweep,
  in a few seconds — puzzles are generated to be solvable by deduction, so
  the solver never has to search. `pytest util/tests -m slow` runs only the
  sweep; `-m "not slow"` skips it, should it ever get expensive again.
- Python deps used by `util/`: `compas`, `networkx`, `matplotlib`, `pytest`
  (plus `numpy` and `scipy` for `genRandomPolyh.py` and `genUniformPolyh.py`).
- Run the suite after changing any file in `util/`.
- **Generate puzzles**: `util/run_gen.py data/<id>.json` — see
  "Generating polyhedra and puzzles" below.
- **Rebuild the grid catalogue** (`data/grids.json`, which the app's pickers
  read) after adding or removing data files: `python3 util/build_catalogue.py`.

## Architecture overview

### Runtime startup (high level)

`main.js` calls `createGameState()` (in `scene.js`), then runs the render loop.

`createGameState()`:
1. Gets the singleton `GameState` and initializes it.
2. Asks `SceneManager` to create the THREE.Scene; adds the underwater skybox.
3. Loads the polyhedron and puzzle JSON in parallel
   (`loadPolyhedronFromJSON()` from `geometry.js`, `loadPuzzleData()` from `puzzleLoader.js`).
   The grid and puzzle are chosen by the `?grid=` and `?puzzle=` URL
   parameters (default in `constants.js`); the pickers in the panel reload
   the page with new parameters.
4. Hands the loaded data to `GameState.setupScene()`, which copies grid topology
   into the `PuzzleGrid`, applies clues, and validates the solution.
5. Builds edge cylinders (`createEdgeGeometry()`), vertex spheres and clue
   digits (`clueRenderer.js`). The debugging ID labels (`idLabels.js`) are
   only registered here, and built if the player ever asks for them.
6. `setupUI(gameState)` (in `ui.js`) registers PuzzleGrid's UI observers,
   wires the DOM buttons, constructs the `interaction` object, and hands the
   pickers and the check-reporting to `puzzlePicker.js` and `checkFeedback.js`.
   (The panel's layout was already set up, before step 1, by
   `panelLayout.js::initPanelLayout()`.)

`main.js` then drives `requestAnimationFrame` → `updateTextVisibility()` →
`timer.update()` → `controls.update()` → `gameState.render()`.

### Central objects

- **GameState** (`js/GameState.js`) — singleton; owns `SceneManager`, `PuzzleGrid`,
  and the `interaction` handler. Top-level coordinator for setup, toggles
  (show IDs, show solution), resize, render, dispose.
- **SceneManager** (`js/SceneManager.js`) — owns all THREE.js objects: scene,
  camera, renderer, controls (Trackball or Orbit), timer, lights,
  polyhedron mesh, edge meshes, vertex group, text/label groups.
- **Grid** (`js/Grid.js`) — pure topology: `Map`s of `Vertex`, `Edge`, `Face`
  by ID, plus a `vertexPairToEdge` hash for O(1) edge lookup. Also stores
  cross-references to THREE geometry (`faceMap`, `faceVertexRanges`,
  `edgeMeshMap`).
- **PuzzleGrid extends Grid** (`js/PuzzleGrid.js`) — adds puzzle data, clue
  application, solution validation/highlighting, user-guess checking
  (`checkUserSolution`, whose pure rule/solution queries live in
  `solutionChecker.js`), the undo/redo history (each move is an array of
  edge-state deltas, so Reset and Clear-errors are single compound moves),
  and `clearErrors()`. Deliberately imports nothing from the UI/GameState
  layers (that once formed an import cycle): it exposes null-safe observer
  callbacks (`onHistoryChanged`, `onSolved`) that `ui.js` registers, and it
  runs headless in the JS unit tests.
- **solutionChecker** (`js/solutionChecker.js`) — pure queries mirroring the
  Python solver's rule structure: vertex violations, clue violations, the
  single-loop check, and solution mismatches (spoiler data: report counts,
  not locations).
- **Vertex / Edge / Face** (`js/Vertex.js`, `Edge.js`, `Face.js`) — small data
  classes. Each carries a `metadata` object: e.g. `Edge.metadata.userGuess`
  (0=unknown, 1=filled, 2=ruled out), `Face.metadata.clue`, `.index`,
  `.isHighlighted`, etc.

### Geometry & rendering

- `geometry.js` — `loadPolyhedronFromJSON()` loads a grid JSON file;
  `createPolyhedron()` builds the THREE `BufferGeometry` with one fan per
  face (centroid + ring of vertices) so faces can be color-highlighted;
  `createEdgeGeometry()` makes a cylinder per edge.
- `geometryUtils.js` — pure vector math (centroids, point-to-line distance,
  face inscribed radius, face normals, vertex normalization); no Grid or
  scene dependencies, unit-tested headless.
- `clueRenderer.js` — gameplay clue digits, drawn on canvas textures and
  "painted" onto faces, each sized to its face's inscribed circle; plus
  per-frame culling of clues on faces turned away from the camera.
  Uses `Intl.NumberFormat(gameState.numberLocale)` for the digits.
- `idLabels.js` — sprite-based debugging ID labels for vertices, edges and
  faces (the "Show IDs" checkbox), one shape and color per kind: green
  ellipse, pink rectangle, yellow diamond. Built on the first toggle rather
  than with the scene — a canvas and texture per label is ~100 ms on the
  truncated icosahedron's 182 of them — then kept, and added to or removed
  from the scene as the checkbox goes on and off. `createGameState` passes
  `SceneManager` the builder function; see `getIdLabelGroups()` and
  `GameState.toggleShowIDs`.
- `skybox.js` — procedural underwater backdrop (canvas gradient + caustics).

### Input & UI

- `interaction.js::makeInteraction(gameState)` — raycasts on tap/click to
  either cycle an edge state or toggle a face highlight; long press cycles
  the edge backwards (the touch stand-in for shift+click). Tracks pointer
  travel in pixels to suppress click-on-drag (deliberately NOT the
  controls' start/change events; see the comment in the file).
- `ui.js::setupUI(gameState)` — registers PuzzleGrid's observers (undo/redo
  button states; the solved celebration), and wires the controls it still owns:
  Undo/Redo (with Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y shortcuts), Reset,
  "Right side up", the "Auto-highlight mistakes" checkbox, the debug toggles,
  and the dismissable overlay (`displayOverlay(title, message)`). The bulkier
  UI concerns live in their own modules, which `setupUI` calls:
- `panelLayout.js::initPanelLayout()` — the main panel's two shapes: the full
  drawer, and the one-line strip a phone collapses to (which the in-play
  buttons are *moved* into, so each keeps one set of listeners). Also
  `isPanelCollapsed()`, which decides where a message should go, and
  `setWhereAmI()`, the strip's label. Called before the puzzle loads, so a
  phone never shows the full panel while waiting. No imports.
- `checkFeedback.js` — reporting how the solution is doing: the drawer's status
  line when the panel is open, a bottom toast bar when it's collapsed. Owns the
  Check and Clear-errors buttons, and the spoiler policy (mismatches reported
  as a count only).
- `puzzlePicker.js` — the polyhedron/puzzle pickers, populated from
  `data/grids.json`; the "Next puzzle" buttons; and the "are you sure?" that
  guards leaving a part-worked board. Navigating reloads the page with new
  `?grid=`/`?puzzle=` parameters.
- `confirmDialog.js` — our own yes/no dialog, in place of `window.confirm()`.
- `constants.js` — colors, radii, zoom limits, `EDGE_STATES` array.
- `debug.js::debug(...)` — `console.log` gated off by default; on with
  `?debug=1` in the URL, or `SLI_DEBUG=1` in the environment for the Node
  tests. The checker's and scene builder's traces go through it, so a genuine
  console warning isn't lost among them.

### Cross-reference structures (interaction critical)

- `faceMap` — geometry index-buffer triangle index → grid face ID (used by
  raycasting to identify the picked face).
- `faceVertexRanges` — face ID → `{start, count}` range in the geometry's
  vertex/color buffer (used to recolor a face on highlight).
- `edgeMeshMap` — edge ID → `THREE.Mesh` for the edge cylinder.

## Module dependencies (rough)

```
main.js
└── scene.js (createGameState)
    ├── GameState ── SceneManager
    │             └── PuzzleGrid (extends Grid → Edge/Face/Vertex)
    │                           └── solutionChecker.js
    ├── geometry.js (loadPolyhedronFromJSON, createEdgeGeometry)
    │   └── geometryUtils.js
    ├── puzzleLoader.js (loadPuzzleData)
    ├── skybox.js
    ├── clueRenderer.js ── geometryUtils.js
    ├── idLabels.js
    └── ui.js (setupUI → interaction.js; registers PuzzleGrid's observers)
        ├── checkFeedback.js ── panelLayout.js
        ├── puzzlePicker.js ─┬─ panelLayout.js
        │                    ├── confirmDialog.js
        │                    └── catalogue.js
        └── confirmDialog.js

main.js also calls panelLayout.js::initPanelLayout() directly, first of all.
debug.js is imported wherever there are traces to gate; it imports nothing.
```

The graph is acyclic: PuzzleGrid never imports upward (GameState/ui);
those layers subscribe to its observer callbacks instead.

## File organization

- **js/** — all ES6 modules; Three.js vendored under `js/three/`.
  - Core game logic: `Grid.js`, `PuzzleGrid.js`, `solutionChecker.js`,
    `Face.js`, `Edge.js`, `Vertex.js`, `GameState.js`
  - Rendering: `SceneManager.js`, `scene.js`, `geometry.js`,
    `geometryUtils.js`, `clueRenderer.js`, `idLabels.js`, `skybox.js`
  - Input/UI: `interaction.js`, `ui.js`, `panelLayout.js`,
    `checkFeedback.js`, `puzzlePicker.js`, `confirmDialog.js`
  - Configuration: `constants.js`; `debug.js` (gated tracing)
  - Data loading: `puzzleLoader.js` (puzzle JSON), plus
    `loadPolyhedronFromJSON()` in `geometry.js`
  - Tests: `tests/` — headless unit tests for the game logic
    (run with `npm test`; see Development Commands)
- **data/** — grid (`*.json`) and puzzle (`*-puzzles.json`) files (format
  spec in `docs/json-format.md`), plus `grids.json`, the generated catalogue
  the app's pickers read (rebuild with `util/build_catalogue.py`).
- **docs/** — `json-format.md` (authoritative format reference),
  `project-overview.md` (this file), `upgrading-THREE.md` (how and when to
  upgrade the vendored THREE.js).
- **ideas/** — `TODOs.md` and design notes (e.g. `graph-cycles.txt`).
- **util/** — Python utilities:
  - `genUniformPolyh.py` — generates Platonic/Archimedean grid JSON from exact
    coordinates, verifying uniformity before writing.
  - `obj2json.py` — converts polyHédronisme OBJ → grid JSON.
  - `genRandomPolyh.py` — random polyhedron generator.
  - `genSliPuzzles.py` — puzzle generator: paints faces red/blue, ensures each
    color is connected and non-boring, derives the loop along edges between
    differently-colored faces, then uses `slisolver` to whittle clues to a
    fairly minimal set that is still solvable by deduction.
  - `slisolver.py` — solver: propagation rules, clue patterns, face coloring,
    and bounded lookahead; used to check both deductive solvability and
    uniqueness.
    (`slisolver_old.py` is a retired earlier draft, kept for reference.)
  - `run_gen.py` — wrapper that runs `genSliPuzzles.py` headlessly with a
    timeout (see "Generating polyhedra and puzzles").
  - `build_catalogue.py` — regenerates `data/grids.json` from the data files.
  - `tests/` — pytest suite covering `slisolver.py`, the region coloring and
    clue-minimization workflow in `genSliPuzzles.py`, and a `slow`-marked
    uniqueness sweep of every puzzle in `data/`.
- **main.html** — single page; loads `js/main.js` as an ES module.

## Data formats

The authoritative spec is `docs/json-format.md`. In brief:

- **Grid JSON** (`data/<id>.json`): `gridId`, `gridName`, optional
  `categories`/`recipe`, `vertices` (`[[x,y,z], ...]`), `faces`
  (`[[v1,v2,v3,...], ...]`).
- **Puzzle JSON** (`data/<id>-puzzles.json`): `gridId` plus `puzzles[]`, each
  with `clues` (array indexed by face; -1 = no clue) and `solution` (ordered
  list of vertex IDs forming the loop, no repeat of first at end).

Vertex/face IDs in the running grid are the array indices from the JSON.

## Generating polyhedra and puzzles

The Python scripts in `util/` produce the JSON files in `data/`. They must be
run with a Python interpreter that has the required packages installed
(`compas`, `networkx`, `matplotlib`; see Development Commands) — the system
default `python3` may not have them.

### Step 1: Obtain a grid (polyhedron)

Three sources:

- **`genUniformPolyh.py`**: for a Platonic or Archimedean solid, whose exact
  vertex coordinates are known, this is the best source — it writes the grid
  JSON directly, with no OBJ step:

  ```
  python3 util/genUniformPolyh.py            # list the solids it knows
  python3 util/genUniformPolyh.py tO         # write data/tO.json
  python3 util/genUniformPolyh.py --all      # all of them
  python3 util/genUniformPolyh.py tO --check # verify without writing
  ```

  It hulls a vertex list, merges the hull's coplanar triangles back into the
  real polygonal faces (hexagons, octagons, ...), orders each face's vertices,
  and winds them outward. Truncations are derived from their Platonic seeds
  using the cut fraction that keeps the result uniform.

  Every solid is verified before being written — equal edge lengths, equal
  vertex radii, planar faces, the expected face census, Euler's formula, and
  consistent winding — and one that fails is *not* written. Requires `numpy`
  and `scipy`.

  Generating beats importing where it's possible, for a reason worth knowing:
  the rhombicuboctahedron and rhombicosidodecahedron have Johnson-solid twins
  with identical face censuses (J37 and J75, both in `data/`), so an OBJ of the
  wrong one would be nearly impossible to spot by counting faces.

- **polyHédronisme** (http://levskaya.github.io/polyhedronisme/): for anything
  `genUniformPolyh.py` doesn't cover (Johnson solids, exotica), construct the
  polyhedron interactively, export it as OBJ, then convert:

  ```
  python3 util/obj2json.py myPolyhedron.obj > data/myGrid.json
  ```

  The grid's `gridId`/`gridName` are derived from the OBJ's group name.
  The converter sanity-checks Euler's formula (F + V = E + 2) and fails
  if it doesn't hold.

- **`genRandomPolyh.py`**: generates a random sphere-like polyhedron —
  scatters points on a sphere (randomly with simulated repulsion to spread
  them evenly, or via golden spiral), takes the convex hull, then merges
  nearly-coplanar adjacent triangles into quads. Writes
  `polyhedron_with_quads.obj`, which then goes through `obj2json.py` as
  above. There are no command-line arguments; parameters (method, vertex
  count, quad-merge threshold) are set by editing its `main()`. It also
  requires `numpy` and `scipy`, and displays a matplotlib animation while
  running.

### Step 2: Generate puzzles for the grid

`genSliPuzzles.py` generates puzzles for a given grid, in two phases
(spec: `ideas/puzzle gen algorithm.txt`):

- **Phase A — solution**: randomly paint faces red/blue, force each color
  region to be connected (via a dual graph in networkx), disrupt "boring"
  all-one-color neighborhoods, and take the edges between differently-colored
  faces as the solution loop. The coloring and its bookkeeping live in a
  `RegionColoring` object; the boundary is rejected unless it is a single
  simple loop, which counts as a failed attempt and re-randomizes.
- **Phase B — clues**: compute each face's wall count, then whittle the
  clues down to a fairly minimal subset that is still *solvable by
  deduction* at `LOOKAHEAD_DEPTH` — a stronger requirement than a unique
  solution, and the difference between a puzzle you can reason through and
  one that needs trial and error. Checked by `slisolver.py` (constraint
  propagation, clue patterns, coloring, and bounded suppositions); the
  minimal prefix of a random clue ordering is found by binary search, and
  the best of several random orderings wins.

Two ways to run it:

- **Headless with a timeout** (good for testing; no GUI windows):

  ```
  util/run_gen.py data/myGrid.json [numPuzzles] [timeoutSeconds]
  ```

  Defaults: 1 puzzle, 60-second timeout (exit status 124 on timeout, like
  GNU `timeout`). The wrapper's shebang selects `python3.11`; edit that if
  your compas-equipped interpreter is a different one.

- **Directly** (opens the interactive matplotlib 3D view of the mesh):

  ```
  python3.11 util/genSliPuzzles.py data/myGrid.json [numPuzzles]
  ```

Either way, the puzzle JSON goes to stdout and all diagnostic/progress
output goes to stderr, so a clean puzzle file can be captured with:

```
util/run_gen.py data/myGrid.json > data/myGrid-puzzles.json
```

(Add `2>/dev/null` to hide the progress chatter.) Note that generation is
random and not seeded from the command line, so runs are not reproducible.

### Step 3: Rebuild the grid catalogue

The app's polyhedron/puzzle pickers can't scan `data/` at runtime (a static
site can't list a directory over HTTP); they read `data/grids.json`. After
adding, removing, or regenerating grid or puzzle files, rebuild it:

```
python3 util/build_catalogue.py
```

This scans `data/`, pairs each grid file with its `-puzzles.json`, counts
faces/edges/puzzles, and writes the catalogue sorted by size (edges, then
faces) — the order the picker presents, intended eventually as the player's
progression order. A new grid won't appear in the picker until this has run.

## Key Implementation Details

- **Three.js version**: r185 (npm 0.185.1), vendored locally under `js/three/`
  (`three.module.min.js`, its required companion `three.core.min.js`, and
  `OrbitControls.js`); imported via relative ES module paths —
  no CDN, no importmap. To upgrade it — occasional and deliberate — see
  [upgrading-THREE.md](upgrading-THREE.md).
- **Coordinate system**: Right-handed with Z-up orientation
- **Edge interaction**: Click edges to cycle through unknown→filledIn→ruledOut→unknown
- **Face interaction**: Click faces to highlight them (debugging feature)
- **Camera controls**: TrackballControls by default — unconstrained tumbling
  in any direction, with a "Right side up" button to undo any resulting roll.
  Loading with `?controls=orbit` switches to OrbitControls, which keeps the
  view level so the player can't get disoriented, at the cost of dragging
  stopping at the poles. Clue digits stay legible either way, since
  `clueRenderer` rolls them toward the camera each frame.

## Current State & TODOs

The project is in active development.

The Python puzzle-generation pipeline (solver + generator) works end-to-end.
`data/` currently holds **26 grids with 76 puzzles**: all 5 Platonic solids,
all 13 Archimedean solids, and 8 Johnson solids, ranging from the tetrahedron
(4 faces, 6 edges) to the truncated icosidodecahedron (62 faces, 180 edges).
Every grid offers 3 puzzles except the tetrahedron, which has exactly one
puzzle in total: its loop is always some face's boundary, that face's clue is
excluded for having a deficit of 0, and all four faces are equivalent under
the solid's symmetries, so every such puzzle is the same one turned around.

Every puzzle is uniquely solvable AND solvable by deduction, and no two on a
grid are the same board up to rotation or reflection -- verified by the
solver, and re-verified any time by the `slow`-marked pytest sweep, which
runs as part of a normal `pytest util/tests`.

Uniqueness checks are time-budgeted, so generation stays bounded even where
the solver's search would blow up. Generating a couple of puzzles takes
seconds on small grids and about 9 minutes at 180 edges, which is roughly the
practical ceiling today. Notably, cost tracks face composition as much as
size: the 72-edge truncated cuboctahedron generated ~17x faster than the
90-edge truncated dodecahedron, whose 20 triangles admit only clues 0-3 and so
give propagation less to work with (see the difficulty discussion in
`ideas/TODOs.md`).

On the JS side, the core play loop works end-to-end: pick a polyhedron and
puzzle (dropdowns backed by `?grid=`/`?puzzle=` URL parameters), mark edges
with undo/redo and reset, get mistake feedback (passive red highlighting of
rule violations, toggleable; solution-mismatch counts with an undoable
"Clear errors" after an explicit check), and a celebration on solving.
The game logic is covered by the headless JS unit tests.

Bigger items still open (see `ideas/TODOs.md` for the full roadmap):
- Puzzle quality: measuring whether generated puzzles are *fun* — not just
  uniquely solvable — e.g. trivially propagatable vs. deep trial-and-error.
- A guided progression: a "next puzzle" button walking the catalogue order,
  rather than manual selection only.
- Switching grids/puzzles without a full page reload (needs careful THREE.js
  disposal; the reload approach deliberately sidesteps that for now).
- Player-facing polish: grid name/category on screen, face coloring to aid
  inside/outside reasoning, aesthetic animations, a "show errors" hint
  button.
