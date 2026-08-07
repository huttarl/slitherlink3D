# Generating puzzles

How `data/<id>-puzzles.json` files are produced for an existing grid, and how the
catalogue the app reads gets rebuilt afterwards. For making the grid itself, see
`docs/generating-grids.md`.

## The two phases

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
  whose failure discards one cheap attempt.
- **Phase B — clues**: compute each face's wall count, then whittle the
  clues down to a fairly minimal subset that is still *solvable by
  deduction* at `LOOKAHEAD_DEPTH` — a stronger requirement than a unique
  solution, and the difference between a puzzle you can reason through and
  one that needs trial and error. Checked by `slisolver.py` (constraint
  propagation, clue patterns, coloring, edge-pair reasoning, and bounded
  suppositions); the minimal prefix of a random clue ordering is found by binary
  search, and the best of several random orderings wins.

Almost all the run time is Phase B. See `docs/edge-pair-constraints.md` for the
newest family of solver rules and what it bought.

Cost tracks face composition as much as size, which is the surprise worth
remembering: the 72-edge truncated cuboctahedron once generated ~17x faster than
the 90-edge truncated dodecahedron, whose 20 triangles admit only clues 0-3 and so
give propagation less to work with. An all-triangle solid is the hard case, not a
big one (see the difficulty discussion in `ideas/TODOs.md`).

`slisolver.py` is the solver both phases lean on. The pytest suite under
`util/tests/` covers it, the region coloring and clue-minimization workflow in
`genSliPuzzles.py`, the shared topology helpers, the catalogue report's staleness
guard, and a `slow`-marked sweep that re-proves every puzzle in `data/` unique.

`util/about-scripts.md` groups every script in `util/` by what it is for.

## Running it

Two ways:

- **Headless with a timeout** (good for testing; no GUI windows):

  ```
  util/run_gen.py data/myGrid.json [numPuzzles] [timeoutSeconds]
  ```

  Defaults: 1 puzzle, 60-second timeout (exit status 124 on timeout, like
  GNU `timeout`). It runs the generator under its own interpreter, so the two
  can't end up on different Pythons.

- **Directly** (opens the interactive matplotlib 3D view of the mesh):

  ```
  util/genSliPuzzles.py data/myGrid.json [numPuzzles]
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
util/fill_puzzles.py --force dtC              # regenerate one that has some
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

## Rebuilding the catalogue

The app's polyhedron/puzzle pickers can't scan `data/` at runtime (a static
site can't list a directory over HTTP); they read `data/grids.json`. After
adding, removing, or regenerating grid or puzzle files, rebuild it:

```
util/build_catalogue.py
```

This scans `data/`, pairs each grid file with its `-puzzles.json`, counts
faces/edges/puzzles, and writes the catalogue sorted by size (edges, then
faces) — the order the picker presents, intended eventually as the player's
progression order. A new grid won't appear in the picker until this has run.

`util/catalogue_report.py` then prints what `data/` holds: a line per grid with
its counts, puzzles, display puzzles and categories, plus totals, and a note on
any grid with no puzzles or (if it's big enough for the title screen) no display
puzzle. It takes grid names to report on just those, and warns if the catalogue is
older than the data files it summarizes, since its puzzle counts come from the
catalogue rather than from the puzzle files.

`--puzzles` switches to the per-puzzle view, and this is the one to run after
generating and before committing: face census, the clue values the puzzles use,
clue density, the loop length against the most this solid could have, and the
largest connected patch of faces the loop never touches. That last column is the
one that catches a dull puzzle — a big patch is a field of 0 clues with nothing to
do in it. It is how the old repair-based colorer was caught leaving 44–66 of
`dbD`'s 120 faces untouched — a whole dead hemisphere — while every other grid
managed 0–2. Since the rewrite no grid exceeds 6, and `dbD` itself is down to 4.

## Judging whether a generator change helped

`util/sweep_grids.py` generates one puzzle for every grid and reports how good it
is, writing nothing: time taken, loop length against the ceiling (the vertex
count, since the loop is a simple cycle through vertices), the largest connected
patch of faces the loop never touches, and the clue count — each against the mean
of the puzzles already in `data/`.

This is the regression test for changes to the *generator*, as distinct from the
solver: a change that speeds generation up while making the puzzles duller shows
here and nowhere else. The largest untouched patch is the number to watch, since
it is what a player sees as a dull blank area. The seed is fixed and reported so
two runs are comparable; with a varying seed the per-grid differences are noise.

```
util/sweep_grids.py                      # every grid, 60s each
util/sweep_grids.py --budget 150         # the biggest grids need more
util/sweep_grids.py --seed 7 dbD dtD     # just these, a different draw
```
