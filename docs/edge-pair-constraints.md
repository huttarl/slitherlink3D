# Edge-pair constraints

Design notes for teaching the solver to reason about *pairs* of edges, not only
about single edges.

**Status.** Built and unit-tested in `util/slisolver.py`: the data model
(`ParityRelation`, extracted from `FaceColoring`, which now subclasses it, plus
`EdgePairing` and `EdgeClauses`) and the emitters (`emit_vertex_pairs`,
`emit_face_pairs`, driven by `apply_pair_rules`, which runs in
`propagate_constraints` after coloring stalls). Still to come: the substitution
queries described below, which rewrite the clue arithmetic rather than only
propagating. Tracked in `ideas/TODOs.md`.

Two things measured once the emitters were working, both worth recording:

- **It fires where the doc predicted and nowhere else.** From positions where the
  older families had stalled, `apply_pair_rules` deduced something in 156 of 200
  cases on the pentakis dodecahedron (`dtI`) and 127 of 200 on the tetrakis
  hexahedron (`dtO`) — triangle-faced, high-degree solids — and in **0 of 200** on
  the dodecahedron. That is the locality and degree argument below, confirmed: a
  3-valent solid with pentagonal faces gives the emitters almost nothing to say,
  because `f == 0, u == 3` yields no pair constraint at all and Rules A and B
  already cover the rest.
- **It pays for itself, modestly.** Timing `solution_is_unique` over the stored
  puzzles with the pass enabled vs stubbed out, in one process: `sD` 0.39s vs
  0.56s, `bD` 1.63s vs 1.93s, `gp12` 25.06s vs 26.98s, and no measurable
  difference on the small ones. Never slower, roughly 7–30% faster on the large
  solids, and the set of puzzles proven unique was identical — as it must be,
  since a sound rule cannot change the solution set, only how fast we reach it.

The four relations that come up constantly when solving these puzzles by hand:

| relation | logic | meaning |
|---|---|---|
| both or neither | `a ↔ b` | the two edges agree |
| exactly one | `a ⊕ b` | the two edges disagree |
| at least one | `a ∨ b` | not both empty |
| at most one | `¬a ∨ ¬b` | not both filled |

They are two different mathematical animals, and that split drives the whole
design: the first two are *equivalences with a sign*, the last two are *clauses*.

## We already have half of this

`slisolver.py`'s `FaceColoring` is a union-find over faces where each face
carries a parity bit, answering "are these two faces the same colour?" without
ever deciding which colour either one is. "Both or neither" and "exactly one" are
that same question asked about edges. So the first structure to write is the one
we already debugged, pointed at different variables — extract the parity
union-find into its own class and instantiate it twice.

There is a second, prettier connection. An edge is filled exactly when its two
adjacent faces differ in colour, so writing `a` for face colours as bits, an edge
between faces A and B *is* the parity `A ⊕ B`. For two edges that **share a
face** — say `e` between A and B, `f` between B and C:

    e = A ⊕ B,  f = B ⊕ C
    e = f  ⟺  A ⊕ B = B ⊕ C  ⟺  A = C

So for edges sharing a face, "both or neither" means the two *outer* faces are the
same colour, and "exactly one" means they differ. Two consequences:

- Those pairs are already expressible in `FaceColoring` as it stands, so some of
  this can be had with no new structure at all — and, in the other direction,
  querying the colouring yields edge pairings for free.
- For edges that share only a *vertex* and no face, the same algebra gives
  `A ⊕ B = C ⊕ D`, a four-face parity constraint that a pairwise union-find over
  faces cannot hold. That is what the edge-level store is for.

## The data model

**Parity relations** (both-or-neither, exactly-one) go in a parity union-find over
edges. Transitive closure is free, contradictions are detected on insertion, and
querying is O(1):

```python
class EdgePairing(ParityRelation):
    both_or_neither(edge1, edge2)     # False on contradiction
    exactly_one(edge1, edge2)         # False on contradiction
    relation(edge1, edge2)            # True (opposite) / False (same) / None
    group(edge)                       # [(edge, opposite), ...], includes itself
    forced_by(edge, guess)            # {edge: guess} for everything tied to it
```

When any edge in a group becomes known, every edge in the group is determined —
which is what `forced_by` returns, so the caller needs no parity arithmetic of
its own. Edge keys are canonicalized, since COMPAS spells one edge either way
round while a dict would hold those as two items.

**Clause relations** (at-least-one, at-most-one) cannot go there: they are not
equivalences. They want an implication store over literals, where a literal is an
edge together with a state:

```python
class EdgeClauses:
    at_least_one(edge1, edge2)        # ¬a → b,  ¬b → a
    at_most_one(edge1, edge2)         #  a → ¬b,  b → ¬a
    implications(edge, guess)         # what this state forces directly
    forced_by(edge, guess)            # ...and transitively; None if impossible
    exactly_one_pairs()               # pairs holding both clauses
```

Propagation is a walk from each newly decided edge. Deriving both `x` and `¬x`
is the contradiction, and `forced_by` returning `None` is a deduction in its own
right: the supposition is impossible, so the edge takes the other state.

**They compose.** Exactly-one is at-least-one *and* at-most-one, so a pair that
collects both clauses — typically from two different rules — can be **promoted**
into the union-find as an opposite-parity relation. `exactly_one_pairs()` is that
seam; promotion is where separate rule families start feeding each other, and it
is nearly free to check.

## Which pairs to track

Not all of them. A pair is only worth storing if some rule can say something about
it, and rules speak about edges that **share a vertex** or **share a face**. Those
are also the pairs whose relations chain usefully: consecutive edges round a face,
or round a vertex, are how a deduction travels across the solid.

