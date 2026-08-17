# Penrose-ish grids: the rhombic spirals

Where the `spiral7`–`spiral10` grids came from, and what they are. Written up
because the route to them was not the obvious one — the question was "could a
polyhedron be made from Penrose rhombi?", and the answer turned out to be no, with
something better next door.


## The Penrose rhombi themselves cannot do it

The two Penrose (P3) rhombi are 72°/108° and 36°/144°. They tile the PLANE, which
means their vertex configurations sum to exactly 360°. A convex polyhedron needs
every vertex to sum to LESS than 360° — that deficit is what curvature is. So tiles
designed to close up flat cannot close up round. Not a difficulty; a
contradiction.

(You can still build isolated solids from a single Penrose rhombus — six of the
72° ones make a perfectly good rhombohedron — but the tiling's vertex figures
cannot be carried onto a closed surface.)

**And the Penrose rhombi are literally the flat limit of the solid we want.** Take
five unit vectors on a cone of half-angle θ about a five-fold axis and build the
zonohedron. Faces come one per pair of generators, so there are two rhombus
shapes — neighbours and next-neighbours. Vary θ:

| θ | k=1 rhombus | k=2 rhombus | |
|-------|--------------|--------------|---|
| 50° | 53.5 / 126.5 | 93.5 / 86.5 | |
| **63.43°** | **63.43 / 116.57** | **116.56 / 63.44** | golden rhombi — the rhombic icosahedron, `zico5` |
| 75° | 69.2 / 110.8 | 133.5 / 46.5 | |
| 85° | 71.7 / 108.3 | 142.7 / 37.3 | |
| **90°** | **72 / 108** | **144 / 36** | **FLAT — exactly the Penrose rhombi** |

So the parameter interpolates between a solid we already ship and the Penrose
tiling. Push the star off flat by any amount and the angles open up; at one
particular angle they become golden rhombi (63.435°, diagonals in ratio φ).


## What DOES transfer

"Aperiodic" means "no translational symmetry", a property of an infinite tiling. A
closed surface has no translations at all, so the literal property is vacuous on a
polyhedron and the word does no work there. Three things do transfer:

1. **The forbidden symmetry.** A periodic tiling can only have 2-, 3-, 4- or 6-fold
   rotation; 5-fold is banned by the crystallographic restriction. That is why
   Penrose tilings and quasicrystals were startling. Any icosahedral solid has it.
2. **The tiles.** The 3D counterparts of the Penrose rhombi are the two golden
   rhombohedra, and ten of those assemble into the rhombic triacontahedron
   (`daD`).
3. **The construction, which is the tight one.** A zonohedron from n generators is
   the shadow of the n-cube — its faces are the projected 2-faces. Penrose tilings
   are built the same way: project the 2-faces of a slab of the 5-dimensional cubic
   lattice onto a plane. Same machine, one dimension up.

So the rhombic zonohedra are the polyhedral members of the family Penrose tilings
belong to. That was the insight worth recording: zonohedra are the way in.


## Why the classical rhombic zonohedra don't LOOK aperiodic

Because their generators are symmetric. A symmetry group collapses the pairwise
angles into a few classes, and a rhombus is pinned down by its acute angle, so few
angle classes means few face shapes. Measured off the shipped grid files:

| grid | faces | sharpest | widest | shapes | faces per shape |
|----------|-------|----------|--------|--------|-----------------|
| `daC` rhombic dodecahedron | 12 | 70.5 | 70.5 | **1** | 12.0 |
| `zico5` rhombic icosahedron | 20 | 63.4 | 63.4 | **1** | 20.0 |
| `daD` rhombic triacontahedron | 30 | 63.4 | 63.4 | **1** | 30.0 |
| `jtI` rhombic enneacontahedron | 90 | 41.8 | 70.5 | **2** | 45.0 |
| `spiral7` | 42 | 45.0 | 87.1 | **13** | 3.2 |
| `spiral8` | 56 | 42.1 | 89.7 | **13** | 4.3 |
| `spiral9` | 72 | 37.2 | 88.3 | **11** | 6.5 |
| `spiral10` | 90 | 34.6 | 89.3 | **9** | 10.0 |

