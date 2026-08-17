Completed items, moved out of TODOs.md (2026-08-05) to keep the live list
readable. Text is verbatim, including the notes recording how each was settled.
Anything still marked [~] or containing open sub-items stayed in TODOs.md.

- [x] vertex labels appear to be stretched wide for single-digit numbers.

- [x] Celebration:
    - [x] Add some "confetti" at the beginning.
    - [x] Besides just rotating the shape, "gyrate" it, i.e. also rotate the axis of rotation (slowly) so that we get to see all sides equally well.

- [x] If I accidentally press "back", it goes to the previous puzzle, without any
  confirmation about leaving. If I then go "forward", it returns to the puzzle
  I was on, apparently preserving my marks, but then the puzzle is frozen and I can't
  mark it.
  - [x] If a puzzle is partly done, and the user tries to navigate away, ask for confirmation first.

- [x] We could have a setting for automatically marking edges as ruledOut. E.g.
  - when there's a 0 clue, its edges are ruled out;
  - when a face is already satisfied (has filled = clue).
  - when a vertex has 0 filled and 1 unknown; or 2 filled and any number of unknown.
  - we'd have to make sure that "undo" will undo auto-markings as well as manual.
  - Built as a checkbox below "auto-highlight mistakes", off by default. The 0-clue
    case turned out to be the satisfied-face rule with nothing filled, so there are
    two rules, not three. One pass, local to the moved edge: chaining them to a
    fixed point would unfold a large region from one click. The move and its
    rule-outs share one undo entry, which the history's existing array-of-deltas
    shape already supported.

- [x] put in some aesthetic animation: smoothed zooming in on load, zooming out when solved,
    smoothed autorotate after load (while zooming), stops when mouse clicked.
- [x] on phone: edges are too thin, hard to pick.

- [x] quick?: highlight the "Check Solution" button automatically when it's ready to check.
    Not sure if "ready to check" should mean when all clues are satisfied and no mistakes are highlighted ... or only
    when the puzzle is completely & correctly solved... or when the loop is complete and not self-intersecting...
    or some combination of these. I don't want to add an expensive test on the player's every click.
    But maybe if there's a cheap test that short-circuits expensive tests...
- [x] Celebration tweaking:
  - [x] have end of music coincide with end of animation (3 "beats"). Probably by shortening notes.
  - [x] cycling of loop needs to be slower than it is when loop is longer. (too flashy now
    -- is it proportional to loop length? effectively yes: shimmerCyclesPerSecond: 0.3
    seems to be for the whole loop.)
  - [x] It's harder to test with a longer loop, because it takes longer to solve the puzzle by hand. Maybe I need an "insta-solve" key.
    The existing debug "show solution" shows this, but then you still have to copy the solution by clicking.
- [x] tetrakis snub cube (geodesic-ish)
- [x] I want to add a few geodesic polyhedra to our grid. It's probably not worth a new family though; we'll keep them under Miscellaneous. But "geodesic" would be a new category.
  - Read https://en.wikipedia.org/wiki/Geodesic_polyhedron 
  - What would be the best 2 or 3 geodesic polyhedra to add? My criteria are:
  - Simpler is better
  - Get the real "flavor" of geodesic solids
  - distinct from existing grids (like icosahedron)
  - Maybe a variety of class I, II, III from the wikipedia article
  - Don't let them get too big. All-triangle solids are probably boring at large size.

