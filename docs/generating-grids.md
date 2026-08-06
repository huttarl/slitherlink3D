# Generating grids (polyhedra)

How the `data/<id>.json` grid files are produced. Once a grid exists, see
`docs/generating-puzzles.md` for putting puzzles on it, and
`docs/json-format.md` for the file format.

The Python scripts in `util/` must be run with an interpreter that has the
required packages installed (`compas`, `networkx`, `matplotlib`, and for several
of these `numpy`/`scipy`) — the system default `python3` may not have them. See
"Python utilities" in `docs/project-overview.md`.

There are several sources, in rough order of preference: exact coordinates where
we know them, then a construction from an existing solid, then an interactive
modeller, then randomness.

## genUniformPolyh.py — Platonic and Archimedean solids

For a solid whose exact vertex coordinates are known, this is the best source —
it writes the grid JSON directly, with no OBJ step:

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

## genDual.py — the dual of a grid, and the Catalan solids

The dual of an existing grid, and the way the Catalan solids are made, since each
is the dual of an Archimedean solid:

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

## genGoldberg.py — Goldberg polyhedra

Generates a Goldberg polyhedron — 12 pentagons, the rest hexagons, three faces
at every vertex — from its parameters (m,n):

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

## genPrism.py — prisms and antiprisms

Generates a prism or antiprism, all of whose faces are regular polygons:

```
python3 util/genPrism.py 6 P6 "Hexagonal prism" > data/P6.json
python3 util/genPrism.py --anti 5 A5 "Pentagonal antiprism" > data/A5.json
```

Exact coordinates: two regular n-gons of circumradius 1/(2 sin(π/n)), a unit
apart for a prism, and for an antiprism twisted half a step and set
√(1 − 1/(4cos²(π/2n))) apart, which is what makes the lateral faces unit
squares or equilateral triangles. Every run checks that all edges are the same
length, that each face's corners are equidistant from its center (equal edges
plus equal radii is regularity, for a flat face), that faces are flat, and that
the winding is outward — exiting non-zero otherwise. Standard library only.

Both families are infinite, which is why they're excluded from the Johnson
solids and why the script takes n. Two sizes it declines to be used for: the
square prism is the cube and the triangular antiprism is the octahedron, both
already in `data/` from `genUniformPolyh.py`. (Running it on those anyway is a
useful check — it reproduces them, with a note saying so.)

## polyHédronisme + obj2json.py — anything else

For anything `genUniformPolyh.py` doesn't cover (Johnson solids, exotica),
construct the polyhedron interactively at
http://levskaya.github.io/polyhedronisme/, export it as OBJ, then convert:

```
python3 util/obj2json.py myPolyhedron.obj > data/myGrid.json
```

The grid's `gridId`/`gridName` are derived from the OBJ's group name — the
whole of it, so `g Random sphere B` gives that name and a `RandomsphereB` id.
The converter sanity-checks Euler's formula (F + V = E + 2) and fails
if it doesn't hold. It writes no `categories`, so add the family by hand.

## genRandomPolyh.py — random sphere-like solids

Scatters points on a sphere (randomly with simulated repulsion to spread
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
  neighbors, so there are *no* triangles at all and n is the FACE count
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
which can afford it: there the relaxation only spreads the seed *centers*,
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

## Checking a grid afterwards

`util/grid_quality.py` reports the things that make a solid awkward to look at
or play on: shortest/median/longest edge, the sharpest corner of any face, the
range of face inscribed radii (which is the range of clue digit sizes), how far
faces stray from flat, the vertex degrees, and whether every face is wound
outward.
