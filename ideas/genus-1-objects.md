# Grids with a hole in them (genus ≥ 1)

Notes from looking into whether a torus would work as a grid. Not started; this
is what we'd be signing up for if we did.

The capsid and the nanotube broke the "every grid is a closed sphere-like solid"
assumption, but only along the BOUNDARY axis — they still have genus 0. A torus
is the next axis over, and it breaks something the boundary work didn't touch.


## The thing that decides it: the solver assumes the Jordan curve theorem

`apply_color_rules` in util/slisolver.py says so in its own docstring:

> The loop is a closed curve **on the sphere**, so (Jordan curve theorem) it
> divides the faces into two patches.

and encodes

    an edge is filled     <=>  its two faces are in DIFFERENT patches
    an edge is ruled out  <=>  its two faces are in the SAME patch

On a torus that is false. Genus ≥ 1 is exactly the condition under which a closed
curve can fail to separate the surface: a loop running the long way round the ring
leaves ONE region behind it, not two. So on a torus this rule would derive a
contradiction from a perfectly legal solution, prune it, and let
`solution_is_unique` report "unique" for a puzzle that has other answers.

Nothing else would catch it. Both loop checks are purely edge-based — degree 2 and
connected — and neither asks about separation:

  - `is_valid_loop` (util/slisolver.py)
  - `checkSingleLoop` (js/solutionChecker.js)

So the game would happily ACCEPT one of those other answers from a player. That's
the failure mode: not a crash, just a puzzle that quietly isn't the puzzle we
proved.

`genSliPuzzles` itself is fine either way. It paints two regions and takes the
boundary, so it can only ever PRODUCE separating loops — it would simply never
offer the exotic ones. It's the uniqueness proof that has to know they exist.

**Fix:** gate `apply_color_rules` off for genus > 0. It's one of the stronger
deductions, so the cost is slower solving, i.e. slower puzzle generation on
exactly the grids that are already the biggest.


## Two smaller things that would break

**"The solid encloses the origin."** Two places orient a face normal by comparing
it against the direction from the solid's center:

  - `wound_outward`, util/grid_checks.py
  - the facePlanes loop in js/interaction.js (`if (normal.dot(centroid) < 0)`)

A torus's inner-rim faces have outward normals pointing TOWARD the axis, so both
would judge them inward. `grid_quality` would report every inner face as wrongly
wound, and `facesTowardCamera` would invert for exactly the faces we most need to
be able to pick. Winding is validated independently, so interaction.js could just
trust it instead of centroid-correcting. `facesTowardCamera` already carries a
comment saying it assumes convexity and would need dropping otherwise.

**Euler.** `wanted_euler = 2 - rims` in util/grid_quality.py is genus-blind. The
general form is χ = 2 − 2·genus − rims, so a closed torus wants 0, not 2. Would
need a `genus` field in the grid JSON, alongside `closed`.


## What each surface would actually add

A warped plane adds nothing to the PUZZLE — a warped disk is topologically
identical to flat Slitherlink. The properties that change the puzzle are boundary,
genus, and orientability.

| Surface                        | χ | rims | every loop separates? | new work |
|--------------------------------|---|------|-----------------------|----------|
| sphere-like (all closed solids)| 2 | 0    | yes                   | —        |
| disk (capsid with portal)      | 1 | 1    | yes                   | done     |
| cylinder (nanotube)            | 0 | 2    | yes                   | done     |
| torus                          | 0 | 0    | **no**                | solver, normals, Euler |
| Möbius band                    | 0 | 1    | **no**                | all that, plus winding is undefined |

Note the cylinder and the torus share χ = 0, which is why counting rims separately
matters — grid_quality already does.


## Candidates, if we ever do this

**Carbon nanotorus** — the one to build first. Bend genNanotube's rolled lattice
into a ring (two wrap directions instead of one), so most of that machinery
carries over. It's a real object in the chemistry literature, so it belongs in the
existing fullerene/nanotube categories with a real link, and being made of
hexagons it reads as a polyhedron rather than a subdivided donut. Keep the
major/minor radius ratio around 3 so the hole is wide enough to see and reach
through — that makes reachability a parameter rather than a hope.

**Szilassi polyhedron** — 7 hexagonal faces, every pair of them adjacent,
toroidal: the realization of the 7-color theorem on a torus, and a lovely "About
this solid" story. Its dual, the **Császár polyhedron** (7 vertices, 21 edges, 14
triangles, every pair of vertices joined) is the same curiosity from the other
side. Both are far too small to play — 7 clues — so display-only.

**Stewart toroids** — toroidal polyhedra built from regular faces, e.g. rings of
antiprisms or cupolas. Answers the "not just a warped plane" objection by
construction.

**Möbius band** — the biggest conceptual leap, and the one place where "which side
is out" stops having an answer at all. `wound_outward` isn't merely wrong there,
it's meaningless, so that check would have to be skipped rather than fixed. Worth
doing after a torus, not before.

**Skip:** Klein bottle and the projective plane (Boy's surface, Roman surface).
Both self-intersect in any 3D embedding, which wrecks picking and makes the
surface unreadable.

**Probably skip:** hyperboloid of one sheet / catenoid. Handsome, and its two
rulings give it a natural edge structure, but it's topologically a cylinder — the
nanotube again, in a nicer coat.