- [x] genSliPuzzles LIVELOCKS on dtC, in Phase A -- painting the red/blue regions
  -- and never reaches a clue set at all. Profiled 2026-08-06: of 240s, 210s was
  ensure_connected, with 137,047 iterations of generate()'s while loop and 1.95M
  faces repainted (~14 per iteration). For comparison dtO, identical at
  14/36/24, leaves generate() in 0.008s after 9 iterations and spends its time
  where you'd expect, in generate_minimal_clueset. So this is not slowness and
  more patience cannot help.
  - [x] Capped it: paint_regions() gives up on a coloring after
    REPAIR_PASS_LIMIT (200) passes and generate() starts over from a fresh
    random coloring, raising after COLORING_ATTEMPT_LIMIT (20) failures. All
    three now fail loudly in seconds -- dtC 1.7s, dtD 9.3s, dbD 24.5s -- instead
    of spinning forever, while dtO still settles in 9 passes and dtI in 7. The
    attempt limit is deliberately small: cost per pass grows with face count, so
    a generous limit just means minutes of spinning before the error appears
    (500 attempts took over 10 minutes on dbD).
  - [x] Replaced the networkx component search in ensure_connected with a plain
    BFS (color_components). Measured 1.5x faster unprofiled -- NOT the large
    factor the profile suggested. Lesson: cProfile charges per call, so it
    inflates call-heavy library code like networkx's generators and coreviews.
    It was still right about WHERE the time went structurally (region painting,
    not the solver); just not about how much a rewrite would save.
  - Retrying does NOT rescue these solids: 20 fresh colorings, up to 200
    repair passes each, and none settle. So the repair approach itself has to go,
    not just its patience. The loop only exits when a whole pass leaves both
    colors connected without painting, and the two repairs fight --
    ensure_connected(blue) grows blue until connected, which can cut red, and
    vice versa. Prime suspect: adjust_populations calls paint_random_faces to
    hit its 1/3-of-faces quota, and scattered random faces are almost certain to
    be disconnected, so the repair is re-armed every pass. (An earlier note here
    also blamed fix_boring_neighborhoods for not setting the needs_check flags.
    That was wrong: it paints via paint_face, which sets the other color's flag,
    and test_painting_flags_the_other_color_for_a_check covers exactly that.)
  - [x] Done: paint_regions now grows ONE connected region and tests it,
    discarding failures, with generate() retrying -- genLoosePuzzle's approach
    lifted in, replacing the repair loop entirely. All 49 grids now generate,
    dtC/dtD/dbD for the first time; slowest is gp12 at 24.7s, 44 of 49 under 5s.
    One wrinkle the lift did not anticipate: the loop IS the region's boundary,
    so growing uniformly makes compact regions and loops only 40-60% as long as
    the old painter's on larger solids (gp12 39 edges against a stored 112).
    Growing at the region's tips restores the length, but a dendritic region
    keeps touching itself at a vertex, which has to be discarded, and that is
    fatal on the highest-degree solids (dbD failed 2000 attempts running). So
    raggedness now starts at 1.0 and eases off by 0.1 every RAGGEDNESS_PATIENCE
    attempts, letting each grid find its own tolerance.
  - [x] The three newly-working solids get poor puzzles, for the same reason
    they were hard in the first place: being high-degree, they are forced down to
    low raggedness, so their loops stay short and cover little of the solid --
    dbD is a 21-edge loop on a 180-edge solid needing 79 clues across 120 faces,
    and dtD is 14 edges with 34 clues. Worth a better idea than backing off
    raggedness globally: perhaps grow raggedly but repair only the pinches.
  - [ ] Six RegionColoring methods are dead now (ensure_connected,
    fix_boring_neighborhoods, paint_neighbor_face, adjust_populations,
    paint_random_faces, randomize_face_colors) plus the two *_needs_check flags,
    which nothing reads. Left in place for now because their docstrings record
    real historical bugs; delete them (and the three tests that only cover them)
    once we have decided that history can live in git alone.
      - [ ] Confirm the same diagnosis on dtD (20 degree-3 apexes) and dbD,
        which has no degree-3 vertices at all, so its flips must involve
        degree-4 ones and the story may differ.