`daD`'s six generators are all 63.43° apart, so all thirty faces are the same
golden rhombus. That reads as crystalline because it is. The sharpest comparison is
`spiral10` against `jtI`: the same 90 rhombic faces, 9 shapes against 2.

**How the spirals differ from the zonohedra already in data/, in one line:** same
construction, same all-rhombic faces, same n-zones-of-parallel-edges structure —
but an ASYMMETRIC star, so the face shapes don't collapse into classes. Every
other star in `genZonohedron.py` is "the diagonals of" some symmetric solid; these
are not the diagonals of anything.


## The star: a golden-angle spiral

See `golden_spiral_star` in `util/genZonohedron.py`. Equal-area steps in z so the
directions don't bunch toward the pole, and an azimuth step of 2π/φ² — an
irrational fraction of a turn, so no two generators are ever related by a rotation.
(Same reasoning as the tumble's irrational rate ratio in `SceneManager.js`: an
irrational step never comes back into phase.) A HEMISPHERE, not a sphere, since a
vector and its negative are one zone.

Result: no rotational symmetry at all, only the central inversion every zonohedron
has.

**Repulsion was tried and rejected**, which is the counter-intuitive part. Pushing
the directions apart gives a better sharpest corner at n=9 (42.3° vs 37.2°) but
CLUMPS the angles — five faces at 51°, seven near 88°, only 7 distinct shapes
against the spiral's 11. Evenness tends toward symmetry, which is the thing being
avoided. So the star is deliberately not optimized.

**Both numbers improve as n falls**, which was also unexpected: fewer lines through
one origin spread further apart, so corners are blunter, and the angles that remain
are better separated, so more pairs give visually distinct rhombi. n=7 gets 62% of
its pairs distinct; n=10 only 20%. The pull the other way is just that a bigger
grid is a bigger puzzle.


## Caveats

**Central symmetry is unavoidable.** Every zonohedron is centrally symmetric, so
faces come in antipodal congruent pairs: n(n−1) faces means n(n−1)/2 distinct
shapes, each used exactly twice. That is a real ceiling on how unrepeating these
can look, and it cannot be engineered away within this construction.

**Sharpness is the limiting resource.** A slim rhombus has little room for its clue
digit (`clueRenderer` sizes digits to the inscribed circle). `spiral10` at 34.6° is
the sharpest grid in data/; `jtI` at 41.8° was the previous worst.


## Puzzle quality

All four generate quickly and well — 25s to 70s for 3 puzzles plus a display
puzzle. The `patch` column (untouched patches) and `loop/max` are the measures that
matter, and all four beat `jtI`:

| grid | clue density | loop/max | patches |
|----------|--------------|-------------|---------|
| `spiral7` | 50% | 36–40/44 | 0–2 |
| `spiral8` | 52–61% | 48–52/58 | 1–2 |
| `spiral9` | 49–62% | 60–66/74 | 2–3 |
| `spiral10` | 54–59% | 74–80/92 | 1–3 |
| `jtI` | 47–59% | 60–64/92 | 4–8 |

A WARNING worth keeping, since it cost time: the first puzzles for these came from
`genLoosePuzzle`, which produced loops using about a third of the available length
and 15 to 39 untouched patches — big dead areas a player notices immediately, and
one puzzle that genuinely had two solutions and failed
`test_puzzle_solution_is_unique`. `genLoosePuzzle` cannot balance the two colour
regions, which is exactly what forces a long loop. Use `fill_puzzles.py` (which
writes through `run_gen` into a temp file) rather than `run_gen` directly — the
latter is a smoke-test wrapper and saves nothing.


## Untried

- **n=6**: 30 faces with 11 shapes at 48.7° sharpest — the same face count as
  `daD` with the opposite character. Measured but not built.
- **Unequal generator lengths**: gives general parallelograms rather than rhombi.
  Further from Penrose, but opens up the shape space.
- **A non-centrally-symmetric all-rhombic solid**, if such a thing exists outside
  the zonohedra. Not investigated.
