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
(deltahedron, chiral, quasiregular, zonohedron, parallelohedron, self-dual)
which a solid may have alongside its family. Grouping should key on the family;
the attributes are interesting extra badges.

Two conventions, both enforced by tests in `js/tests/catalogue.test.js`:

- **Exactly one family per grid**, since the picker files each solid under one
  heading.
- **Only the narrowest category, where one implies another.** Every
  parallelohedron is a zonohedron (Polytope Wiki even makes Parallelohedra a
  subcategory of Zonohedra), so the cube is listed as a parallelohedron and
  leaves it there; the broader fact is one click away on that page.

### The attribute audit (2026-08-05)

Checked against Polytope Wiki's own category tags, via its API, rather than from
memory — `Category:Convex_deltahedra`, `Category:Parallelohedra`,
`Category:Zonohedra`, `Category:Convex_quasiregular_polyhedra` — plus the
articles' own text for chirality (the wiki's `Category:Chiral polyhedra` is
about skew polyhedra, so it's the wrong tool; the symmetry notation's `+`
suffix and the prose agree instead).

What that turned up, beyond what the data already had:

| added | to | why |
|---|---|---|
| `deltahedron` | I | the icosahedron is one of the 8 convex deltahedra, along with T and O which already had it |
| `parallelohedron` | C | the cube is the first of Fedorov's five; only C and tO qualify here |
| `zonohedron` | bC, bD | all faces centrally symmetric. Among uniform solids only C, tO, bC, bD qualify — and the first two are listed as parallelohedra instead |
| `chiral` | sD, J47, J48 | sC already had it. J47 and J48 are two of the five chiral Johnson solids (J44–J48) |
| `self-dual` | T | the tetrahedron is its own dual — a nice thing to meet on the first puzzle |
| `Goldberg` | D, tI | trivalent, faces only pentagons and hexagons, always exactly 12 pentagons. D is GP(1,0) and tI is GP(1,1); no other solid we had at the time qualified (checked by counting face sizes and vertex degrees across data/). Capitalized, being someone's name. The two grids added since — cD = GP(2,0) and gp12 = GP(1,2) — carry it as well, with "Miscellaneous" for a family, since they belong to none of the classical four |

Checked and deliberately NOT added: `quasiregular` stays on aC and aD only (the
octahedron is quasiregular *as a tetratetrahedron*, which the wiki doesn't tag
and which needs more explanation than a badge affords); J10 and J75 are
**not** chiral (`B2×I` and `A2×I` symmetry, no `+`, and their articles don't say
chiral) even though several of their Johnson neighbours are.

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
| the individual solid | [Polytope Wiki](https://polytope.miraheze.org/wiki/Cuboctahedron) | an article each: prose, pictures, a "Related polyhedra" section, hundreds of cross-links to wander |
| the family / property | [Virtual Polyhedra](https://www.georgehart.com/virtual-polyhedra/vp.html) (George Hart) | tutorial prose with exercises — what someone meeting "Archimedean" needs |
| Euler's formula | [Plus Magazine](https://plus.maths.org/eulers-polyhedron-formula) | Cambridge's Millennium Mathematics Project; authoritative *and* for general readers |

Rejected for the per-solid link: **Visual Polyhedra** (dmccooey.com), which was
the first choice and is more precise, but its pages are a table of vital
statistics — accurate and dry, the wrong note to end a puzzle on. Kept in mind as
a data reference. **qfbox.info/4d/&lt;name&gt;** is the fallback for a solid
Polytope Wiki lacks, but its naming is irregular (`/cuboctahedron` exists,
`/truncated_icosahedron` doesn't), so each such link needs checking by hand.

Notes from wiring this up:

- **Hart has no readable per-solid pages.** His individual links are raw
  `.wrl` VRML model files, so he's the family source, not the solid source.
- **Per-solid URLs are derived, not tabulated.** MediaWiki titles are the plain
  name with underscores for spaces, which is the form the gridNames are already
  in (minus the `(J37)` suffix), so all 26 come out right and the exception table
  is empty. It stays in place because the rule is a convention, not a guarantee.
- **Chirality is a non-issue here.** Polytope Wiki has one article per snub
  solid; Visual Polyhedra splits them laevo/dextro with no plain page, which
  would have needed two exceptions.

A polyhedron added later gets its link for free, but an unverified one.
`npm run test:links` fetches every link the catalogue produces and insists on
200; it's skipped by the everyday suite, which shouldn't need the network.

`CATEGORY_PAGES` holds full URLs, so each category can go wherever it's covered
best: the families to Hart, **chiral** to Polytope Wiki's
[Chirality](https://polytope.miraheze.org/wiki/Chirality) (Hart's glossary has an
entry but no per-term anchor, so a link would land at the top of a long page).

Still unlinked, on purpose: **parallelohedron**. The good write-ups are either
Wikipedia or terse reference entries (MathWorld). Better a plain word than a
disappointing link.

Category names are kept short — `chiral`, not `chiral polyhedron` — since the
card has already given the solid's name and family by the time you read them.
(`quasiregular polyhedron` is the remaining long one.)

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
