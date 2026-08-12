# JS architecture

How the browser app is put together: what happens on startup, which objects own
what, and which modules depend on which. See `docs/project-overview.md` for the
short version and how to run it.

## Runtime startup (high level)

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

## Central objects

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

## Geometry & rendering

- `geometry.js` — `loadPolyhedronFromJSON()` loads a grid JSON file;
  `createPolyhedron()` builds the THREE `BufferGeometry` with one fan per
  face (centroid + ring of vertices) so faces can be color-highlighted;
  `createEdgeGeometry()` makes a cylinder per edge.
- `geometryUtils.js` — pure vector math (centroids, point-to-line distance,
  face inscribed radius, face normals, vertex normalization); no Grid or
  scene dependencies, unit-tested headless. Also `radiusScale()` and
  `pickTolerances()`, the one multiplier the edge radius, the vertex radius and
  the click tolerance all pass through — so it is where the grid's edge length
  and the player's pointer (see `pointer.js`) are both applied, and the only
  thing here that wants a `window`.
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

## Input & UI

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
  - `?debug=1` also enables the **`s` key: solve the puzzle outright** and run the
    check (`PuzzleGrid.fillInSolution`, then a click on Check). It exists so the
    solve celebration can be watched repeatedly without hand-solving a 131-edge
    loop each time, and it is gated because it hands over the answer. Recorded as
    one compound move, so a single Undo puts the board back.

## Cross-reference structures (interaction critical)

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

## Files under js/

All ES6 modules; Three.js vendored under `js/three/`.

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
- What the player's device is like, each a single media query with its reasoning:
  `motion.js` (does it want less animation?) and `pointer.js` (a finger or a
  mouse?)
- Data loading: `puzzleLoader.js` (puzzle JSON), plus
  `loadPolyhedronFromJSON()` in `geometry.js`
- Celebration: `celebration.js` (lights running round the solved loop) and
  `celebrationSound.js` (the tune, synthesized) — see `docs/celebration.md`
- Tests: `tests/` — headless unit tests for the game logic (run with `npm test`).
  Includes `modules-load.test.js`, which imports every module in `js/` and so
  catches a syntax error, a bad import path or a misspelled named import in the
  many modules no other test reaches (ES modules link before they run, so the
  import alone proves all three). It replaces checking those by hand.

## Conventions worth knowing

- **Coordinate system**: right-handed with Z-up orientation.
- **Edge interaction**: clicking an edge cycles unknown → filledIn → ruledOut →
  unknown.
- **Face interaction**: clicking a face highlights it (a debugging feature).
- **Camera controls**: TrackballControls by default — unconstrained tumbling
  in any direction, with a "Right side up" button to undo any resulting roll.
  Loading with `?controls=orbit` switches to OrbitControls, which keeps the
  view level so the player can't get disoriented, at the cost of dragging
  stopping at the poles. Clue digits stay legible either way, since
  `clueRenderer` rolls them toward the camera each frame.
- **Three.js version**: r185 (npm 0.185.1), vendored locally under `js/three/`
  (`three.module.min.js`, its required companion `three.core.min.js`, and
  `OrbitControls.js`); imported via relative ES module paths — no CDN, no
  importmap. To upgrade it — occasional and deliberate — see
  [upgrading-THREE.md](upgrading-THREE.md).
