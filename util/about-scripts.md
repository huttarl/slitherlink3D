# Scripts (in util/)

## Shared library
- grid_topology — edges, face adjacency, connected groups, and the puzzle
  measures (loop length, untouched patches). Uses the standard library only, working on the
  raw JSON, so the stdlib-only reporting scripts can use it too. Imported by
  catalogue_report, grid_quality, sweep_grids and genSliPuzzles.
- grid_checks — the geometric checks a generated solid must pass before being
  written: Euler's formula, face census, vertex degrees, equal edges and radii,
  flat faces, a closed and outward-wound surface, regular faces, congruent faces.
  Each returns a list of problems, so a generator composes the ones it needs and
  keeps its own reporting. Also the shared face geometry (normals, bow, angles,
  inscribed radius). Uses the standard library only, so genPrism still needs nothing
  installed. Imported by all four coordinate generators and grid_quality.
- json_format — readable JSON for the data files: one line per vertex, face and
  clue list.
- polyhedron_shape — shaping a solid whose topological structure is settled but whose shape is
  not, without changing which faces meet: Hart's canonical form, or regular faces of
  one edge length. Needs numpy, unlike the three above.

## Grid generators
Each writes one grid to stdout, or into data/ when asked for a whole family. The
first six verify the result through grid_checks before writing it.
- genUniformPolyh — the Platonic and Archimedean solids, from exact coordinates.
- genGoldberg — a Goldberg polyhedron GP(m,n): 12 pentagons and hexagons. With
  --geodesic, its dual GD(m,n) instead: all triangles, on the sphere.
- genFullerene — a fullerene cage of 12 pentagons and hexagons, for the ones that
  aren't Goldberg polyhedra: built as the dual of a triangulation, then canonicalized.
- genPrism — an n-prism or n-antiprism, all faces regular.
- genDual — the dual of an existing grid, which is how the Catalan solids are made.
- genZonohedron — a zonohedron from a star of generating vectors, faces exactly
  parallelogram.
- genZonish — a seed solid expanded by zones taken from its own symmetry, after
  Hart's zonish polyhedra.
- genRandomPolyh — invented sphere-like solids, from repelled random points.
- obj2json — converts Wavefront OBJ format (such as from polyHedronisme) to our JSON format.

## Solver & puzzle generator
- slisolver — decides whether a clue set has exactly one solution, and whether
  deduction alone can find it. The engine both puzzle-generation phases lean on.
- genSliPuzzles — the puzzle generator: paint a region for the solution loop, then
  whittle the clues to a minimal deductively-solvable set.
- genLoosePuzzle — a valid puzzle without the uniqueness proof, for when
  genSliPuzzles is too slow or for hand-solving experiments.

## Drivers
- run_gen — runs genSliPuzzles headlessly under a timeout, salvaging what it has.
- fill_puzzles — runs run_gen over many grids, smallest first, unattended.

## Reporting
- catalogue_report — one line per grid, driven by data/grids.json: counts, puzzles,
  categories. --puzzles swaps the categories for quality columns; run before committing.
- grid_quality — the geometry that makes a solid awkward to look at or play on: edge
  lengths, sharpest corners, inscribed radii, bow, vertex degrees, winding.
- sweep_grids — generates a throwaway puzzle for every grid and scores it against
  what's stored. The regression test for changes to the generator.

## Plumbing
- build_catalogue — writes data/grids.json, the manifest the app reads because it
  can't list data/ over HTTP. Re-run after adding or removing any data file.
- serve — a local dev server like http.server, but with no-cache revalidation so
  an edit always shows up on reload.