- [x] Edge-pair constraints ("exactly one of these two", "both or neither",
  "at least one", "at most one"), which is how several of those hand rules
  actually work. Designed in docs/edge-pair-constraints.md: a parity
  union-find over edges (the FaceColoring pattern, extracted and reused) for
  the first two, a 2-clause store for the other two, emitted from vertex and
  clue arithmetic, and queried to rewrite that arithmetic. Benchmark: dtC,
  dtD and dbD, whose puzzles can't be generated at all today.
    - [x] The data model: ParityRelation extracted from FaceColoring, plus
      EdgePairing and EdgeClauses in slisolver.py, with promotion of a
      both-clauses pair to "exactly one". Unit-tested; nothing calls it yet.
    - [x] Emitters: emit_vertex_pairs and emit_face_pairs, driven by
      apply_pair_rules, which runs in propagate_constraints after coloring
      stalls. Subsumes Rules A and B (verified). Fires often on
      triangle-faced high-degree solids and never on the dodecahedron;
      7-30% faster uniqueness checks on the large solids. Figures are in
      docs/edge-pair-constraints.md.
    - [x] Queries: feasible_choices and apply_substitution rewrite the
      clue/vertex arithmetic using known pairings. This was indeed where the
      gain was: gp12's uniqueness checks went 26.9s -> 3.5s, and one of its
      puzzles that used to exhaust the time budget is now proven unique.
    - [x] Measured against dtC, and the answer overturns the assumption that
      these three need more solver rules. dtC puzzles are NOT hard to solve:
      clued at 90% of faces, plain propagation finishes all 36 edges on every
      seed tried. What they are is hard to make UNIQUE. dtC has 8 degree-3
      apexes, and at each one the loop can either pass through the apex (two
      edges) or take the base edge between its two degree-8 neighbours (one
      edge) -- a two-way flip that only a clue on the apex's own triangle can
      settle. Leave a few triangles unclued and ambiguity is almost certain:
      at 80% clues, two different seeds each gave exactly 2 solutions
      (verified by enumerating the completions propagation left open).
      So uniqueness needs ~22 of 24 clues, and by then the puzzle is trivial
      for our solver -- there is no "hard but unique" band to aim at.
    - [ ] Therefore the fix for dtC/dtD/dbD is CLUE PLACEMENT, not more rules:
      clue every low-degree apex's triangle deliberately, then minimise over
      the rest. util/genLoosePuzzle.py exists for probing this (it builds a
      valid puzzle without proving uniqueness, and can survey clue densities).

- [x] On the celebration UI, besides the "Next" button, also have a button for
  staying on the current puzzle for a while to look around. Not sure what to call
  it ... Cancel, Back, "Hang out" or "Stay here". The Esc key already does this:
  dismiss the "dialog" and let the user explore the just-solved puzzle, and then
  select a new one at their own pace.
- [x] The buttons are of slightly uneven sizes.
        E.g. the "upright" and "Reset" buttons look a little shorter on top than the others.
        Actually on careful inspection, the buttons with icons (Unicode symbols) are slightly *taller* than the icons with words.
        (In general, the disabled buttons look taller, probably because their grayed edge contrasts more with the dark background.
        But that's not what I'm talking about. The buttons with icons are actually taller by measurement.)
    - [x] In the collapsed strip, and the expanded panel, the upper padding looks bigger than the lower. It looks funny.
- [x] When a clue is satisfied (i.e. has the right number of walls filled in around
  it), change the color of the digit to be gray instead of black. That will help the
  player visually scan for what can be worked on next. This would include any faces with 0​, unless they have a wall filled in (on which we may later paint the clue digit red or something).
- [x] A while back, when we were getting the puzzle verifier to work, it had heuristics for
    what to try next (I think this was for a depth search), and I said that a very good heuristic would
    be to pick the state for an edge that would determine where the loop goes next (or something like that).
    Anyway Claude timed the results with that heuristic and others, and said that mine actually resulted
    in worse times, and removed that heuristic in favor of another. I allowed that at the time, but it seems to me that
    this was a strong heuristic for pruning the remaining search space. So, given that we're running up against
    time limits in verifying puzzles, maybe we should reintroduce that heuristic ... not instead of others,
    but in conjunction with others. Seems like it can't hurt.
    Claude responded to this paragraph: "For whatever it's worth on the substance: the heuristic you're describing is chain-following, which is option (b) in the note in select_edge_for_branching — it measured worst of the three (96.6s and 4 timeouts, against naive's 80.8s and 3). But that note also records why, and it supports your point rather than undercutting it: the per-call scoring overhead outweighed the search-tree reduction, and no selector helped the pathological instances that dominate total time. So "it can't hurt" was contradicted only by the bookkeeping cost, not by the pruning logic. Combining heuristics as you suggest would add cost rather than remove it, so if we revisit this, the thing to attack first is making the selector cheap to evaluate — and the pair stores now being built during propagation may give it that information for free."
    However, now that we're focusing on making sure puzzles are "deductively solvable" rather than "uniquely solvable," maybe these
    search heuristics aren't even being used anymore.
