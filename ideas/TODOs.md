- [ ] move some of the sceneManager.setup*() calls in main() into a single
  a single sceneManager.setupStuff() function.
- [ ] show some visual indication when puzzle is solved successfully.
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
  - [ ] A simpler option: animate the camera a bit. Spin-orbit the camera around and zoom out/in a bit.
    - Maybe also do something with the direct and ambient lighting...
- [ ] try to refactor loadPolyhedronFromJSON() to not pass back so many random parameters.
  - [ ] similarly createPolyhedron().
- [ ] there still appears to be unused code after the refactor... especially return values.
  - [~] also return*Data() in GameState
  - [ ] unused members in SceneManager
- [ ] vertex labels appear to be stretched wide for single-digit numbers.
- [x] display solution (don't just set the edge states; or maybe even don't change the edge states
  but just the color of the edge geometry!)
  - [ ] make sure we're not unnecessarily overwriting userGuess anywhere else.
  - [ ] stop displaying solution when we turn off "display solution"
- [ ] Debugging mode could show face IDs, or at least log them when you click on a face.
- [ ] Add a "Done" button, at which point we check the user's guesses and
    give feedback on whether they were correct.
  - [ ] highlight wrong guesses in red
  - [ ] tell them if they have failed to make a loop
- [ ] Later on, add a "show solution" button, and maybe a "hint" button.
- [ ] Eventually, we'll need a button to go on to the next puzzle, or select
  another puzzle.
  - [ ] when we do, we'll need to be careful to 'dispose()' of THREE.js objects,
    - and also remove bidirectional references.
  - [ ] somehow we'll need to implement a catalogue of available grids.
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
    
- [ ] settle on a format for puzzles and solutions.
    - [ ] What do we have so far?
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
    - [ ] So let's settle on a variation of the above:
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
    - [ ] So that gives us a JSON representation for puzzles and solutions. In regard to the grids, I guess
      we're good with the JSON format emitted by obj2json.py, although it calls faces "cells,"
      which is inconsistent with our usage elsewhere.
      In one sense, "cell" is more consistent with 2D Slitherlink puzzles. I guess we'll leave it as is.
- Handle errors more gracefully, e.g. in loadPolyhedronFromJSON().
- [ ] display name and category of polyhedron (grid) on screen. This will add some "atmosphere."
    - [ ] Is this encoded in the JSON?
    - [ ] maybe associate a color (scheme) with each polyhedron, and category, for more atmosphere?
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
            - [ ] existing code to load from the files (in the web app and/or in other programs)
            - The web app may take JSON? Does my old code use this?
                - [ ] If the web app does this, it will need to convert it to the Grid data structure (enriching as needed).
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
        - [ ] JSON
            - [ ] metadata such as name, category, acknowledgements/source, comments
            - [ ] board/grid data
            - [ ] puzzle (and solution) data
            - [ ] sources and sinks of this format
        - [ ] OBJ
            - [ ] metadata such as name, category, acknowledgements/source, comments
            - [ ] board/grid data
            - [ ] puzzle (and solution) data
            - [ ] sources and sinks of this format



- It would be good if we can use a URL, possibly including parameters, to specify a particular grid and puzzle.
    But we don't want the web page to have to reload when switching grids or puzzles.

- implement loading from files of:
    - grids
        - Note! We already have a LOT of polyhedra defined in slitherlink3D-old/js/polyhedra.js,
        thanks to Hart and Stemkowski.
        Data from the website "Virtual Polyhedra: The Encyclopedia of Polyhedra" by George W. Hart
          http://www.georgehart.com/virtual-polyhedra/vp.html
        Converted to JSON by Lee Stemkoski. Which is probably much easier to work with.
    - puzzles
        - (with solutions)
- implement feedback on puzzles
    - detect when user has correct solution, and celebrate
    - choose and load next puzzle (let user do so when ready)
        - I like the idea of progressing: go thru Platonics, Archimedean solids, prisms & antiprisms,
                Johnson solids, Catalan solids, zonohedra...
            - more puzzles on the bigger polyhedra


- graph theory regarding slitherlink circuits: see ideas/graph-cycles.txt.

- [ ] maybe enhance underwater skymap with some bubbles coming up out of the deep; and shadows of large creatures
    swimming in the depths; and maybe a swarm of small fish passing above (shadows on the puzzle!)
- [ ] improve how vertices and edges interact visually, especially when edges meeting at the same vertex 
  are different colors: How about having the edges stop short of both vertices. E.g. if an edge goes between
  v1 and v2, then draw it from v1 + normalize(v2 - v1) * vertexBallRadius * 1.5 to v2 - normalize(v2 - v1) * vertexBallRadius * 1.5. 
- [ ] Try some transparency on the faces? Let the user control it with a live slider or settings?

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
