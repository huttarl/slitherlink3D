Note, some of these items may be already done even if they're not checked off.
Finished items live in ideas/TODOs-done.md.

- [ ] We could have a setting for automatically marking edges as ruledOut. E.g.
  when there's a 0 clue, its edges are ruled out; or when a vertex has 0 filled and
  1 unknown; or 2 filled and any number of unknown.
- [ ] The routine tests seem to be getting really slow. Can we refine our testing
  process to require fewer tests unless necessary? Or maybe it's just me.
- [ ] On the celebration UI, besides the "Next" button, also have a button for
  staying on the current puzzle for a while to look around. Not sure what to call
  it ... Cancel, Back, "Hang out" or "Stay here". The Esc key already does this:
  dismiss the "dialog" and let the user explore the just-solved puzzle, and then
  select a new one at their own pace.
- [ ] Adding more info about each polyhedron, as applicable:
  - [ ] add aliases, like "buckyball" / "soccer ball" for truncated icosahedron
  - [ ] link to dual solid - linking to that solid in the game, if we have it
  - [ ] Conway recipe, with link to polyhedronisme
  - [ ] Where to fit all this stuff, without overwhelming the user? Put some of it
    under a "More" fold?
- [ ] Add more rules, after A B C and D, to help the puzzle generator / evaluator know
    what's possible & easy for players. I have several that I use experientially in
    solving variety slitherlink puzzles.
    - [ ] Edge-pair constraints ("exactly one of these two", "both or neither",
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
- [ ] genSliPuzzles LIVELOCKS on dtC, in Phase A -- painting the red/blue regions
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
    - [ ] Retrying does NOT rescue these solids: 20 fresh colorings, up to 200
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
    - [ ] The three newly-working solids get poor puzzles, for the same reason
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
    - [ ] One thing that should be fruitful is to walk through my manual solving process
      of a puzzle or two, telling Claude along the way what patterns I'm seeing and using,
      and letting it decide whether that's a new rule, or something that's covered by existing
      rules.

- [ ] quick?: highlight the "Check Solution" button automatically when it's ready to check.
    Not sure if that's when all clues are satisfied and no mistakes are highlighted ... or only
    when the puzzle is completely & correctly solved.
- [ ] This is probably mentioned elsewhere where I talk about sources of polyhedra, but ...
    look at Krazydad's Variety Slitherlinks to see which tilings might inspire good
    new polyhedra. E.g. Penrose tiling...
- [ ] At some point, it would be good to save persistent state about which puzzles the user
    has solved. Then completionists can make sure they've done all of them. The dropdown
    pickers could reflect which grids and puzzles are done, and the panel could show that state
    for the current puzzle. (Maybe even "Solved in 4m55s.")
- [ ] Consider "landmarks" in the background, to help the player stay oriented, especially if
    we're using trackball controls, where "up" doesn't stay stable. E.g. a moon or planet. But landmarks
    whose "up" is obvious would help more. And 2 or 3 landmarks would help more than one.
    Maybe a bird, a cloud, an airplane... milky way...
    - [ ] I was thinking just part of the background texture, but we could do actual 3D models,
      if they're close enough for that to matter. It's just harder to find good ones free.
- [ ] Celebration:
    - [ ] Add some "confetti" at the beginning.
    - [x] Besides just rotating the shape, "gyrate" it, i.e. also rotate the axis of rotation (slowly) so that we get to see all sides equally well.
- [ ] In JS code, why are we copying data from grid to puzzleGrid, instead of inheriting it?
- [ ] try to refactor loadPolyhedronFromJSON() to not pass back so many random parameters.
  - [ ] similarly createPolyhedron().
- [ ] vertex labels appear to be stretched wide for single-digit numbers.
- [~] Add a "Done" button, at which point we check the user's guesses and
    give feedback on whether they were correct.
  - [~] highlight wrong guesses in red — done for clear RULE violations (self-crossings),
    highlighted passively, toggleable via the "Auto-highlight mistakes" checkbox.
    Solution mismatches that don't break a rule are deliberately NOT highlighted
    (that would spoil the puzzle); "Check solution" reports only their count.
    - [ ] Maybe instead of coloring *edges* red when there are too many filled-in edges to a vertex,
      color the *vertex* red in that case. Because it's not one edge rather than the others that is the problem.
      Or similarly in the case when a vertex has exactly one filled-in edge
      and no edges remaining that could later be marked filled-in. The mistake is specific to the vertex.
    - [ ] When a face has too many filled-in edges for its clue, or can't get enough walls, highlight the face red.
    - [ ] Persist these passive highlights, so that the next mistake doesn't remove highlights for
      the previous one.
    - [ ] maybe later: a "show errors" button that highlights solution mismatches
      on request — a stronger, spoiler-level hint that some players like.
- [~] Add a "show solution" button
    - [ ] This is available in the debug panel. Is that sufficient?
- [ ] maybe add a "hint" button.
- [ ] when we switch puzzles in place, we'll need to be careful to 'dispose()' of THREE.js objects,
    - and also remove bidirectional references.
    - (Sidestepped for now: changing grid/puzzle reloads the page, which
      disposes everything for free.)
    - (Left behind when its parent item -- the "next puzzle" button -- was moved
      to TODOs-done.md.)
- [ ] Add the ability to "color" faces to reflect "inside" vs. "outside". User selects a
    "color" and then can click on a face to tint it that color. Implementation would have to
    make sure it interacted OK with clue numerals. Colors must be light enough to contrast well.
- [ ] put in some aesthetic animation: smoothed zooming in on load, zooming out when solved,
    smoothed autorotate after load (while zooming), stops when mouse clicked.
- [ ] maybe just for fun, add an option to use other numerals for clues:
  Persian/Urdu/Hindi/Eastern Arabic ...
    - [x] implement number->string conversion for other locales
    - [ ] add user-accessible settings for this
- [ ] convert some existing .json files to the latest format spec, or move them out of the
    data folder, so it's less cluttered. Maybe just have a C.json and T.json in there for now.
- [ ] terminology: how do we talk consistently about the "sides" of a face? The especially tricky distinction
  is between how many edges a face has, vs. how many of them are actually part of the loop
  that forms the solution. And how do we say the opposite?
  - (We could also make a distinction between the user's marks and the actual solution.) 
  - For example, "the number inside a
    (face) represents how many of its sides are segments in the loop"? or
  - "the number on a face represents how many of its edges are filled in"?
  - or something else? Looking at https://en.wikipedia.org/wiki/Slitherlink ...
  - "Whenever the number of lines around a cell matches the number in the cell, the other potential
    lines must be eliminated". Here "lines around a cell" means "edges filled in" and "eliminated" means "ruled out"
    as definitely not filled in.
  - "... a ninety degree arc between two adjacent lines, to indicate that exactly one of the two must be filled"
  - "every point has either exactly two lines connected to it, or no lines" - Here again, "lines" means
    "segments of the solution loop," not edges in general.
  - "if a point on the edge of the grid, not at a corner, has two incoming lines which are X'd out, the third must also be X'd out"
    Here, "line" merely means "edge of a square," not "segment of the solution loop." And "X'd out" means
    ruled out as definitely not part of the solution loop.
  - "if one of the three remaining directions that the line can continue ... is a known blank" Here "line" is
    part of the solution loop, and "known blank" is definitely not.
  - Conclusion: Since "line" is unclear from the word itself, and since it's used inconsistently, let's not use it.
    Instead, we'll used "filled in" to mean "part of the solution loop." Then "ruled out" makes a sensible opposite.
    "X'd (out)" is fairly clear but it seems to imply the user's markings, rather than being able
    to refer merely to the fact that a given edge is not part of the solution loop. I guess the same could be
    said of "ruled out," to a lesser degree. "Blank" may work, though it's not as clear. 
    
- [~] Handle errors more gracefully, e.g. in loadPolyhedronFromJSON().
- [~] display name and category of polyhedron (grid) on screen. This will add some "atmosphere."
    - [x] Is this encoded in the JSON?
    - [ ] maybe associate a scene color (scheme) with each polyhedron, and category, for more atmosphere?
- [ ] figure out data flow for grids, puzzles and solutions
    - [x] what formats do we already have
        - [x] as example data
            - we have Stemkowski's JSON format for many polyhedra (converted from Hart)
                - We could use this JSON source for grids in the app, but to use it in puzzle
                generator programs, we'd need to convert it.
                See slitherlink3D-old/js/polyhedron_data.js. Each polyhedron entry has exactly the following properties:
                    name, category (list?), vertex (list of float triples), edge (list of index pairs), face (list of index lists)
                - Seems like edge list is redundant, since it can be derived from face list, right? Assuming every edge
                  is part of at least one face.
            - Hart has a VRML model for practically any polyhedron I would want, but I can't figure out the format.
                It says VRML but it's binary data, whereas VRML is supposed to be text.
            - We have .obj (Wavefront) files for many polyhedra, e.g. in slitherlink3D-2018/data
            - We have corresponding JSON files for the same polyhedra, e.g. in slitherlink3D-2018/data
                - Is this the same JSON format Stemkowski uses? Not sure ... there are definitely some differences
                    between the various JSON formats in files I have lying around, e.g. properties like _comment,
                    id, name, meshId, ...
                - How did I convert between .obj and .json? Do I have code for that somewhere? (probably Python)
                    which direction did it go? I'm guessing .obj -> .json because polyHédronisme exports .obj
                    - Ah yes, there is a program obj2json.py in slitherlink3D-2018 (now in util). Apparently it works.
                        Its comment says "Convert OBJ export from polyHedronisme to Slitherlink3D JSON data".
                        But that JSON output format is not the same as Stemkowski's.
            - polyHédronisme exports as .obj (and not JSON), which is where several of my models came from.
                - polyHédronisme can also export VRML2 (.wrl), a[objToSlith3D.py](../../../../IDrive-Sync/Lars/programming/SlitherlinkNGons3D/objToSlith3D.py) text format, but I haven't played with it.
                    I don't think we need another format in the mix; OBJ and JSON are sufficient.
        - [ ] other programs that generate data (e.g. grids and/or puzzles)
            - polyHédronisme exports .obj
            - my obj2json.py outputs JSON
            - Just discovered https://andrewmarsh.com/software/poly3d-web/, which is very nice.
                It can export .obj, as well as a couple of other formats
            - Python scripts that generate grids? what do I have? do they produce obj?
            - Python scripts that generate puzzles & solutions given a grid? What do I have? Do they use "enriched" obj or
                something separate?
              - [ ] Need to find those scripts! Not sure if I have any that specifically work on 3D data, but the
                algorithm should be very similar. It's still a 1D path on a 2D surface, not a volume as such.
                - Maybe all I ever had for that was Krazydad's algorithms, in Python, Java or Processing.
                    Anyway I can write my own. The question is what format to input. We'll output JSON -- not Stemkowski's,
                    but the kind that obj2json.py already outputs. See above for encoding of puzzles and solutions.
                - [ ] ** Check IDrive-Sync/Lars/programming/SlitherlinkNGons3D/SlitherlinkNGons3D.pde! (Processing code)
                  Yes, this is puzzle generator code that I adapted from Krazydad. How far did I get with it in converting
                    to 3D? Shall I adapt it more or write my own? What format does it output?
        - [ ] programs that take data input (e.g. grids and/or puzzles)
            - [x] existing code to load from the files (in the web app and/or in other programs)
            - The web app may take JSON? Does my old code use this?
                - [x] If the web app does this, it will need to convert it to the Grid data structure (enriching as needed).
                - [ ] OK, in slitherlink3D-2018/js/sl3D.js, a data file like data/phe-T.json is loaded, and in
                    importData(), we can see how the JSON properties are used. Not sure how complete that was...
            - Python puzzle generator?
                - [ ] need to find Python (or Java??) scripts that aren't currently in this repo and integrate them,
                    so I can see what I have.
    - I think for now we'll follow the model of krazydad.com, in which
        - The user can select grid styles, and select a puzzle for that grid from a list
            - They can also press a "next" button which will take them along a preset path of puzzles, of
                equal or increasing difficulty (but unlike on krazydad.com, it can lead them to other varieties
                 of grids)
        - But the user can't provide their own grids or puzzles
        - The web app won't generate new puzzles (for now)
        - The conclusion regarding formats & data flow is, the web app doesn't need to accept data from users at all.
    - [ ] ** Having decided that we'll continue using JSON and OBJ, document the formats in an easy-to-find place.
        - [x] JSON
            - [x] metadata such as name, category, acknowledgements/source, comments
            - [x] board/grid data
            - [x] puzzle (and solution) data
            - [x] sources and sinks of this format
        - [ ] OBJ
            - [ ] metadata such as name, category, acknowledgements/source, comments
            - [ ] board/grid data
            - [ ] puzzle (and solution) data
            - [ ] sources and sinks of this format



- [~] It would be good if we can use a URL, possibly including parameters, to specify a particular grid and puzzle.
    - [ ] But we don't want the web page to have to reload when switching grids or puzzles. Currently it does reload, but for better polish, we'll fix that.

- implement loading from files of:
    - grids
        - Note! We already have a LOT of polyhedra defined in slitherlink3D-old/js/polyhedra.js,
        thanks to Hart and Stemkowski.
        Data from the website "Virtual Polyhedra: The Encyclopedia of Polyhedra" by George W. Hart
          http://www.georgehart.com/virtual-polyhedra/vp.html
        Converted to JSON by Lee Stemkoski. Which is probably much easier to work with.
    - puzzles
        - (with solutions)
- [x] implement feedback on puzzles
    - [~] detect when user has correct solution, and celebrate
    - [x] choose and load next puzzle (let user do so when ready)
        - I like the idea of progressing: go thru Platonics, Archimedean solids, prisms & antiprisms,
                Johnson solids, Catalan solids, zonohedra... but currently we progress by number of faces, which is also nice for steadily increasing complexity; and it takes the user through all the families.
            - [ ] more puzzles on the bigger polyhedra?


- graph theory regarding slitherlink circuits: see ideas/graph-cycles.txt.

- [ ] maybe enhance underwater skymap with some bubbles coming up out of the deep; and shadows of large creatures
    swimming in the depths; and maybe a swarm of small fish passing above (shadows on the puzzle!)
- [ ] improve how vertices and edges interact visually, especially when edges meeting at the same vertex 
  are different colors: How about having the edges stop short of both vertices. E.g. if an edge goes between
  v1 and v2, then draw it from v1 + normalize(v2 - v1) * vertexBallRadius * 1.5 to v2 - normalize(v2 - v1) * vertexBallRadius * 1.5. 
- [ ] Try some transparency on the faces? Let the user control it with a live slider or settings?
