# Project Overview

Slitherlink3D is an interactive 3D puzzle game that brings the classic Slitherlink puzzle to polyhedral surfaces. Players solve puzzles by drawing loops on the edges of 3D polyhedra (dodecahedrons, cubes) following traditional Slitherlink rules. The project uses Three.js for 3D rendering and is structured as a client-side web application. Python scripts are used to generate polyhedra and puzzles to be played on them.

## Development Commands

The JS side of the app runs directly in the browser with no build process:

- **Run the application**: Open `main.html` in a web browser or serve via a local web server
- **Local development server**: `python3 -m http.server 8000` (or any static file server)
- **No build/lint commands** for the JS code — vanilla ES modules.
- **Run JS unit tests**: `npm test` (equivalently `node --test "js/tests/*.test.js"`).
  Uses Node's built-in test runner — no npm install, no dependencies. Covers the
  headless game logic (Grid topology, solution checking, undo/redo history);
  rendering and interaction are still verified manually in the browser.
  Run these after changing game-logic files in `js/`.

The Python utilities under `util/` have a pytest suite:

- **Run Python tests**: `pytest util/tests` from the repo root.
  Thorough-but-slow tests (e.g. the data/ puzzle-uniqueness sweep) are
  skipped by default; `pytest --all util/tests` runs everything, and
  `pytest -m slow util/tests` runs only the slow ones.
- Python deps used by `util/`: `compas`, `networkx`, `matplotlib`, `pytest`
  (plus `numpy` and `scipy` for `genRandomPolyh.py`).
- Run the suite after changing any file in `util/`.
- **Generate puzzles**: `util/run_gen.py data/<id>.json` — see
  "Generating polyhedra and puzzles" below.

## Architecture overview

### Runtime startup (high level)

`main.js` calls `createGameState()` (in `scene.js`), then runs the render loop.

`createGameState()`:
1. Gets the singleton `GameState` and initializes it.
2. Asks `SceneManager` to create the THREE.Scene; adds the underwater skybox.
3. Loads the polyhedron and puzzle JSON in parallel
   (`loadPolyhedronFromJSON()` from `geometry.js`, `loadPuzzleData()` from `puzzleLoader.js`).
   Currently the grid filename is hardcoded in `scene.js` (e.g. `"D"`).
4. Hands the loaded data to `GameState.setupScene()`, which copies grid topology
   into the `PuzzleGrid`, applies clues, and validates the solution.
5. Builds edge cylinders (`createEdgeGeometry()`), vertex spheres, and
   clue/label sprites.
6. `setupUI(gameState)` (in `ui.js`) wires DOM buttons and constructs the
   `interaction` object.

`main.js` then drives `requestAnimationFrame` → `updateTextVisibility()` →
`controls.update()` → `gameState.render()`.

### Central objects

- **GameState** (`js/GameState.js`) — singleton; owns `SceneManager`, `PuzzleGrid`,
  and the `interaction` handler. Top-level coordinator for setup, toggles
  (show IDs, show solution), resize, render, dispose.
- **SceneManager** (`js/SceneManager.js`) — owns all THREE.js objects: scene,
  camera, renderer, OrbitControls, clock, lights, polyhedron mesh,
  edge meshes, vertex group, text/label groups.
- **Grid** (`js/Grid.js`) — pure topology: `Map`s of `Vertex`, `Edge`, `Face`
  by ID, plus a `vertexPairToEdge` hash for O(1) edge lookup. Also stores
  cross-references to THREE geometry (`faceMap`, `faceVertexRanges`,
  `edgeMeshMap`).
- **PuzzleGrid extends Grid** (`js/PuzzleGrid.js`) — adds puzzle data, clue
  application, solution validation/highlighting, user-guess checking
  (`checkUserSolution`), and the "solved" celebration.
- **Vertex / Edge / Face** (`js/Vertex.js`, `Edge.js`, `Face.js`) — small data
  classes. Each carries a `metadata` object: e.g. `Edge.metadata.userGuess`
  (0=unknown, 1=filled, 2=ruled out), `Face.metadata.clue`, `.index`,
  `.isHighlighted`, etc.

### Geometry & rendering

- `geometry.js` — defines hardcoded cube and dodecahedron, plus
  `loadPolyhedronFromJSON()`; `createPolyhedron()` builds the THREE
  `BufferGeometry` with one fan per face (centroid + ring of vertices) so
  faces can be color-highlighted; `createEdgeGeometry()` makes a cylinder per
  edge; `normalizeVertices()` re-centers and rescales to unit radius.
- `textRenderer.js` — sprite-based labels: face clues, vertex IDs, edge IDs.
  Uses `Intl.NumberFormat(gameState.numberLocale)` for clue digits.
