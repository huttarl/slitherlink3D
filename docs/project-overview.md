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
- **Check the About card's links**: `npm run test:links` — fetches the outbound
  links the catalogue produces and insists on HTTP 200. Needs the network, so
  `npm test` skips it. Run it after adding a polyhedron, whose link is derived
  from its name and so is otherwise unverified.
  It only fetches links it has no record of, keeping that record in
  `js/tests/links-checked.json` (committed, and updated by the run itself), so
  adding one solid costs one request rather than re-asking every site we link to
  for pages we verified long ago. `SLI_CHECK_ALL_LINKS=1 npm run test:links`
  re-checks everything, for the occasional audit — worth doing rarely, since
  these are other people's servers.

The Python utilities under `util/` have a pytest suite:

- **Run Python tests**: `pytest util/tests` from the repo root. That runs
  everything, including the `slow`-marked data/ puzzle-uniqueness sweep. Most of
  it is fast, puzzles being generated to be solvable by deduction so the solver
  rarely has to search; the largest grids dominate the runtime. `pytest
  util/tests -m slow` runs only the sweep; `-m "not slow"` skips it when you want
  the quick answer.
- Python deps used by `util/` are declared in `requirements.txt` (`compas`,
  `networkx`, `matplotlib`, `numpy`, `scipy`, `pytest`), with a note there on
  which script needs what. None of them are needed to play or develop the
  browser app. Python 3.11 or newer.

      python3 -m venv .venv
      .venv/bin/pip install -r requirements.txt

  A venv matters more than it looks: on a machine with several Pythons, the one
  first on `PATH` is easily not the one carrying these libraries, and the
  generators then fail with a bare `ModuleNotFoundError`.
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
   the page with new parameters. A URL naming neither is a cold launch, which
   is the **title screen** and loads one of the larger solids at random instead
   — `titleScreen.js::gridIdFromUrl()` is the single answer (async, since the
   pick reads the catalogue, and cached), so the pickers can't label a different
   solid than the one on screen.
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

On a cold launch, `main.js` also calls `initTitleScreen()` before step 1, to wire
the two buttons. Everything visual about the title screen — hiding the panel,
showing the title box — is done by main.html's inline pre-paint script, so it is
already on screen while the solid is still loading. Both buttons
navigate to `?grid=<DEFAULT_GRID>`; "How to Play" adds `?howto=1`, which
`openHowToPlay()` acts on and then strips from the URL.

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
- `titleScreen.js` — the cold-launch title screen: the app's name over a
  tumbling solid, zoomed in a little closer than a board, showing a **display
  puzzle** — its clues plus its solution loop drawn in as filled-in marks
  (`showTitleLoop`). Display puzzles live under `displayPuzzles` in the puzzle
  file, never in `puzzles`, so the loop on show is nothing a player can be given;
  a grid without one shows clues and no loop. The loop can't be edited because
  the overlay covers the canvas and `interaction.js` ignores pointer events
  aimed anywhere else. No panel. `wantsTitleScreen()` is the rule (no `?grid=`, no `?puzzle=`), and it's
  duplicated in main.html's inline script, which has to hide the panel before
  the first paint. Which solid is a random pick per launch, from the playable
  grids with at least `TITLE_SCREEN_MIN_FACES` faces — big enough to look
  impressive, and big enough to have several puzzles, so showing one off can't
  spoil a grid's only puzzle. Start and How to Play both navigate to
  `DEFAULT_GRID`.
- `aboutSolid.js` — the opt-in "About this solid" card: family and categories,
  V/E/F, the face census, the vertex configuration where every vertex is alike,
  and Euler's formula. Shown behind the ⓘ beside the polyhedron picker and
  below the Next button on the celebration overlay (never above it — see
  ideas/learning-about-polys.md). Facts come from the loaded grid, so the card
  can't disagree with what's on screen; only the categories come from the
  catalogue.
- `polyhedronLinks.js` — where the card's links go: Polytope Wiki per solid,
  George Hart's Virtual Polyhedra per family, Plus Magazine for Euler's formula.
  Deliberately not Wikipedia. Per-solid URLs are derived from the polyhedron's
  name (a MediaWiki title is the name with underscores for spaces), with a small
  exception table for the solids that rule gets wrong. A polyhedron added later is
  linked automatically; `npm run test:links` then confirms the pages exist (it
  needs the network, so the everyday suite skips it).
