# Gently teaching players about polyhedra

Goal: a player who came for the puzzle leaves knowing that these solids have
characters and reasons for existing. Strictly opt-in — no quizzes, no "Did you
know?" interruptions, nothing that reads as homework.

## What the data already supports

Every grid JSON carries `categories`, and `data/grids.json` adds V/E/F counts,
so several of the best hooks need no authoring at all.

Category vocabulary in use (26 grids, as of 2026-08-04):

| count | category |
|------:|----------|
| 13 | Archimedean solid |
|  8 | Johnson solid |
|  5 | Platonic solid |
|  2 | deltahedron |
|  2 | quasiregular polyhedron |
|  1 | parallelohedron |
|  1 | chiral polyhedron |

Note the two kinds: **families** (Platonic / Archimedean / Johnson, later
Catalan…) which partition the collection, and **cross-cutting attributes**
(deltahedron, chiral, quasiregular, parallelohedron) which a solid may have
alongside its family. Grouping should key on the family; the attributes are
interesting extra badges.

**Caveat on the `recipe` field:** it is the recipe used to *generate* the
geometry, not a pedagogical label, and it sometimes takes a non-canonical
route — `sD.json` has `dgD` and `tI.json` has `dkdI`, where a learner wants
`sD` and `tI`. `T` and `D` have no recipe at all. So teaching Conway notation
(see below) wants a separate `conway` field, not this one.

## The three highest-value ideas

### 1. Group the polyhedron picker by family

A `<select>` takes `<optgroup>`, so the picker becomes:

```
── Platonic solids ──      Tetrahedron (4 faces), Cube (6 faces), …
── Archimedean solids ──   Cuboctahedron (14 faces), …
── Johnson solids ──       Square pyramid (J1) (5 faces), …
```

Everyone who picks a puzzle absorbs the taxonomy — no prose, no clicks,
nothing to dismiss. Highest learning-per-byte in the list, and it scales as
solids are added: the families do the organising.

### 2. An "About this solid" card, reachable in two places

The celebration dialog is the natural moment — the player has just spent real
time with the shape and earned the curiosity. But put the same card behind an
ⓘ next to the Polyhedron picker as well, because someone curious mid-puzzle
shouldn't have to finish first, and someone who never finishes a 32-face grid
shouldn't be locked out of the interesting part.

Content, all derivable from data on hand:

> **Cuboctahedron** — Archimedean solid · quasiregular polyhedron
> 12 vertices, 24 edges, 14 faces — 8 triangles, 6 squares
> Every vertex is the same: triangle, square, triangle, square (3.4.3.4)
> 12 − 24 + 14 = 2 · like every solid here
> Conway recipe **aC** — the *ambo* of the Cube
> More: Wikipedia · Visual Polyhedra

The **vertex configuration** line is computed by walking the faces around a
vertex; it *shows* what "Archimedean" means instead of asserting it. Only worth
printing when it's the same at every vertex — which is exactly the
vertex-transitivity that makes it meaningful.

The **Euler line** is the cheap delight: different arithmetic every puzzle,
same answer every time. That's how a person discovers a theorem instead of
being told one.

**The exception the data handed us.** Running the vertex-configuration
computation over all 26 grids turned up this pair:

```
J37   Elongated square gyrobicupola   V24 E48 F26   8 triangles, 18 squares   3.4.4.4
eC    Rhombicuboctahedron             V24 E48 F26   8 triangles, 18 squares   3.4.4.4
```

Same counts, same faces, same arrangement at every vertex — and one is
Archimedean while the other is a Johnson solid. J37 is the
pseudo-rhombicuboctahedron: matching vertex figures, but no symmetry of the
whole solid carries one vertex to another, so it fails vertex-transitivity.
It's the standard counterexample for why the Archimedean definition needs
global symmetry rather than local matching, and it's *in the puzzle set*.

The card detects this by rule rather than by name — a uniform configuration on
a solid outside the Platonic/Archimedean families — and adds a note. Any future
solid in the same position gets it too. Worth pairing with a cross-link to the
rhombicuboctahedron when cross-links exist: "compare these two" is the whole
lesson.

### 3. Cross-links to related solids you can play