- `skybox.js` — procedural underwater backdrop (canvas gradient + caustics).

### Input & UI

- `interaction.js::makeInteraction(gameState)` — raycasts on click to either
  cycle an edge state or toggle a face highlight; uses OrbitControls
  start/change to suppress click-on-drag.
- `ui.js::setupUI(gameState)` — wires the "show IDs" / "show solution" /
  "check solution" controls and the dismissable overlay; defines
  `displayOverlay(title, message)`.
- `constants.js` — colors, radii, zoom limits, `EDGE_STATES` array.

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
    ├── geometry.js (loadPolyhedronFromJSON, createEdgeGeometry, …)
    ├── puzzleLoader.js (loadPuzzleData)
    ├── skybox.js
    ├── textRenderer.js
    └── ui.js (setupUI → interaction.js)
```

## File organization

- **js/** — all ES6 modules; Three.js vendored under `js/three/`.
  - Core game logic: `Grid.js`, `PuzzleGrid.js`, `Face.js`, `Edge.js`,
    `Vertex.js`, `GameState.js`
  - Rendering: `SceneManager.js`, `scene.js`, `geometry.js`, `skybox.js`,
    `textRenderer.js`
  - Input/UI: `interaction.js`, `ui.js`
  - Configuration: `constants.js`
  - Data loading: `puzzleLoader.js` (puzzle JSON), plus
    `loadPolyhedronFromJSON()` in `geometry.js`
  - Tests: `tests/` — headless unit tests for the game logic
    (run with `npm test`; see Development Commands)
- **data/** — grid (`*.json`) and puzzle (`*-puzzles.json`) files. Format
  spec in `docs/json-format.md`.
- **docs/** — `json-format.md` (authoritative format reference),
  `project-overview.md` (this file).
- **ideas/** — `TODOs.md` and design notes (e.g. `graph-cycles.txt`).
- **util/** — Python utilities:
  - `obj2json.py` — converts polyHédronisme OBJ → grid JSON.
  - `genRandomPolyh.py` — random polyhedron generator.
  - `genSliPuzzles.py` — puzzle generator: paints faces red/blue, ensures each
    color is connected and non-boring, derives the loop along edges between
    differently-colored faces, then uses `slisolver` to whittle clues to a
    minimal uniquely-solvable set.
  - `slisolver.py` — solver used to verify clue uniqueness.
    (`slisolver_old.py` is a retired earlier draft, kept for reference.)
  - `run_gen.py` — wrapper that runs `genSliPuzzles.py` headlessly with a
    timeout (see "Generating polyhedra and puzzles").
  - `tests/` — pytest suite covering `slisolver.py` and the
    clue-minimization workflow in `genSliPuzzles.py`.
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

Two sources:

- **polyHédronisme** (http://levskaya.github.io/polyhedronisme/): construct a
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
  faces as the solution loop.
- **Phase B — clues**: compute each face's wall count, then whittle the
  clues down to a fairly minimal subset that still yields a *unique*
  solution. Uniqueness is checked by `slisolver.py` (constraint propagation
  + depth-first search); the minimal prefix of a random clue ordering is
  found by binary search, and the best of several random orderings wins.

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

## Key Implementation Details

- **Three.js version**: r170 (vendored locally at `js/three/three.module.min.js`
  and `js/three/OrbitControls.js`; imported via relative ES module paths —
  no CDN, no importmap).
- **Coordinate system**: Right-handed with Z-up orientation
- **Edge interaction**: Click edges to cycle through unknown→filledIn→ruledOut→unknown
- **Face interaction**: Click faces to highlight them (debugging feature)
- **Camera controls**: OrbitControls for 3D navigation with zoom constraints

## Current State & TODOs

The project is in active development.

The Python puzzle-generation pipeline (solver + generator) works end-to-end
and is covered by the pytest suite, though so far it has only been exercised
on small grids (cube, dodecahedron).

On the JS side, the core play loop works: grid and puzzle JSON are loaded and
validated at startup, clues are displayed, edge guesses are checked as you go
(passive mode), and the "Check solution" button does a full win check
(constraint violations, single complete loop) with a celebration on success.

Key incomplete features:
- Grid and puzzle selection: the grid is hardcoded in `scene.js`
  (`gridFilename = "D"`) and the puzzle index to 0 — any grid JSON loads,
  but there's no UI to choose a grid/puzzle or advance to the next one,
  and no catalogue of available grids.
- User feedback on errors: several failure cases (clue violations,
  incomplete or multiple loops) are detected but only logged to the
  console, not yet shown to the user.
- Undo and reset of edge guesses.

See `ideas/TODOs.md` for the detailed development roadmap.
