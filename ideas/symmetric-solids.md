# Random symmetric solids: status, open questions, lessons

How `util/genSymmetric.py` works is documented in `docs/generating-grids.md`
(the genSymmetric.py section, including separation and `--regularize`). This
note holds what that doesn't: where the work stands, the facts that decide what
is possible next, and the open questions. Written 2026-09-23.

## Where it stands

- `util/genSymmetric.py` uses the **tetrahedral rotation group T** (12
  rotations) by default, and the octahedral group O with `--group=octahedral`
  (see open question 1 for where that stands). Random orbit representatives →
  hull → polar dual, with symmetric
  relaxation, short-edge separation (on by default, `--min-edge=0.4`) and
  `--regularize` (off by default, so older commands still reproduce). Every
  step keeps the symmetry exact, the faces exactly flat, and the triangulation
  (hence the census) fixed.
- **Seven solids shipped**: `data/cageA`–`cageG` ("Tetrahedral cage A"–"G"),
  60–96 faces, all regularized, each with 3 puzzles and a display puzzle. Their
  `source` lines reproduce them. They carry the `random` category and file under
  "Random solids" in the picker.
- Candidates were reviewed on a private page,
  https://claude.ai/artifact/G3W5K5YVEKwSn5cdfjx2WV (exported locally to
  `tmp/Tetrahedral Solid Candidates/`). It names them by their generator ids
  (symT…), not by the cage letters. Mapping: cageA ← symT5_r25_reg_s1,
  cageB ← symT6_v_r25_reg_s1, cageC ← symT6_vf_r25_reg_s2,
  cageD ← symT7_r25_reg_s1, cageE ← symT7_r25_reg_s3, cageF ← symT7_r10_reg_s2,
  cageG ← symT8_r25_reg_s1.
- Dropped as too similar to the others, by choice: symT6_r25_reg_s3,
  symT5_vf_r50_reg_s8, symT6_e_r25_reg_s1.

## Facts that decide what's possible

1. **Every vertex of these solids has degree 3, by construction.** A polar
   dual's vertices are the poles of the hull's facets, one per facet, and a
   vertex has as many faces as its facet has corners. Random points are never
   four-at-a-time coplanar, so every facet is a triangle. **A degree-k vertex
   needs k exactly coplanar primal points** (a k-cornered facet); its pole is a
   single dual vertex on k faces, and the faces stay exactly flat.
2. **Vertex degree is paid for in face size.** For any convex solid,
   Σ over faces (4 − sides) + Σ over vertices (4 − degree) = 8 (that is
   4(V − E + F)). All-trivalent leaves room for big faces; all-4-valent forces
   faces to average about 4 sides (triangles and squares, the cuboctahedron's
   world). Triangles allow only clues 0–2, so raising degree narrows the clue
   vocabulary, while adding a different kind of reasoning at the vertices.
3. **The angle budget limits regularity.** At a vertex, faces that were regular
   would leave 360 − Σ(180 − 360/sides) degrees; where that is negative (a
   heptagon between two hexagons, for instance), those faces can't all be
   regular, and a squeezed corner pushes the face's fixed angle sum into its
   other corners — which is where straight corners come from. It depends only
   on which faces touch which, so it can be computed before any geometry.
   A scan of 1,524 varied tetrahedral draws found only 2 with no over-budget
   vertex, both with just pentagons, hexagons and heptagons. **Random orbits
   cannot give faces that are both regular and very varied**; that needs
   structured adjacency, big faces ringed by small ones, as in the Archimedean
   solids.
4. **Regularizing depends only on the combinatorics.** Two different draws
   (seeds 8 and 34 of the same settings) regularized to exactly the same solid.
   So a seed search should deduplicate by triangulation, not by seed.
5. **Neighboring faces' angle = their points' angle.** Each dual face lies in
   the plane x·v = 1, so its normal is its own point v. "No two faces nearly
   flat" is therefore a cheap constraint on point spacing.
6. **Higher symmetry means less variety.** Every face in an orbit is congruent,
   so the census comes in orbit-sized blocks. In 60–100 faces: tetrahedral
   (order 12) leaves 5–8 free orbits, octahedral (24) 2–4, icosahedral (60)
   one, where Euler all but forces a Goldberg solid (12 pentagons, 60 hexagons).
7. **Only higher-order axes can force coplanarity.** A point's images around a
   k-fold axis are exactly coplanar however the point moves. The tetrahedral
   group's axes are at most 3-fold, and three points are always coplanar, so it
   can't force degree > 3 — which is why every cage is trivalent, axis options
   and all. The octahedral group's 4-fold axes give squares (degree-4 vertices,
   six of them); the icosahedral group's 5-fold axes give pentagons (degree 5,
   twelve).

## Open questions and next steps

1. **Vertices of degree > 3: the octahedral prototype is built** (2026-09-23),
   as `--group=octahedral`: merged facets, a polar dual over them, and the
   facets held fixed. How it works, and a table of eighteen regularized
   candidates, are in the genSymmetric section of `docs/generating-grids.md`.
   Every octahedral solid has exactly six vertices of degree 4, except with
   `--vertex-axes`, which leaves none. The tetrahedral cages still regenerate
   byte for byte.
   - **Not yet reviewed**: the candidates are in
     `tmp/Octahedral Solid Candidates/solids/`, and nothing is in `data/`.
   - **As expected, there's little room.** Most draws are one orbit of
     pentagons among hexagons, which regularizes to near-regular and plain.
     The varied draws regularize badly, and the relax-0 ones worst.
   - Six degree-4 vertices out of 100–180 is a light seasoning. More would
     need more forced coplanarity, and only the 4-fold axes force it: a facet
     off every axis has no rotation holding its corners in one plane. So under
     O, six is the most.
   - Unused so far: the angle-budget formula for a degree-d vertex,
     360 − Σ over its d faces of (180 − 360/sides), which a budget-aware seed
     search (question 4) would need.
2. **Icosahedral with forced pentagons** (degree-5 vertices): only one free
   orbit, but the degree-5 vertices might make it worthwhile anyway.
3. **Full groups with reflections** (T_d, T_h, O_h): mirror-symmetric rather
   than chiral solids; orbits double in size, so even less variety. Untried.
4. **A budget-aware seed search**, e.g. `--search=N`: of N draws, keep the one
   with the fewest over-budget vertices (fact 3), deduplicating by
   triangulation (fact 4). The scan behind fact 3 was a throwaway script; its
   method is all in fact 3.
5. **A generator for faces both regular and varied** would need structured
   adjacency rather than random orbits: a separate project, not started.
6. **"Sides within a face"**, the longest ÷ shortest side ratio reported by
   `util/grid_quality.py` and on the candidate page, is an unclear label.
   "Longest ÷ shortest side" was suggested; not decided.
7. The capsid and the expanded truncated icosahedron land under "Others" in
   the picker: the capsid has no structural category.
8. Clue digits look off-center on irregular faces (see `ideas/TODOs.md`),
   which the cages make more noticeable.
