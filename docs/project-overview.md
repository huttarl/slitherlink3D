# Project Overview

Slitherlink3D is an interactive 3D puzzle game that brings the classic Slitherlink
puzzle to polyhedral surfaces. Players solve puzzles by drawing loops on the edges
of 3D polyhedra (Platonic, Archimedean, and Johnson solids, among others)
following traditional Slitherlink rules. The project uses Three.js for 3D
rendering and is structured as a client-side web application. Python scripts are
used to generate polyhedra and puzzles to be played on them.

There are two halves, and they meet only at the JSON files in `data/`: a
browser app that plays puzzles, and Python tooling that makes them.

## Where things are

- **main.html** — the single page; loads `js/main.js` as an ES module.
- **js/** — the app: vanilla ES modules, no build step. Three.js is vendored
  under `js/three/`. → `docs/js-architecture.md`
- **data/** — grid files (`*.json`) and puzzle files (`*-puzzles.json`), plus
  `grids.json`, the generated catalogue the app's pickers read.
  → `docs/json-format.md`
- **util/** — Python: generators for polyhedra, the puzzle generator, the solver,
  and reporting tools. → `docs/generating-grids.md`,
  `docs/generating-puzzles.md`
- **docs/** — this file and the topic docs listed below.
- **ideas/** — `TODOs.md` (the roadmap) and design notes.

## Further reading

| doc | what's in it |
|---|---|
| `js-architecture.md` | startup sequence, the central objects, rendering, UI modules, module dependency graph, interaction conventions |
| `json-format.md` | authoritative spec for grid and puzzle files |
| `generating-grids.md` | every way a polyhedron gets into `data/`, and how each is verified |
| `generating-puzzles.md` | the two-phase puzzle generator, running it in batches, rebuilding the catalogue |
| `edge-pair-constraints.md` | the solver's edge-pair reasoning: design, and what it measured |
| `upgrading-THREE.md` | how and when to upgrade the vendored Three.js |

## Running the app

No build process:

- **Run it**: open `main.html` in a browser, or serve it.
- **Local development server**: `util/serve.py` (http.server plus
  `Cache-Control: no-cache`, so an edit is always picked up on reload; plain
  `python3 -m http.server 8000` can serve stale modules for days).

## Tests

- **`npm test`** — headless JS unit tests (Node's built-in runner; no install, no
  dependencies). Covers the game logic (Grid topology, solution checking,
  undo/redo history) and a few CSS conventions read out of `main.html`. Run after
  changing game-logic files in `js/`.
- **`npm run test:mobile`** — the real app in a real browser at phone size,
  asserting *where things land on screen* and how touch input sequences. Opt-in:
  needs a one-time `npm install --save-dev @playwright/test && npx playwright
  install chromium`. See `js/tests/mobile/README.md`.
- **`npm run test:links`** — fetches the About card's outbound links and insists
  on HTTP 200. Needs the network, so `npm test` skips it. Run after adding a
  polyhedron, whose link is derived from its name and so is otherwise unverified.
  It only fetches links it has no record of, keeping that record in
  `js/tests/links-checked.json` (committed, and updated by the run itself), so
  adding one solid costs one request rather than re-asking every site we link to
  for pages we verified long ago. `SLI_CHECK_ALL_LINKS=1 npm run test:links`
  re-checks everything, for the occasional audit — worth doing rarely, since
  these are other people's servers.
- **`pytest util/tests`** — the Python suite, including the `slow`-marked sweep
  that re-proves every puzzle in `data/` unique. `-m slow` runs only the sweep;
  `-m "not slow"` skips it. Run after changing any file in `util/`.

## Python utilities

Python 3.11 or newer. Dependencies are declared in `requirements.txt` (`compas`,
`networkx`, `matplotlib`, `numpy`, `scipy`, `pytest`), with a note there on which
script needs what. None of them are needed to play or develop the browser app.

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

A venv matters more than it looks: on a machine with several Pythons, the one
first on `PATH` is easily not the one carrying these libraries, and the
generators then fail with a bare `ModuleNotFoundError`.

The usual sequence for adding a solid is: generate the grid
(`docs/generating-grids.md`), generate puzzles for it
(`docs/generating-puzzles.md`), then rebuild the catalogue with
`util/build_catalogue.py` — until that last step runs, the new grid does not
appear in the app's picker.

## Current state

The project is in active development.

The Python pipeline (solver + generator) works end-to-end, and every grid in
`data/` has puzzles. For the actual inventory — what's there today, with counts,
categories and puzzle numbers — run `util/catalogue_report.py`; it reads the data,
so it can't go stale the way a figure written down here does.

Every puzzle is uniquely solvable AND solvable by deduction, and no two on a grid
are the same board up to rotation or reflection — verified by the solver, and
re-verified any time by the `slow`-marked pytest sweep.

Uniqueness checks are time-budgeted, so generation stays bounded even where the
solver's search would blow up. Cost tracks face composition as much as size,
which is the surprise worth remembering: an all-triangle solid admits only clues
0–2 and so gives propagation much less to work with than a solid of the same size
with larger faces.

The tetrahedron is the one grid with a single puzzle, and the reason is worth
knowing: its loop is always some face's boundary, that face's clue is excluded
for having a deficit of 0, and all four faces are equivalent under the solid's
symmetries, so every such puzzle is the same one turned around.

On the JS side, the core play loop works end-to-end: pick a polyhedron and puzzle
(dropdowns backed by `?grid=`/`?puzzle=` URL parameters), mark edges with
undo/redo and reset, get mistake feedback (passive red highlighting of rule
violations, toggleable; solution-mismatch counts with an undoable "Clear errors"
after an explicit check), and a celebration on solving. The game logic is covered
by the headless JS unit tests.

Bigger items still open (see `ideas/TODOs.md` for the full roadmap):

- Puzzle quality: measuring whether generated puzzles are *fun* — not just
  uniquely solvable — e.g. trivially propagatable vs. deep trial-and-error.
- A guided progression: a "next puzzle" button walking the catalogue order,
  rather than manual selection only.
- Switching grids/puzzles without a full page reload (needs careful THREE.js
  disposal; the reload approach deliberately sidesteps that for now).
- Player-facing polish: grid name/category on screen, face coloring to aid
  inside/outside reasoning, aesthetic animations, a "show errors" hint button.
