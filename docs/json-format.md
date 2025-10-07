JSON polyhedron (grid) format

A JSON object containing the following properties:
- "gridId": string, a unique identifier for the polyhedron grid (mesh). E.g. "dodecahedron"
  - This ID will be used to ensure that puzzles are played on compatible meshes.
- "gridName": string, a human-readable name for the mesh. E.g. "Dodecahedron"
- "recipe": string (optional), Conway's notation for the polyhedron. E.g. "aC". (This can be used
   in a link to a polyhedron construction site, e.g. https://levskaya.github.io/polyhedronisme/?recipe=aC)
- "categories": an array of strings, human-readable names for the categories that the polyhedron
  belongs to. E.g. ["Platonic solid", "zonohedron"]
- "vertices": array of 3-number arrays. Each sub-array is a vertex, and each number is
    a coordinate (X, Y, Z). E.g. [ [0, 0, 1], [-0.3, 0.577, 0.745], ...]
- "faces": array of arrays of numbers. Each sub-array is a face, and each number is a zero-based
  index into the vertices array. E.g. [[0, 1, 2], [10, 11, 17, 19], [0, 2, 3], ...]
- Validation:
  - The arrays for "vertices" and "faces" must be non-empty. There must be at least 4
    vertices and 4 faces.
- Example:
```JSON
  {
    "gridId": "T",
    "gridName": "Tetrahedron",
    "categories": ["Platonic solid", "deltahedron"],
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
      same order as in the "faces" array. -1 means no clue shown for this face.
    - "solution" property: an array of zero-based vertex indices, corresponding to the order in the
      vertices list, and tracing out the solution loop. We don't repeat the first vertex at the end.
- Validation:
  - the length of a "clues" list must be <= the number of faces in the associated mesh
  - the value of each clue must be in the range 0..n-1, where n is the number of edges that the corresponding face has
  - the length of a "solution" list must be <= the number of vertices
  - a "solution" list must not contain any duplicates
  - adjacent vertices in the "solution" list (including the first and last)
    must appear adjacent in one or more faces
- Example:
```JSON
  {
    "gridId": "T",
    "puzzles": [ { "clues": [3, 1, -1, -1], "solution": [1, 2, 3] } ]
  }
```