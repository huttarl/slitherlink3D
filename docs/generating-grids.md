# Generating grids (polyhedra)

How the `data/<id>.json` grid files are produced. Once a grid exists, see
`docs/generating-puzzles.md` for putting puzzles on it, and
`docs/json-format.md` for the file format.

Run these scripts directly — `util/genPrism.py 6 ...`, not `python3
util/genPrism.py 6 ...`. Every one of them asks for plain `python3`, so it is your
environment that decides which Python they get, and it must be one carrying
`numpy`, `scipy` and `matplotlib` (see "Python utilities" in
`docs/project-overview.md`). If it isn't, the failure is a bare
`ModuleNotFoundError` that says nothing about why. In `util/`, a shebang also means
the file is meant to be run: the shared libraries (`grid_topology.py`,
`grid_checks.py`, `slisolver.py`) have none.

There are several sources, in rough order of preference: exact coordinates where
we know them, then a construction from an existing solid, then an interactive
modeller, then randomness.

Every generator that computes coordinates ends by verifying what it built and
refusing to write a solid that fails, and they share those checks through
`util/grid_checks.py`: Euler's formula, the face census, vertex degrees, equal
edge lengths and vertex radii, flat faces, a closed and consistently outward-wound
surface, regular faces, congruent faces. Each generator composes the checks that
apply to it — uniformity for the Platonic and Archimedean solids, congruence for
the Catalan ones, regularity for the prisms — and sets its own tolerances, since
what counts as flat differs between exact coordinates and coordinates that came
back rounded from an OBJ file.

## genUniformPolyh.py — Platonic and Archimedean solids

For a solid whose exact vertex coordinates are known, this is the best source —
it writes the grid JSON directly, with no OBJ step:

```
util/genUniformPolyh.py            # list the solids it knows
util/genUniformPolyh.py tO         # write data/tO.json
util/genUniformPolyh.py --all      # all of them
util/genUniformPolyh.py tO --check # verify without writing
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
`data/tI.json` and `data/sD.json` came through `obj2json.py` when it rounded to 3
decimals, so their duals' faces agree only to about a quarter of a degree rather
than exactly. Harmless, but it is why the congruence tolerances aren't tighter.
The converter writes 6 decimals now, so a model imported today is a thousand times
closer; re-converting those two would tighten their duals in turn.

## genGoldberg.py — Goldberg polyhedra

Generates a Goldberg polyhedron — 12 pentagons, the rest hexagons, three faces
at every vertex — from its parameters (m,n):

```
util/genGoldberg.py 1 2 gp12 "Goldberg GP(1,2)" > data/gp12.json
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
util/genPrism.py 6 P6 "Hexagonal prism" > data/P6.json
util/genPrism.py --anti 5 A5 "Pentagonal antiprism" > data/A5.json
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
util/obj2json.py myPolyhedron.obj > data/myGrid.json
```

The grid's `gridId`/`gridName` are derived from the OBJ's group name — the
whole of it, so `g Random sphere B` gives that name and a `RandomsphereB` id.
The converter sanity-checks Euler's formula (F + V = E + 2) and fails
if it doesn't hold.

Give the metadata on the command line rather than patching the result, so that
re-converting the same OBJ reproduces the same grid file:

```
util/obj2json.py data-scratch/J84.obj --id=J84 --name="Snub disphenoid (J84)" \
    --categories="Johnson solid,deltahedron" \
    "--source=https://levskaya.github.io/polyhedronisme/?recipe=J84" > data/J84.json