The saving is large. Pairs sharing a vertex number `Σ_v C(d_v, 2)`, pairs sharing
a face `Σ_f C(n_f, 2)`, against `C(E, 2)` for every pair:

| solid | E | sharing a vertex | sharing a face | all pairs |
|---|---|---|---|---|
| disdyakis triacontahedron (`dbD`) | 180 | 1020 | 360 | 16110 |
| Goldberg GP(1,2) (`gp12`) | 210 | 420 | 1020 | 21945 |

So locality cuts the space by more than tenfold, and the pairs it drops are ones
no rule would have populated anyway.

That said, the general machinery does not *need* the restriction — a relation
between two edges on opposite sides of the solid is perfectly meaningful, and
transitive closure will occasionally produce one. Two thoughts on that:

- Chains are how such pairs arise, and the union-find keeps them without being
  asked: relate `e` to `f` and `f` to `g` and it knows about `e` and `g`, however
  far apart they are. That is free and should not be suppressed.
- Deliberately *enumerating* distant pairs is a separate experiment — occasionally
  useful, and interesting in its own right, since it asks how much of a puzzle's
  difficulty is local. Any large solid is a fair benchmark for measuring what it
  costs and what it buys.

## Where the constraints come from

**At a vertex** with `f` filled edges and `u` unknown ones, given the rule that a
vertex uses 0 or 2 edges:

| situation | constraint |
|---|---|
| `f == 1, u == 2` | exactly one of the two |
| `f == 0, u == 2` | both or neither |
| `f == 1, u > 2` | at most one, for each of the `C(u,2)` pairs |
| `f == 2` | every unknown edge is ruled out (the existing rule) |

Note `f == 0, u == 3` yields *nothing* pairwise: `000` and `110` are both legal, so
no pair is constrained.

**On a face** with clue `k`, `f` filled edges and `u` unknown, writing
`deficit = k − f`:

| situation | constraint |
|---|---|
| `deficit == 1` | at most one, for every pair of unknowns |
| `deficit == u − 1` | at least one, for every pair of unknowns |
| both (`u == 2, deficit == 1`) | exactly one |
| `deficit == 0` or `deficit == u` | all ruled out / all filled (existing rules) |

Those two lines generalise the cases that turn up by hand. Both are `O(u²)` pairs
per face, which is nothing for `u ≤ 10`.

**These emitters subsume pattern Rules A and B**, which is a useful correctness
check and was verified directly. Rule A is a -1 face (deficit `u−1`, so
at-least-one) at a vertex whose other edges are ruled out (`f == 0, u == 2`, so
both-or-neither); at-least-one plus both-or-neither forces both edges filled,
which is exactly what Rule A concludes. Rule B is the same shape with clue 1,
deficit 1 and at-most-one, forcing both ruled out. Keep the patterns anyway: they
are far cheaper, and they model what a player recognizes at a glance, which is
the same reason `apply_pattern_rules` coexists with `propagate_with_lookahead`.

## The payoff is in the queries, not the propagation

Propagating these relations is the obvious benefit. The larger one is *asking*
about them while applying the ordinary rules, which lets the clue arithmetic be
rewritten before it is used. For a face, group its unknown edges by what the
pairing knows:

- two unknowns that are **exactly one** contribute precisely 1 between them, so
  drop both and reduce the deficit by 1, then apply the ordinary clue rule to
  what remains;
- two unknowns that are **both or neither** contribute 0 or 2, never 1. On a face
  with deficit 1 and unknowns `{a, b≡a, c}`, both `a` and `b` must be empty and
  `c` filled;
- and if a face with deficit 1 has *only* two unknowns which are both-or-neither,
  the position is contradictory — a pruning the solver cannot currently see.

The same substitution sharpens the vertex rule. None of these deductions are
reachable today, and each is a one-line query away once the store exists.

## Two decisions that keep it simple

**Don't trail it; rebuild it.** `FaceColoring` is built from scratch inside
`apply_color_rules` and thrown away, which is why `save_state` is nothing but a
list of edge guesses. Build the pairing and the clause store the same way and the
lookahead machinery needs no changes at all — there is no constraint database to
unwind on backtrack, which is where solvers of this kind usually acquire their
subtlest bugs.

**Run it where colouring runs.** Colouring every round was measured at 25–40%
slower for little gain, because the local rules usually get there first. The new
family belongs in the same slot in `propagate_constraints`: only once the cheaper
rules have stalled.

## Why this should unlock the hard solids

High vertex degree cuts both ways, and the two effects are the same number seen
from opposite ends. A `d`-valent vertex admits `1 + C(d,2)` states — 4 at `d = 3`,
46 at `d = 10` — which is the branching cost. But the payoff scales too: the
*second* filled edge at that vertex rules out `d − 2` others at a stroke, and a
*single* filled edge means exactly one of the remaining `d − 1` is filled, which
is 36 at-most-one pairs at a 10-valent vertex.

So a high-degree vertex is a liability only until the first fact lands there, and
an asset afterwards. That is the shape of the failure on the three Catalan solids
whose puzzles could not be generated (`dtC`, `dtD`, `dbD`, at 36, 90 and 180
edges): their faces are all triangles, so clues can only say 0, 1 or 2, and the
solver rarely gets the foothold that would start the cascade at their 8- and
10-valent apexes. Pair constraints are precisely the machinery for making a
partial fact useful, so those three are the benchmark to measure this work
against: today they are not merely slow but out of reach.

## Later: the player's side

The same model — a pair of edges plus a relation — is what a UI hint would draw:
two edges tied together, or marked as alternatives. Worth remembering that the
browser has its own mirror of the rules in `js/solutionChecker.js`, so that would
be a second implementation to keep honest rather than shared code.