- [x] On launch, have a title screen that shows an impressive polyhedron (rotating) with puzzle clues
    (and possibly marks too... maybe the solution to a puzzle, but one that's extra, not a spoiler).
    Have a semitransparent overlay in the center with the title "Slitherlink 3D" and maybe buttons
    "How to Play" and "Start". The latter would exit the title screen and start normal play.
    (A URL naming no grid or puzzle is the title screen: it tumbles a random one
    of the bigger solids, zoomed in, with its clues showing, and hides the main
    panel. Both buttons navigate to the tetrahedron; "How to Play" also opens the
    instructions there. See js/titleScreen.js.)
    - [x] show a slitherlink loop on the title solid -- marks, or a solution
      that no puzzle in the catalogue uses, so it can't spoil anything.
      (Done with "display puzzles": an extra authentic puzzle per grid, kept
      under `displayPuzzles` rather than in `puzzles`, so it's never offered to
      a player. Its loop is drawn as filled-in marks.
      Generated by `genSliPuzzles.py --display=N`. All 19 grids big enough for
      the title screen have one.)

- [x] Add Catalan solids
    (All 13, as the duals of the Archimedean solids: `util/genDual.py
    --all-catalan`. Polar reciprocation, which gives exactly flat and provably
    congruent faces -- reciprocation keeps the symmetry group, and a
    vertex-transitive primal therefore dualizes to a face-transitive solid.
    Puzzles filled in by `util/fill_puzzles.py`.)

- [x] Debugging mode could show face IDs, or at least log them when you click on a face.
- [x] Make the info about the polyhedra and their categories more front-and-center.
    Each grid file already includes categories (many-to-many), but we don't show them yet.
    Include a link to info about each polyhedron, and each category. Wikipedia would be a
    defensible standard, but I don't really want to support that anymore. What to use instead?
    - [x] A serious geometer would even want to browse or filter by category, e.g. Johnson solids.
  - [x] tell them if they have failed to make a loop
  - [x] as a player, I would really like to have a button to "remove errors", so I can get back to
  a state where I can move forward, without having to start from scratch.
    (The "Clear errors" button appears when "Check solution" finds wrong marks;
    clearing is one compound move, so a single Undo restores the cleared marks.)
- [x] quick: add a link from the web UI to the github repo, and vice versa from the README to where the app is hosted online.
    - [x] UI -> repo: "source code" link on the panel's title line.
    - [x] README -> hosted app: still needs a URL.
    - [x] requires uploading the code to our web site

- [x] Tweak for mobile:
  - [x] quick: Debug panel overlaps main panel. Move it to lower right.
  - [x] quick: Shift+click isn't available; use long-tap instead.
  - [x] broader margin for picking an edge? In that case do we also need to allow the tap ray
        to intersect multiple edges and pick the closest?
  - [x] The main panel is way too big. Will need to collapse it to a small button.
- [x] quick: let initial (default) puzzle be the simple T? A bigger poly is more impressive,
    but the T is a better place for beginners to start.
- [x] quick: make trackball the default control.
- [x] quick: fix "black" to "dark blue" in instructions.
- [x] quick: brighten lighting on the faces that the camera can see. Sometimes the polyhedron appears
    backlit, and it can be hard to distinguish edge colors.
- [x] puzzle generation: try to make sure that puzzles are fun, not just uniquely solvable.
    Can we measure whether they're trivially propagatable or require deep trial and error?
    This could be similar to the "adjustable difficulty" idea in ideas/puzzle gen algorithm.txt
    One way to measure difficulty is: how many paths forward are available (inferences that can be made) at each step along the way,
    on average?
    - Data point (Aug 2026, from generating the Archimedean solids): our solver's own
      running time is already a rough proxy for "how much search this puzzle needs,"
      and it does NOT track grid size closely. Generating 2 puzzles took:
        truncated cuboctahedron (72 edges): 4 sec
        truncated dodecahedron (90 edges): 68 sec
        rhombicosidodecahedron (120 edges): 150 sec
        truncated icosidodecahedron (180 edges): 560 sec
      So bC, though smaller, was 17x faster than tD. The likely reason is face
      composition rather than size: tD has 20 triangles, whose clues can only be 0-3,
      whereas bC's squares/hexagons/octagons admit higher, more informative clues that
      propagate further. If that's right, then propagation-vs-search really is a
      property we can measure, and clue *informativeness* (a function of face degree)
      is a lever for tuning difficulty -- possibly per face, when choosing which
      clues to keep in genSliPuzzles' Phase B.
      Caveat: solver time conflates "hard for a human" with "hard for our particular
      solver," and it's measured over whole generation runs (many uniqueness checks
      on random clue orderings), not per puzzle. Worth measuring deliberately rather
      than inferring from these numbers.
    - [x] Also, it would be nice to be able to verify that no two puzzles for the same grid
      are the same -- or the same under rotation & reflection.