```

`--name` earns its keep here because polyHédronisme's group line is the recipe
(`J84`), which is an id and not a name. Quote the `--source` value: the `?` in the
URL is a shell glob otherwise. `--source` records where the coordinates came from,
which for an imported model is what `_comment` records for a generated one.

## genRandomPolyh.py — random sphere-like solids

Scatters points on a sphere (randomly with simulated repulsion to spread
them evenly, or via golden spiral with `--spiral`), takes the convex hull,
then merges nearly-coplanar adjacent triangles into quads. The OBJ it writes
then goes through `obj2json.py` as above:

```
util/genRandomPolyh.py 20 --quiet --name "Random sphere B" --out /tmp/b.obj
util/obj2json.py /tmp/b.obj --categories="Miscellaneous,random" > data/randB.json
```

The `random` category is what files it with the other random solids in the
picker (see `MISCELLANEOUS_GROUPS` in `js/catalogue.js`). `obj2json.py` adds no
categories of its own, so without it the solid would land under "Others".

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

## genSymmetric.py — random solids with tetrahedral or octahedral symmetry

(Open questions and next steps — other symmetry groups, vertices of higher
degree — are in `ideas/symmetric-solids.md`.)

`genRandomPolyh.py --dual` can give a varied face census, but the result is an
asymmetric blob, while most of the collection's appeal is symmetry. This script
gets both, by making the randomness symmetric:

```
util/genSymmetric.py 6 --relax=0.25 --seed=2
util/genSymmetric.py 6 --relax=0.25 --seed=1 --vertex-axes --edge-axes
```

It picks a few random points and lets the 12 rotations of the tetrahedral group
carry each one to 12 places. Each such set is an **orbit**. The hull of all the
points is a triangulation with the same symmetry, and its polar dual
(`genGoldberg.polar_dual`, so every face is exactly flat) is the solid.

**Every face in an orbit is congruent to the rest**, since a symmetry of the
whole solid carries any one to any other. So the census comes in blocks of 12,
and Euler's formula — summing (6 − sides) over the faces always gives 12 when
three faces meet at every vertex — constrains the blocks: with random orbits
alone, the orbits' own (6 − sides) must sum to 1. The `--vertex-axes`,
`--face-axes` and `--edge-axes` options add points on the symmetry axes, whose
faces are forced to a multiple of 3 sides (vertex and face axes — nonagons do
turn up) or of 2 (edge axes), and which take a share of that 12.

**Why tetrahedral**, rather than a bigger group: with congruent faces per orbit,
higher symmetry means fewer orbits and so less variety. In 60–100 faces the
tetrahedral group (order 12) leaves room for 5–8 independent orbits, the
octahedral (24) for 2–4, and the icosahedral (60) for one, where Euler all but
forces 12 pentagons and 60 hexagons, i.e. a Goldberg solid.
`--group=octahedral` exists anyway, for the one thing the tetrahedral group
can't do: vertices where four faces meet (see below).

Two things the construction must avoid, both of which break the symmetry:

- **Nearly coplanar points.** Their triangles' poles, which are the dual's
  vertices, nearly coincide. A draw whose hull has any is rejected and
  redrawn. *Exactly* coplanar points are a different matter: scipy's hull
  splits the flat facet they make into triangles arbitrarily, so they are
  merged back into one facet, whose pole is then one dual vertex with as many
  faces as the facet has corners. Under the tetrahedral group that never
  happens; under the octahedral group it's the point.
- **Drift during relaxation.** Only one representative per orbit moves, pushed
  by every other point including its own images, and the images are recomputed
  from it after every step. Moving the whole set would stay symmetric only in
  exact arithmetic. The axis points never move.

The output is checked before it is written: that every rotation carries the
triangulation onto itself, then the usual Euler, flatness, closed-surface,
winding and vertex-degree checks. It is also tested for a mirror or an
inversion, and gets the `chiral` category when it has neither, which is
normal: random orbits are chiral like the snub cube.

**Short edges.** Two hull triangles that are nearly coplanar give poles, and
so dual vertices, nearly on top of each other, and symmetric point sets make
such near-coincidences common. Unseparated, even an evenly spread relax-0.5 draw
had an edge 3% of the median. `genRandomPolyh.py`'s `separate_short_edges`
solves this for its solids by nudging the dual's vertices one at a time and
re-flattening the faces, which would break the symmetry here, and leaves the
faces only nearly flat anyway.

So this script's `separate_short_edges` works on the other side of the dual: it
moves the **primal** points, deepening the fold between each nearly coplanar
pair of triangles, by gradient descent on the total shortfall below `--min-edge`
(default 0.4 of the median, as in `genRandomPolyh.py`). Three choices in it,
each forced by something that went wrong without it:

- **One representative per orbit moves**, and the group is reapplied, as in the
  relaxation — so the symmetry stays exact. And since the polar dual of any
  point set is flat, **the faces stay exactly flat** too (bow about 5e-10).
- **The triangulation is held fixed.** A nearly coplanar pair can also be
  resolved by flipping to the other diagonal, and left free to, the search did
  exactly that: two orbits of squares and octagons turned into hexagons, because
  a flip changes vertex degrees and so face sizes. That spends the very variety
  the draw produced, so a step is kept only if its hull has the same triangles.
- **The target tracks the current median.** Separating the short edges
  lengthens the typical edge too — by 22% on one draw — so a target fixed at the
  start was met, yet missed as `grid_quality.py` measures it.

Measured over six draws of 6 orbits (72 faces, 82 with axis points), with
`grid_quality.py`. The census is unchanged by separation in every case:

| relax | census | shortest edge, before → after | sharpest corner | flattest edge |
|---|---|---|---|---|
| 0 | 36×5, 12×6, 24×7 | 36% → 42% | 55° → 52° | 10° → 10° |
| 0 | 24×4, 12×5, 12×6, 24×8 | 2% → **33%** | 58° → 60° | 9° → 9° |
| 0.25 | 12×5, 60×6 | 43% (already past) | 65° | 13° |
| 0.25 | 24×5, 36×6, 12×7 | 21% → 43% | 58° → 69° | 10° → 8° |
| 0.25, both axis options | 12×4, 12×5, 40×6, 12×7, 6×8 | 9% → 42% | 67° → 61° | 13° → 11° |
| 0.5 | 12×5, 60×6 | 3% → 49% | 75° → 85° | 17° → 16° |

Corners and edge angles are healthy throughout — better than an unrelaxed
`genRandomPolyh.py --dual` (31° and 1.6°). One draw stops short: the one with 24
squares beside 24 octagons, which gets from 2% to 33% and then finds no further
step that keeps its triangulation. Whether such an extreme census simply can't
have regular edges, or that draw is caught in a local minimum, isn't settled.
The script says so when it happens ("SHORT OF THE TARGET; try another seed"),
and `--min-edge=0` turns the separation off.

**Regular faces (`--regularize`).** Unregularized, the faces are lopsided —
sides differing 3 to 8.6 times within one face — and, worse for play, have
nearly straight corners, 151–170°. A corner near 180° hides a side, so a
heptagon reads as a hexagon and the player has to count edges. `--regularize`
moves the points again, by the same symmetric descent with the same
triangulation, toward faces with equal sides and equal angles.

It cannot get all the way, and the reason is worth knowing before trying to
make it. A flat face's angles always total (sides − 2) × 180°, and at each
vertex the three faces' angles must total under 360°. If the faces there were
regular, the angle left over would be 360 × (1/a + 1/b + 1/c) − 180°, which
is 0 for three hexagons and negative for a heptagon between two hexagons. Where
it's negative, regularity is impossible: that corner is squeezed, and since the
face's total is fixed, its excess goes into the face's other corners — which
is exactly how straight corners arise. It depends only on which faces touch
which, so it can be read off a draw before any geometry. A scan of 1,524 varied
draws found **only two** with no corner over budget, both pentagons, hexagons
and heptagons. Every draw with squares, octagons or nonagons had at least 12.
Random orbits simply don't ring big faces with small ones, which is how the
Archimedean solids make big faces regular.

Three things in the objective, each from something that went wrong without it:

- A **penalty on corners straighter than 145°** (a regular nonagon's are
  140°). Minimizing the average irregularity alone left the straightest corner
  of the widest candidate at 160° and made its nonagons worse, 147° → 155°,
  because the excess only moved around.
- The **minimum edge** is held, as in separation.
- **No two neighboring faces flatter than 8°**, since pushing corners toward a
  360° total is pushing the solid toward flat. On a polar dual this is cheap:
  each face lies in the plane x·v = 1, so its normal is its own point v, and the
  angle between two neighboring faces *is* the angle between their points.

It's **off by default** so that commands written before it existed still make
the same solid, and gets `reg` in the default id.

Measured on ten candidates:

| solid | census | straightest corner | sides within a face | clue-size spread |
|---|---|---|---|---|
| symT6_v_r25_reg_s1 | 24×5, 40×6, 12×7 | 152° → 138° | ×4.6 → ×1.7 | ×1.4 → ×2.1 |
| symT5_vf_r50_reg_s8 | 24×5, 32×6, 12×7 | 160° → 141° | ×6.4 → ×1.7 | ×1.3 |
| symT6_r25_reg_s3 | 24×5, 36×6, 12×7 | 155° → 141° | ×3.2 → ×1.5 | ×1.5 → ×1.4 |
| symT8_r25_reg_s1 | 36×5, 36×6, 24×7 | 156° → 145° | ×4.8 → ×2.0 | ×1.6 → ×1.7 |
| symT7_r25_reg_s1 | 12×4, 24×5, 12×6, 36×7 | 158° → 145° | ×5.6 → ×3.4 | ×1.5 → ×1.9 |
| symT5_r25_reg_s1 | 36×5, 12×6, 12×8 | 159° → 146° | ×7.3 → ×2.2 | ×1.6 → ×2.5 |
| symT7_r25_reg_s3 | 36×5, 24×6, 24×7 | 157° → 146° | ×3.7 → ×1.5 | ×1.5 → ×1.6 |
| symT6_e_r25_reg_s1 | 12×4, 24×5, 12×6, 24×7, 6×8 | 157° → 147° | ×5.4 → ×3.6 | ×1.6 → ×1.9 |
| symT6_vf_r25_reg_s2 | 12×4, 24×5, 28×6, 12×8, 4×9 | 160° → 149° | ×5.6 → ×3.2 | ×1.7 → ×2.5 |
| symT7_r10_reg_s2 | 12×4, 36×5, 12×6, 12×7, 12×9 | 164° → 153° | ×5.8 → ×4.0 | ×1.9 |

The pattern is the budget's: the more varied the census, the less it
improves. The cost is **clue-size spread**, which grows on the mixed censuses,
because regular faces of different side counts are simply different sizes. And
two different draws (seeds 8 and 34 of the same settings) regularized to exactly
the same solid, metric for metric: once the points are free to move, the
result depends only on which faces touch which.

**Vertices of degree 4 (`--group=octahedral`).**

```
util/genSymmetric.py 3 --group=octahedral --relax=0.25 --seed=9 --regularize
```

Every vertex of a tetrahedral solid has three faces, whatever the options,
because a dual vertex is the pole of one hull facet and has one face per corner
of that facet. Four faces at a vertex need four exactly coplanar points, and
random points are never coplanar four at a time unless the symmetry makes them
so. A point's images about a k-fold axis are always coplanar, but the
tetrahedral group's axes are at most 3-fold, and three points are always
coplanar anyway.

The octahedral group O (the 24 signed permutation matrices of determinant 1)
has 4-fold axes. The hull facet that such an axis passes through must be
carried onto itself by the quarter turn, so it's a square: four images of one
point. So every octahedral draw has six square facets, one at each end of the
three axes, and the solid has six vertices of degree 4. The exception is
`--vertex-axes`, which under O puts points on those very axes: the hull then
has a corner there instead, every facet is a triangle, and every vertex has
degree 3 again.

The axis options take the octahedron's axes under O: `--vertex-axes` 6 points
(4-fold, their faces having a multiple of 4 sides), `--face-axes` 8 (3-fold),
`--edge-axes` 12 (2-fold). Euler's formula still fixes the census's blocks:
summing (6 − sides) gives 12 plus 2 for each vertex of degree 4, so 24 here,
and with 24 faces per orbit, the orbits' own (6 − sides) must again sum to 1.

What the octahedral group needed from the code, which the tetrahedral solids
share without being changed by it:

- **Merged facets** (`hull_facets`). Hull triangles within 1e-9 of one plane are
  merged into one facet. A symmetry-forced square is exact up to rounding,
  near 1e-16, while anything scipy's rounding would merge but this doesn't is
  rejected as nearly coplanar, as before. A merged facet must also be carried
  onto itself by the symmetry, which one merged by accident would not be.
- **A polar dual over the facets** (`facet_dual`). `genGoldberg.polar_dual`
  works from the raw triangles, so it would give a square two poles.
- **Facets, not triangles, held fixed** by separation and regularizing, and
  compared by the symmetry check.

With nothing to merge, `facet_dual` gives exactly what `polar_dual` does, and
the octahedral rotations begin with the tetrahedral ones in their own order.
So every tetrahedral command still makes the same file: `cageA`–`cageG` were
regenerated from their source lines and compared byte for byte.

**What it gives.** A census scan of 40 seeds per setting (2–4 orbits, each axis
option, relax 0 and 0.25) found plenty of variety: triangles through decagons,
and 15-gons once. But the budget of the tetrahedral section applies unchanged,
and there is less room to spend it, with only two to four free orbits. Eighteen
regularized candidates, all with six vertices of degree 4:

| solid | census | straightest corner | sides within a face | shortest edge | flattest |
|---|---|---|---|---|---|
| symO3_r25_reg_s1 | 24×5, 48×6 | 125° | ×1.3 | 95% | 21° |
| symO4_r25_reg_s1 | 24×5, 72×6 | 130° | ×1.5 | 77% | 19° |
| symO3_e_r25_reg_s1 | 24×5, 60×6 | 129° | ×1.6 | 80% | 21° |
| symO2_e_r25_reg_s1 | 12×4, 48×6 | 136° | ×2.0 | 72% | 18° |
| symO3_r25_reg_s9 | 24×4, 24×6, 24×7 | 137° | ×1.8 | 76% | 20° |
| symO3_f_r25_reg_s1 | 48×5, 8×6, 24×7 | 138° | ×1.8 | 67% | 18° |
| symO3_e_r25_reg_s7 | 12×4, 24×5, 24×6, 24×7 | 139° | ×1.9 | 64% | 16° |
| symO2_fe_r25_reg_s1 | 12×4, 24×5, 8×6, 24×7 | 146° | ×2.0 | 58% | 13° |
| symO4_r25_reg_s7 | 24×4, 24×5, 24×6, 24×8 | 147° | ×3.0 | 40% | 14° |
| symO2_fe_r25_reg_s7 | 8×3, 12×4, 24×6, 24×7 | 150° | ×2.9 | 57% | 11° |
| symO3_f_r25_reg_s5 | 8×3, 24×5, 24×6, 24×7 | 150° | ×2.0 | 60% | 10° |
| symO3_f_r25_reg_s21 | 24×4, 24×5, 24×7, 8×9 | 152° | ×4.6 | 42% | 13° |
| symO2_fe_r0_reg_s19 | 24×4, 24×5, 8×6, 12×10 | 161° | ×4.7 | 39% | 11° |
| symO3_e_r0_reg_s8 | 24×4, 24×5, 24×7, 12×8 | 165° | ×6.2 | 39% | 7° |
| symO3_r0_reg_s19 | 24×4, 24×5, 24×8 | 168° | ×13.8 | 39% | 7° |
| symO4_r0_reg_s10 | 24×3, 24×5, 24×6, 24×9 | 178° | ×13.7 | 36% | 1.3° |

(Two more, symO3_r0_reg_s1 and symO3_r25_reg_s2, came out identical to
symO3_r25_reg_s1 metric for metric: the combinatorics decide again.) Six of
these ship as `ocageA`–`ocageF`; `ideas/symmetric-solids.md` says which.

The most common census at relax 0.25, one orbit of pentagons among hexagons,
regularizes almost perfectly and is correspondingly plain. The varied ones
regularize worst, as under T, and the relax-0 draws that gave the widest faces
are unusable. The last row has corners of 7° and 178° and two faces meeting at
1.3°: its separation stopped short of the minimum edge, and regularizing left
its straightest corner at 178°.

**Moving the axis faces (`--face-axes=D`, and likewise for the other two).**
Once everything else is done, this moves the planes of those axis points' faces
to distance D from the center, where regularizing left them at 1. Below 1 it
slices them deeper: they grow, their neighbors are trimmed, and no other face
moves. Each face lies in the plane x·v = 1 of its point v, so this is just the
axis points scaled by 1/D, and the symmetry and flatness stay exact. A distance
that would change which faces meet is refused.

It can only change side lengths. Sliding a plane without tilting it leaves
every edge's direction alone, since an edge runs where two planes meet, so
every corner angle and dihedral angle stays exactly as it was. On the 44-face
small candidate (12 rectangles, 24 pentagons, 8 nonagons on the face axes),
moving the nonagons to 0.92 made the rectangles squares to within 1% and
halved the pentagons' worst side ratio, from ×3.1 to ×1.5. The price was the
clue-size spread, from ×1.5 to ×2.5, as the nonagons grew. At 0.80 a
neighbor's edge vanished, and the move was refused.

## Checking a grid afterwards

`util/grid_quality.py` reports the things that make a solid awkward to look at
or play on: shortest/median/longest edge, the sharpest and the straightest
corner of any face (a corner near 180° hides a side, making the face hard to
count), the worst ratio of a face's longest side to its shortest and of its
largest corner to its smallest, the range of face inscribed radii (which is the range of clue digit sizes), how far
faces stray from flat, the vertex degrees, and whether every face is wound
outward.

How much of each is too much is a judgment, and the lines below are the ones in
use. They are about play first: a face the player can't count, or two faces that
read as one, spoils a board, while most of the rest merely looks less tidy.

| measure | worth a second look past |
|---|---|
| straightest corner | 150°, where a corner starts to hide a side |
| sides within a face | ×3.0 |
| angles within a face | ×3.0 |
| flattest edge | 8°, where two neighboring faces start to read as one |
| sharpest corner | below 55° |
| clue-size spread | **×2.5** |
| shortest edge | below 40% of the median |

Clue-size spread is deliberately the loosest. Clue digits of noticeably
different sizes are fine on the board, and holding the spread tight works
against regular faces: a regular octagon is simply bigger than a regular
pentagon with the same edge, so any mixed census that is regularized widens it.
It used to be judged at ×2.0, which demoted solids for no benefit to play.

The two corner measures answer different questions. The angle ratio says how
irregular a face is, whatever its size: a regular decagon scores ×1.0 with
144° corners, while a triangle of 144°, 18° and 18° scores ×8, although the
straightest corner is the same for both. The straightest corner says whether a
side is hiding, which can happen in a face whose other corners are all alike,
and which the ratio barely notices in a big face. The ratio's line is newer
and less tested. The triakis Catalans (`dtT`, `dtC`, `dtD`) are past it, at ×3.4 to
×3.9, and play well, since their isosceles triangles are all congruent and a
triangle is never hard to count.
