# Scripts (in util/)

## Shared library
- grid_topology — edges, face adjacency, connected groups, and the puzzle
  measures (loop length, untouched patches). Standard library only, working on the
  raw JSON, so the stdlib-only reporting scripts can use it too. Imported by
  catalogue_report, grid_quality, sweep_grids and genSliPuzzles.
- grid_checks — the geometric checks a generated solid must pass before being
  written: Euler's formula, face census, vertex degrees, equal edges and radii,
  flat faces, a closed and outward-wound surface, regular faces, congruent faces.
  Each returns a list of problems, so a generator composes the ones it needs and
  keeps its own reporting. Also the shared face geometry (normals, bow, angles,
  inscribed radius). Standard library only, so genPrism still needs nothing
  installed. Imported by all four coordinate generators and grid_quality.
- json_format — readable JSON for the data files: one line per vertex, face and
  clue list.

## Grid generators
- genUniformPolyh
- genGoldberg
- genPrism
- genDual
- genRandomPolyh
- obj2json

## Solver & puzzle generator
- slisolver
- genSliPuzzles
- genLoosePuzzle

## Drivers
- run_gen
- fill_puzzles

## Reporting
- catalogue_report
- grid_quality
- sweep_grids

## Plumbing
- build_catalogue
- serve