- [x] UI: implement an "undo" function, to undo edge guesses.
- [x] UI: fix the "reset" function, to clear guesses. It may be partially implemented, but doesn't look like it works.
- [x] UI: allow user to dismiss overlay using Esc and/or click on X.
- [x] Eventually, we'll need a button to go on to the next puzzle, or select
  another puzzle.
    ("Next" appears both in the panel and in the solved-celebration overlay; it
    walks the catalogue order. Leaving a partly-worked puzzle asks first.)
  - [x] somehow we'll need to implement a catalogue of available grids.
  - (The remaining sub-item -- dispose() of THREE.js objects -- is still open and
    stayed in TODOs.md.)
- [x] settle on a format for puzzles and solutions.
    - [x] What do we have so far?
      - data/example.json shows a puzzle and solution for a polygon. This was an "old attempt"
            so I'm not sure if I had ever worked with this format. It encodes
        - "puzzles" property as an array of objects, in each of which we have 
        - "clues" property as an array of numbers, presumably corresponding to the faces in the order
            they were previously listed in the "cells" property; and each number gives the number of
            edges of that face that must be "filled in" in the solved puzzle (i.e. how many of its 
            "sides are segments in the loop"). Here -1 means that no clue should be displayed on that face.
        - "solution" property as an array of booleans, presumably with 1's indicating edges that are
            part of the solution loop, and 0's indicating edges that are not. But how do we know which edge
            each boolean corresponds to? There is no previous sequence of edges to refer to.
            I think it would be better to encode the solution as a list of vertex indices.
      - No other data file seems to have developed puzzle or solution encoding any further.
    - [x] So let's settle on a variation of the above:
      - "puzzles" property as an array of objects (each of which is a puzzle), in which
      - "clues" property as an array of clue numbers, corresponding to the faces in the
        same order as in the faces list. -1 means no clue shown. 
      - "solution" property as an array of zero-based vertex indices, corresponding to the order in the
        vertices list. We don't repeat the first vertex at the end.
      - Validation:
        - both lists must be non-empty
        - the length of the "clues" list must be <= the number of faces
        - the length of the "solution" list must be  <= the number of vertices
        - the "solution" list must not contain any duplicates
        - adjacent vertices in the "solution" list (including the first and last)
          must appear adjacent in one or more faces
    - [x] So that gives us a JSON representation for puzzles and solutions. In regard to the grids, I guess
      we're good with the JSON format emitted by obj2json.py, although it calls faces "cells,"
      which is inconsistent with our usage elsewhere.
      In one sense, "cell" is more consistent with 2D Slitherlink puzzles. I guess we'll leave it as is.

Old items:

- [x] print out some 2D flattened charts (not nets) of octahedron, dodecahedron, and icosahedron
  so I can play with puzzles
