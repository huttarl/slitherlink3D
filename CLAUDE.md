# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Slitherlink3D is an interactive 3D puzzle game that brings the classic Slitherlink puzzle to polyhedral surfaces. Players solve puzzles by drawing loops on the edges of 3D polyhedra (dodecahedrons, cubes) following traditional Slitherlink rules. The project uses Three.js for 3D rendering and is structured as a client-side web application.

## Development Commands

The JS side of the app runs directly in the browser with no build process:

- **Run the application**: Open `main.html` in a web browser or serve via a local web server
- **Local development server**: `python3 -m http.server 8000` (or any static file server)
- **No build/lint commands** for the JS code — vanilla ES modules.

The Python utilities under `util/` have a pytest suite:

- **Run Python tests**: `pytest util/tests` from the repo root.
- Python deps used by `util/`: `compas`, `networkx`, `matplotlib`, `pytest`.
- Run the suite after changing any file in `util/`.

## General principles for assisting Lars

- **Don't be sycophantic.** Don't try to "empathize" with mistaken ideas. It's much more helpful to push back (politely) when the user seems to be wrong, than to go along with mistaken assumptions.
- **Don't assert more confidence than is warranted.** Better to express uncertainty than to sound knowledgeable while giving wrong information.
- **Don't remove information in comments.** If you think a comment is obsolete, ask before deleting it. You can propose rewording, but don't lose information.

## Coding style

- Lean toward **clarity** for generalist developers, not code golfing that requires a reader to be an expert in the particular programming language.
  - For example, when assigning to a tuple in Python, use parentheses on the LHS. E.g. `(a, b) = 1, 2` instead of `a, b = 1, 2`.

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
- **data/** — grid (`*.json`) and puzzle (`*-puzzles.json`) files. Format
  spec in `docs/json-format.md`.
- **docs/** — `json-format.md` (authoritative format reference).
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
  - `tests/` — pytest suite, currently focused on `slisolver.py`.
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

## Key Implementation Details

- **Three.js version**: r170 (vendored locally at `js/three/three.module.min.js`
  and `js/three/OrbitControls.js`; imported via relative ES module paths —
  no CDN, no importmap).
- **Coordinate system**: Right-handed with Z-up orientation
- **Edge interaction**: Click edges to cycle through unknown→filledIn→ruledOut→unknown
- **Face interaction**: Click faces to highlight them (debugging feature)
- **Camera controls**: OrbitControls for 3D navigation with zoom constraints

## Current State & TODOs

The project is in active development. Key incomplete features:
- Puzzle loading from JSON data files
- Win condition detection
- Solution validation
- Multiple polyhedron support beyond cube/dodecahedron

See `ideas/TODOs.md` for detailed development roadmap.