- `solidFacts.js` — the pure topology behind that card: `faceCensus`,
  `facesAroundVertex` (walks the fan of faces round a vertex), and
  `vertexConfiguration`, which returns the shared cycle only when every vertex
  has the same one. No DOM, no THREE; unit-tested headless.
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
        ├── aboutSolid.js ───┬─ catalogue.js
        │                    └── solidFacts.js
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
    `checkFeedback.js`, `puzzlePicker.js`, `confirmDialog.js`, `aboutSolid.js`,
    `titleScreen.js`
  - Polyhedron facts: `solidFacts.js`, `polyhedronLinks.js`, plus `categories`
    in the grid data and `groupGridsByFamily` in `catalogue.js`
  - Configuration: `constants.js`; `debug.js` (gated tracing)
  - Data loading: `puzzleLoader.js` (puzzle JSON), plus
    `loadPolyhedronFromJSON()` in `geometry.js`
  - Tests: `tests/` — headless unit tests for the game logic
    (run with `npm test`; see Development Commands)
- **data/** — grid (`*.json`) and puzzle (`*-puzzles.json`) files (format
  spec in `docs/json-format.md`), plus `grids.json`, the generated catalogue
  the app's pickers read (rebuild with `util/build_catalogue.py`).
  - Formatting: one line per vertex, per face and per clue list, via
    `util/json_format.py` — the generators write that way, and
    `python3 util/json_format.py data/*.json` reformats existing files in place
    (idempotent, and it refuses to write if the parsed data would change).
    Neither extreme is readable: minified puts a grid on one 1000-character
    line, while `indent=3` gave every coordinate a line of its own (491 lines
    for three puzzles on the truncated icosidodecahedron).
- **docs/** — `json-format.md` (authoritative format reference),
  `project-overview.md` (this file), `upgrading-THREE.md` (how and when to
  upgrade the vendored THREE.js), `edge-pair-constraints.md` (the design for
  teaching the solver about pairs of edges — planned, not built).
- **ideas/** — `TODOs.md` and design notes (e.g. `graph-cycles.txt`).
- **util/** — Python utilities:
  - `genUniformPolyh.py` — generates Platonic/Archimedean grid JSON from exact
    coordinates, verifying uniformity before writing.
  - `genGoldberg.py` — generates a Goldberg polyhedron GP(m,n) from its two
    parameters, by subdividing an icosahedron and taking the polar dual.
  - `genPrism.py` — generates an n-prism or n-antiprism from exact coordinates,
    with every face a regular polygon.
  - `genDual.py` — the dual of a grid, by polar reciprocation; `--all-catalan`
    writes all 13 Catalan solids from the Archimedean ones in `data/`.
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
  - `fill_puzzles.py` — generates puzzles for every grid that hasn't any, one
    after another, smallest first; start it and leave it. Each grid's puzzles are
    written only if at least one was produced, so a grid that times out is either
    filled with what the generator managed or left untouched.
  - `sweep_grids.py` — generates one puzzle for every grid and reports how good it
    is, writing nothing: time taken, loop length against the ceiling (the vertex
    count, since the loop is a simple cycle through vertices), the largest
    connected patch of faces the loop never touches, and the clue count — each
    against the mean of the puzzles already in `data/`. The regression test for
    changes to the *generator*, as distinct from the solver: a change that speeds
    generation up while making the puzzles duller shows here and nowhere else. The
    seed is fixed and reported so two runs are comparable; with a varying seed the
    per-grid differences are noise.
  - `build_catalogue.py` — regenerates `data/grids.json` from the data files.
  - `catalogue_report.py` — prints what `data/` holds: a line per grid with its
    counts, puzzles, display puzzles and categories, plus totals, and a note on
    any grid with no puzzles or (if it's big enough for the title screen) no
    display puzzle. `--clues` switches to the puzzle view — face census, the clue
    values the puzzles use, and how many faces carry a clue — which is how to
    judge whether a new grid will make decent puzzles. Takes grid names to report
    on just those. Reads only.
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

  The grid's `gridId`/`gridName` are derived from the OBJ's group name — the
  whole of it, so `g Random sphere B` gives that name and a `RandomsphereB` id.
  The converter sanity-checks Euler's formula (F + V = E + 2) and fails
  if it doesn't hold. It writes no `categories`, so add the family by hand.

- **`genGoldberg.py`**: generates a Goldberg polyhedron — 12 pentagons, the
  rest hexagons, three faces at every vertex — from its parameters (m,n):

  ```
  python3 util/genGoldberg.py 1 2 gp12 "Goldberg GP(1,2)" > data/gp12.json
  ```

  GP(1,0) is the dodecahedron and GP(1,1) the truncated icosahedron, which we
  already had from exact coordinates; running those two through this script is
  the check that its lattice arithmetic is right. It works in two easy steps
  rather than one hard one: subdivide the icosahedron's faces along the
  triangular lattice to get the *geodesic* dual (whose triangles are then just a
  convex hull), and take the polar dual of that about the unit sphere, which
  yields exactly flat faces. Every run verifies the result against the counts
  GP(m,n) must have (10T+2 faces, 20T vertices, 30T edges for
  T = m² + mn + n²), the 12-pentagon census, trivalent vertices, and flatness,
  and exits non-zero if any of it is off. Output is deterministic, so
  regenerating a grid doesn't invalidate the puzzles built on it. Requires
  `numpy` and `scipy`.

- **`genDual.py`**: the dual of an existing grid — and the way the Catalan
  solids are made, since each is the dual of an Archimedean solid:

  ```
  util/genDual.py --all-catalan        # all 13, straight into data/
  util/genDual.py data/aC.json         # one, to stdout
  ```

  It works by **polar reciprocation** about a sphere concentric with the solid:
  the vertex replacing a face is the pole of that face's plane, so the face
  replacing a vertex `v` lies in the plane `x·v = 1` and is exactly flat. That
  also explains why this is the right construction rather than an approximation:
  reciprocation preserves the symmetry group, and an Archimedean solid is
  vertex-transitive, so the symmetries that carry any vertex to any other carry
  the dual's faces to each other — the faces come out congruent, which is what
  defines a Catalan solid. The reciprocating radius only scales the result, so
  there is nothing to tune.

  Each solid is checked before being written: Euler's formula, congruent faces
  (edge lengths and angles, with separate tolerances since one unit says nothing
  about the other), flatness, and outward winding. The names and categories come
  from a table keyed by the primal's `gridId`, and the `recipe` is Conway's — `d`
  prefixed to the primal's, so the cuboctahedron's dual `daC` is the rhombic
  dodecahedron. Verified against the literature on the way in: that solid's
  rhombi come out at 70.53°/109.47°, and the rhombic triacontahedron's at
  63.43°/116.57°.

  One caveat worth knowing: the dual inherits the primal's stored precision.
  `data/tI.json` and `data/sD.json` came through `obj2json.py`, which rounds to 3
  decimals, so their duals' faces agree only to about a quarter of a degree
  rather than exactly. Harmless, but it is why the congruence tolerances aren't
  tighter.

- **`genPrism.py`**: generates a prism or antiprism, all of whose faces are
  regular polygons:

  ```
  python3 util/genPrism.py 6 P6 "Hexagonal prism" > data/P6.json
  python3 util/genPrism.py --anti 5 A5 "Pentagonal antiprism" > data/A5.json
  ```

  Exact coordinates: two regular n-gons of circumradius 1/(2 sin(π/n)), a unit
  apart for a prism, and for an antiprism twisted half a step and set
  √(1 − 1/(4cos²(π/2n))) apart, which is what makes the lateral faces unit
  squares or equilateral triangles. Every run checks that all edges are the same
  length, that each face's corners are equidistant from its centre (equal edges
  plus equal radii is regularity, for a flat face), that faces are flat, and that
  the winding is outward — exiting non-zero otherwise. Standard library only.

  Both families are infinite, which is why they're excluded from the Johnson
  solids and why the script takes n. Two sizes it declines to be used for: the
  square prism is the cube and the triangular antiprism is the octahedron, both
  already in `data/` from `genUniformPolyh.py`. (Running it on those anyway is a
  useful check — it reproduces them, with a note saying so.)

- **`genRandomPolyh.py`**: generates a random sphere-like polyhedron —
  scatters points on a sphere (randomly with simulated repulsion to spread
  them evenly, or via golden spiral with `--spiral`), takes the convex hull,
  then merges nearly-coplanar adjacent triangles into quads. The OBJ it writes
  then goes through `obj2json.py` as above:

  ```
  util/genRandomPolyh.py 20 --quiet --name "Random sphere B" --out /tmp/b.obj
  python3 util/obj2json.py /tmp/b.obj > data/randB.json
  ```

  `--name` sets the OBJ group name, which is where `obj2json.py` gets the
  grid's name, so each solid needs its own. `--quiet` skips the matplotlib
  animation and the window, which a scripted run wants. Requires `numpy` and
  `scipy`.

  What the plain method gives is worth knowing before reaching for it. Repulsion
  spreads the points so evenly that hardly any adjacent triangles end up
  coplanar, so the result is nearly all triangles — 0 quads out of 28 faces at
  n=16, 1 out of 35 at n=20 — and neither `--spiral` nor a looser `--angle`
  changes that much (2 and 4 quads respectively at n=20). Triangles admit clues
  0–2 only, so those grids have the same narrow clue vocabulary as the
  icosahedron; what they add is irregularity, with vertex degrees and face sizes
  varying across the solid. Puzzle generation on them is quick, and the clue
  density it settles on (51–61% of faces) is mid-pack for the collection. Small n
  is wasted: 12 points under repulsion converge on the icosahedron exactly, which
  `data/` already has.

  Two other methods produce faces that aren't triangles. Both end in a convex
  hull, so neither needs a planarization or canonicalization pass:

  - `--dual` takes the hull — a triangulation — and returns its **polar dual**
    (`polar_dual` from `genGoldberg.py`). Every triangle becomes a three-valent
    vertex and every point becomes a face with as many sides as that point had
    neighbours, so there are *no* triangles at all and n is the FACE count
    (3n−6 edges, 2n−4 vertices). The face census is the triangulation's degree
    distribution, which is what `--relax` steers: fully spread points give 12
    pentagons and hexagons for the rest (Euler forces exactly 12 when no degree
    strays from 5 or 6), unrelaxed ones anything from triangles to octagons.
  - `--seeds` scatters regular polygons of 3 to 6 sides (sizes drawn as 3 plus
    three coin flips, so 4s and 5s dominate) over the sphere and lets the hull
    triangulate the gaps. Each seed's corners sit on a small circle within its
    own cap, so they are exactly coplanar and no other vertex lies above their
    plane — which is what makes the hull keep each seed as one face.
    `merge_coplanar_faces` from `genUniformPolyh.py` recovers them from the
    triangulation. The catch is arithmetic, not implementation: with S seeds on n
    vertices, Euler's formula fixes the filler count at **T = n + 2S − 4**
    regardless of how well the seeds are packed, so seeds averaging 4.5 sides
    leave about 15% of the faces non-triangular. Tighter packing only shrinks the
    triangles. Reach for `--dual` when you want the census dominated by larger
    faces, and `--seeds` when you want to choose the face sizes yourself.

  `--relax` (0 to 1) is how evenly the points are spread: the repulsion is run to
  convergence and the points are then moved that fraction of the way there, so
  the knob means the same thing at every n — unlike stopping the simulation after
  a fixed number of iterations. It defaults to 0.5, but to 0.9 with `--seeds`,
  which can afford it: there the relaxation only spreads the seed *centres*,
  while the seed sizes are drawn separately, so unlike `--dual` a high setting
  costs nothing in face variety and it keeps unevenly spaced seeds from leaving
  sliver triangles in the gaps. Measured over 6 solids per setting at n=30, the
  sharpest corner any face had was 19° at relax 0.5, 23° at 0.75 and 27° at 0.9,
  with no gain at 1.0; `SEED_FILL` matters as much, at 27° for 0.7 against 8° for
  0.97, where seeds nearly touch and squeeze the fillers flat.

  `--min-edge` (default 0.4, and only used by `--dual`) is the shortest edge to
  tolerate, as a fraction of the median. The dual puts a vertex at each
  triangle's pole, so two nearly coplanar triangles produce two vertices almost
  on top of each other — an edge nobody can see, between two vertices nobody can
  tell apart. One solid had 5 of its 84 edges under 0.10 against a median of
  0.38, the worst at 0.015, where the drawn vertex spheres alone are 0.04 across.
  `separate_short_edges` walks those apart and re-flattens the faces after each
  nudge. The faces then aren't *exactly* flat any more, but the residual is
  smaller than the rounding `obj2json.py` applies anyway.

### Step 2: Generate puzzles for the grid

`genSliPuzzles.py` generates puzzles for a given grid, in two phases
(spec: `ideas/puzzle gen algorithm.txt`):

- **Phase A — solution**: paint one connected region of faces red and the rest
  blue, and take the edges between differently-colored faces as the solution loop.
  The coloring lives in a `RegionColoring` object, and it is *grown* rather than
  repaired: start from one face and repeatedly adopt a frontier face, always at the
  region's tips so the region stays ragged and its boundary long, and never
  adopting a face that would put four loop edges at one vertex. Then hill-climb the
  result, flipping single faces and keeping a flip only if it stays valid and
  shrinks the largest patch of faces the loop never touches — stopping at good
  enough rather than at an optimum, since pushing every grid to its longest
  possible loop leaves the small ones with no uniquely-solvable clue set.

  This replaced an earlier approach that painted every face at random and then
  repaired the two regions until each was connected. That could not terminate on
  some solids, because reconnecting one color cuts the other: on the triakis
  octahedron it ran 137,000 passes without settling, which for a long time looked
  like a slow uniqueness proof rather than a livelock. Growth cannot livelock —
  connectivity is an invariant of the construction, and everything else is a test
  whose failure discards one cheap attempt. `util/sweep_grids.py` is what measures
  whether a change here helps or hurts.
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

For a batch — a set of new grids, say — `util/fill_puzzles.py` runs the generator
over every grid that hasn't any puzzles yet, smallest first, and can be left
unattended:

```
util/fill_puzzles.py                          # all the empty ones
util/fill_puzzles.py --timeout 3600 dbD       # one, with longer to work
```

It writes each grid's file only once at least one puzzle exists, so a grid that
runs out of time keeps whatever the generator salvaged or stays as it was, and it
prints how long each took.

Two more options, both passed through by `run_gen.py`:

- `--display=N` also generates N puzzles under `displayPuzzles` — the loops the
  title screen shows off, kept out of `puzzles` so they can never be handed to a
  player (see `docs/json-format.md`). Default 1; `--display=0` turns it off.
  They are ordinary puzzles by every other measure, generated last and checked
  against both lists so a display puzzle isn't a copy of a playable one. Two
  puzzles may still share a *loop* under different clues: nothing on screen tells
  the player the loops match, so the title screen gives nothing away.
- `--existing=FILE` keeps the puzzles already in `FILE` and generates around
  them. That's how a display puzzle is added to a grid that already ships
  puzzles: they come out byte-identical, so nobody's bookmarked `?puzzle=`
  number moves. Use a temporary file, since the shell truncates the input
  otherwise:

  ```
  util/run_gen.py -q --display=1 --existing=data/aC-puzzles.json \
      data/aC.json 0 600 > /tmp/aC.json && mv /tmp/aC.json data/aC-puzzles.json
  ```

  A grid too small to have a spare puzzle simply gets no `displayPuzzles`, and
  its title screen shows clues with no loop. (Only grids with fewer than
  `TITLE_SCREEN_MIN_FACES` faces should be in that position, and those never
  reach the title screen anyway.)

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
`data/` holds the Platonic and Archimedean solids, a selection of Johnson
solids, and some Goldberg polyhedra, each with a few puzzles. For the actual
inventory — what's there today, with counts, categories and puzzle numbers —
run `util/catalogue_report.py`; it reads the data, so it can't go stale the way
a figure written down here does.

The tetrahedron is the one grid with a single puzzle, and the reason is worth
knowing: its loop is always some face's boundary, that face's clue is excluded
for having a deficit of 0, and all four faces are equivalent under the solid's
symmetries, so every such puzzle is the same one turned around.

Every puzzle is uniquely solvable AND solvable by deduction, and no two on a
grid are the same board up to rotation or reflection -- verified by the
solver, and re-verified any time by the `slow`-marked pytest sweep, which
runs as part of a normal `pytest util/tests`.

Uniqueness checks are time-budgeted, so generation stays bounded even where
the solver's search would blow up. Generating a few puzzles takes seconds on
small grids and minutes on the largest. Cost tracks face composition as much as
size, which is the surprise worth remembering: the 72-edge truncated
cuboctahedron generated ~17x faster than the 90-edge truncated dodecahedron,
whose 20 triangles admit only clues 0-3 and so give propagation less to work
with (see the difficulty discussion in `ideas/TODOs.md`).

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