- [x] display vertex numbers over vertices: this would really help with entering puzzles
- [x] refactor main() to take scene building out into scene.js
- [x] change signature of getFaceVertices() to take a Face instead of a faceId, avoiding an
  unnecessary lookup
- [x] get js web app to load T.json file and display it
    - [x] then load T-puzzles.json, and display the clues
- [x] Let's get rid of the faceIds and vertexIds that were made up in createPolyhedron,
  and instead just use the indices from the data in the loaded file. Then we
  won't need to search or build arrays to map from index to ID.
- [x] q make optional id parameter to addFace and addVertex non-optional (check usage first)
    - [x] (n/a) adapt createCube and createDodecahedron to provide IDs for vertices and faces
- [x] auto-zoom: after loading polyhedron data from file, zoom to an appropriate level
  based on polyhedron size (e.g. max distance of vertices from origin)
    - [x] Do we need to first move vertices to be centered around the origin?
- [x] make a more interesting puzzle to play with, e.g. D.json / D-puzzles.json.
- [x] Don't display the solution automatically on load.
- [x] produce clue textures for up to 12 faces, instead of just 9, to allow us freedom to use more different shapes.
- [x] In main(), try to stop passing big complicated objects or so many parameters back and forth.
  Instead, group them under a few classes, such as part of Grid and/or maybe a new GridGeometry class.
    - [x] do that refactoring
    - [x] check whether we have files, or large code sections, that are now unused
- [x] implement a faster way to find the edge between to vertex IDs. E.g. for
  highlightSolution in PuzzleGrid. It should be easy, by
  first putting the vertex IDs in increasing order (so we don't have to try both orders), then
  making a hashmap from the pair of vertex IDs to the edge ID. Combine the two IDs using
  a string `${id1},${id2}` or probably into a single integer: (id1 << 16) | id2
- [x] use local copies of THREE.js and OrbitControls so I can keep testing w/o wifi.
- [x] add a debugging mode that shows the vertex and face IDs, lets you display the solution, etc.
- [x] loading THREE.js and trackball controls? takes a lot of time to load. What
  can I do to improve this?
- [x] I should probably move userGuess from Mesh.userData to Edge.metadata, because that's where it belongs.
    But it will take some involved refactoring. Actually it wasn't too bad ... it was mostly in the right place already.
- [x] clicking on an edge has been messed up in that it cycles thru more states than
  just black/white/gray. Fix it. Actually, it only seems to have that problem when
  in debug mode...
- [x] display solution (don't just set the edge states; or maybe even don't change the edge states
  but just the color of the edge geometry!)
    - [x] make sure we're not unnecessarily overwriting userGuess anywhere else.
    - [x] stop displaying solution when we turn off "display solution"
- [x] move some of the sceneManager.setup*() calls in main() into a single
  a single sceneManager.setupStuff() function.
- [x] show some visual indication when puzzle is solved successfully.
    - [ ] probably too slow & complex: a surface wobble. The idea was that for every polygon vertex v_i (not
      to be confused with vertices of subtriangles of faces), you pick a random phase ph; then over say 2 seconds,
      0 < t < 2, set the position p_i of v_i = (original p_i) * (1 + sin(t * 6.0 + ph) * amp), where
      amp is a smoothed bump function like cos(t * 2π / t_max).
        - The reason I think that's too slow & complex is that not only will every polygon vertex sphere position
          have to be moved for every animation frame; but also every edge cylinder will have to be re-angled according
          to the wobbled position of its adjacent polygon vertices, and every sub-triangle of each face polygon will have
          to be repositioned according to the wobbled position of the relevant polygon vertices. That sounds like a lot
          to achieve in 1/30 second, especially on a mobile device. A GPU optimization guru could maybe do it, but do
          I want to do that work?
    - [x] A simpler option: animate the camera a bit. Spin-orbit the camera around and zoom out/in a bit.
        - Maybe also do something with the direct and ambient lighting...
- [x] there still appears to be unused code after the refactor... especially return values.
    - [x] also return*Data() in GameState
    - [x] unused members in SceneManager
- [x] why is SceneManager.initializeScene() called in both GameState.initialize() and scene.js:createGameState()?