"The cuboctahedron is the *ambo* of both the Cube and the Octahedron" — both
as links that load those puzzles. This turns the category labels into a space
to wander, which is what produces the sense that solids have reasons to exist.
Much of it derives from Conway recipes: `aC`/`tC`/`eC`/`bC`/`sC` share a seed,
so "other things made from the Cube" is a query rather than data entry.

## Worth adding later

- **Duals**, once Catalan solids exist. The most memorable structural fact,
  and after the Euler line the player can verify it: the counts swap.
  "Rhombic dodecahedron: 14 vertices, 24 edges, 12 faces — the cuboctahedron's
  numbers, inside out."
- **"You've seen this before."** Truncated icosahedron → football, buckyball.
  Cuboctahedron → how oranges stack. Rhombic dodecahedron → honeycomb cells,
  garnet crystals. The most human door, and the only idea needing hand-written
  prose: one sentence per solid.
- **A progression that teaches.** `nextPuzzleLocation` already walks a fixed
  order; if that order moves family by family, the sequence is a curriculum
  nobody has to opt into.
- **A "collection" page** — every solid, grouped by family, the solved ones
  marked. Encourages breadth over grinding one grid. Needs localStorage
  persistence, so it's a bigger piece.

## Data that would need adding

| field | per | effort | powers |
|---|---|---|---|
| `wikipedia` slug | grid | trivial | the More link |
| `conway` | grid | trivial | the "how it's made" line (see caveat above) |
| `blurb` (1 sentence) | grid | ~26 sentences | "you've seen this before" |
| `related` / `dual` gridIds | grid | small, or derive from `conway` | cross-links |
| category descriptions | ~8 categories | 8 short paragraphs | "what *is* an Archimedean solid?" |

Category text is the best value: eight paragraphs cover all 26 solids and
everything added later.

## Sources (settled)

Wikipedia is deliberately **not** used. What the card links to instead, all
checked (every URL HTTP 200 on 2026-08-04) and recorded in
`js/polyhedronLinks.js`:

| what | source | why |
|---|---|---|
| the individual solid | [Visual Polyhedra](https://dmccooey.com/polyhedra/) (dmccooey.com) | a page per polyhedron: interactive model you can spin, plus vital statistics |
| the family / property | [Virtual Polyhedra](https://www.georgehart.com/virtual-polyhedra/vp.html) (George Hart) | tutorial prose with exercises — what someone meeting "Archimedean" needs |
| Euler's formula | [Plus Magazine](https://plus.maths.org/eulers-polyhedron-formula) | Cambridge's Millennium Mathematics Project; authoritative *and* for general readers |

Two traps found while wiring this up:

- **Hart has no readable per-solid pages.** His individual links are raw
  `.wrl` VRML model files, so he's the family source, not the solid source.
- **The URLs can't be derived from names.** Chiral solids have separate laevo
  and dextro pages at Visual Polyhedra and no plain one (`SnubCube.html` is a
  404), so `sC` and `sD` point at the laevo page and the card claims nothing
  about which hand our model is. Hence a hand-maintained table, with a test that
  fails if a newly added grid isn't in it.

Still unlinked, on purpose: **parallelohedron** and **chiral polyhedron**. Hart's
glossary defines chirality but has no per-term anchors to link to, and the good
parallelohedron write-ups are either Wikipedia or terse reference entries
(MathWorld). Better a plain word than a disappointing link.

Also worth a look if more sources are wanted later: polyHédronisme, an
interactive Conway-operator playground, for someone who has just learned what
*ambo* means.

## Constraints

- Opt-in only. Nothing blocks, nags, or quizzes.
- On the celebration overlay, many players want **Next puzzle** immediately, and
  the phone layout is tight: the About card goes *below* that button, or behind
  a single collapsed line, so it never pushes the button toward the fold.

## Status

- [x] Picker grouping by family
- [x] About card (name, categories, V/E/F, face census, vertex configuration,
      Euler) in the drawer and on the celebration overlay
- [x] Outbound links: the solid, each family/property, Euler's formula
- [ ] A source for parallelohedron and chiral polyhedron (see Sources)
- [ ] Category descriptions
- [ ] Cross-links between related solids (needs `conway` or `related`)
- [ ] Duals, "you've seen this before" blurbs, collection page
