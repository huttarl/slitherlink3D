JSON polyhedron (grid) format

A JSON object containing the following properties:
- "gridId": string, a unique identifier for the polyhedron grid (mesh). E.g. "dodecahedron"
  - This ID will be used to ensure that puzzles are played on compatible meshes.
- "gridName": string, a human-readable name for the grid. E.g. "Dodecahedron"
- "recipe" (optional): string, Conway's notation for the polyhedron. E.g. "aC". (This can be used
   in a link to a polyhedron construction site, e.g. https://levskaya.github.io/polyhedronisme/?recipe=aC)
- "categories" (optional): an array of strings, human-readable names for the categories that the polyhedron
  belongs to. E.g. ["Platonic solid", "zonohedron"]
  - Exactly one of these should be a *family* — "Platonic solid", "Archimedean solid",
    "Catalan solid", "Johnson solid", "Miscellaneous" — since the polyhedron picker
    groups by family, and a solid can only be filed under one heading.
    The rest are cross-cutting properties: "deltahedron", "quasiregular", "zonohedron",
    "parallelohedron", "chiral", "self-dual", "Goldberg", "prism", "antiprism".
  - Some of those attributes catch a classical solid too, which is the point of their
    being cross-cutting: the cube is a "prism" as well as Platonic, and the octahedron
    an "antiprism".
  - "Miscellaneous" is the catch-all for a solid in none of the classical families:
    the Goldberg polyhedra past GP(1,1), and prisms and antiprisms when we have them.
    It says nothing about the solid — what it actually is comes from its other
    categories, so the chamfered dodecahedron is ["Miscellaneous", "Goldberg"] — and
    it's the one category with no link, there being nothing to read about being
    miscellaneous.
  - Where one category implies another, list only the narrowest: every parallelohedron
    is a zonohedron, so the cube says "parallelohedron" and stops there.
  - Names are kept short — "chiral", not "chiral polyhedron"; "Goldberg", not
    "Goldberg polyhedron" — since the About card has already given the solid's name
    and family by the time these are read. One named after a person keeps its capital. Each is linked
    to an explanation where there's a good one; see js/polyhedronLinks.js.
  - Both conventions are checked by js/tests/catalogue.test.js.
- "vertices": array of 3-number arrays. Each sub-array is a vertex, and each number is
    a coordinate (X, Y, Z). E.g. [ [0, 0, 1], [-0.3, 0.577, 0.745], ...]
- "faces": array of arrays of numbers. Each sub-array is a face, and each number is a zero-based
  index into the vertices array. E.g. [[0, 1, 2], [10, 11, 17, 19], [0, 2, 3], ...]
- Validation:
  - The arrays for "vertices" and "faces" must be non-empty. There must be at least 4
    vertices and 4 faces.
  - Each face must have at least 3 vertices.
- IDs: a vertex's or face's ID, in the running grid and everywhere the app or the
  solver refers to one, is simply its index in these arrays. There is no separate
  ID field, so reordering "vertices" or "faces" renumbers everything and
  invalidates any puzzle file built on the grid.
- File formatting: one line per vertex, per face and per clue list, written that
  way by `util/json_format.py`. The generators all use it, and
  `python3 util/json_format.py data/*.json` reformats existing files in place —
  idempotent, and it refuses to write if the parsed data would change. Neither
  extreme is readable: minified puts a grid on one 1000-character line, while
  `indent=3` gave every coordinate a line of its own (491 lines for three puzzles
  on the truncated icosidodecahedron).
- Example:
```JSON
  {
    "gridId": "T",
    "gridName": "Tetrahedron",
    "categories": ["Platonic solid", "deltahedron"],
    "recipe": "T",
    "vertices": [
      [0.577, 0.577, 0.577], [0.577, -0.577, -0.577],
      [-0.577, 0.577, -0.577], [-0.577, -0.577, 0.577]
    ],
    "faces": [[1, 3, 2], [0, 1, 2], [0, 2, 3], [0, 3, 1]]
  }
```

Puzzles (and their solutions) will appear in a separate JSON file, with the following structure:
- A JSON object with the following properties:
  - a "gridId" (string), which must match the "gridId" property in the grid file.
  - "puzzles": array of objects, each of which represents a puzzle, in which we have:
    - "clues" property: an array of clue numbers, corresponding to the faces in the
      same order as in the "faces" array. -1 means no clue shown for this face. If the number
      of clues is less than the number of faces, the remaining faces will have no clues.
    - "solution" property: an array of zero-based vertex indices, corresponding to the order in the
      vertices list, and tracing out the solution loop. We don't repeat the first vertex at the end.
  - "displayPuzzles": optional array, in exactly the same format as "puzzles".
    These are shown off, not played: the title screen loads one and draws its
    loop on the tumbling solid (see js/titleScreen.js). They are kept out of
    "puzzles" so that nothing a player can select is ever put on show — which is
    also why they must be authentic puzzles (one loop, uniquely solvable): the
    clues are visible beside the loop, and a player may well check them by eye.
    The key is absent, rather than empty, when a grid has none; the title screen
    then shows that grid's clues with no loop. Only the small grids should end up
    without one: the tetrahedron has just one distinct puzzle in total, so there
    is nothing spare to display.
- Validation:
  - the length of a "clues" list must be <= the number of faces in the associated grid
  - the value of each clue must be in the range 0..n-1, where n is the number of edges that the corresponding face has
  - the length of a "solution" list must be <= the number of vertices
  - a "solution" list must not contain any duplicates
  - adjacent vertices in the "solution" list (including the first and last)
    must appear adjacent in one or more faces
  - the same rules apply to each entry of "displayPuzzles"; and if the key is
    present, its array must not be empty
- Example:
```JSON
  {
    "gridId": "T",
    "puzzles": [ { "clues": [3, 1, -1], "solution": [1, 2, 3] } ],
    "displayPuzzles": [ { "clues": [-1, 3, 1], "solution": [0, 1, 2] } ]
  }
```
