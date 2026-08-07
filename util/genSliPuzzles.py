"""Generate Slitherlink3D puzzles (in JSON) for a given grid (input from JSON).
Usage: python3 genSliPuzzles.py [--quiet|--verbose] [--display=N]
           [--existing=FILE] myGrid.json [numPuzzles]
Output is written to stdout; diagnostic/progress messages go to stderr.
--quiet keeps only errors, warnings and the outcome; --verbose adds per-edge
detail. See VERBOSITY.
--display=N asks for N extra puzzles under "displayPuzzles" -- shown off on the
title screen, never handed to a player. See generate_puzzles.
--existing=FILE keeps the puzzles already in FILE and generates around them,
which is how display puzzles are added to a grid without churning the puzzles
people may have bookmarked. See load_existing_puzzles.
For JSON format specifications, see docs/json-format.md."""
import itertools, json, random, sys, math
from collections import Counter

import matplotlib.pyplot as plt
import networkx as nx
from networkx.algorithms.isomorphism import GraphMatcher, categorical_node_match
from compas.datastructures import Mesh
from compas.geometry import Point, length_vector
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Our local module
import grid_topology
import json_format
import slisolver

# Global variables
grid_json: dict|None = None
grid_id: str|None = None
# Path to the grid file, from the command line. Not read straight out of
# sys.argv, because the flags may come before or after it.
grid_path: str|None = None
num_puzzles_wanted: int = 1
# How many display-only puzzles to generate as well (--display=N). One is
# enough: the title screen shows a single loop per grid.
num_display_wanted: int = 1
# Path given by --existing=FILE, whose puzzles are kept as-is; None otherwise.
existing_puzzles_path: str|None = None
puzzles_output: dict = {}
# Display-only puzzles, generated exactly like the playable ones (authentic,
# uniquely solvable) but kept in a separate list so that they can never reach a
# player. output_puzzles attaches them under "displayPuzzles", and only if we
# managed to produce any -- an absent key means the title screen shows that
# grid's clues without a loop. See docs/json-format.md.
display_puzzles: list = []

grid_vertices: list|None = None
num_vertices: int = 0
grid_faces: list|None = None
num_faces: int = 0

# The COMPAS Mesh represents the grid, and has colored faces.
mesh: Mesh|None = None
# The dual graph has a node for each face in the grid, and helps compute their connectedness.
dualG: nx.Graph|None = None
# The structure of these graphs will not change, only the colors of faces and edges.

puzzles: list = []
solution: list[int] = []

# for Matplotlib
fig: Figure|None = None
ax: Axes3D|None = None
poly: Poly3DCollection|None = None

# Puzzle generation state. The face coloring and its bookkeeping live in a
# RegionColoring, built once the mesh exists; see build_graphs.
coloring = None
# The solid's symmetries, computed on first use by face_symmetries().
symmetries_cache = None
# Symbols for our colors, so that we don't risk typos.
red = "red"
blue = "blue"
opposite_color = {red: blue, blue: red}

# Give up on a single uniqueness check after this many seconds, treating the
# clue set as not proven unique. Solver search times have a heavy tail (a rare
# pathological clue set can take minutes where most take milliseconds); this
# bounds them. The cost is occasionally using more clues than strictly
# minimal, or discarding a region — never an unverified puzzle.
SOLVER_TIME_BUDGET = 20.0

# How much "suppose this edge were filled..." reasoning a puzzle may require.
# 0 demands that plain propagation finish it, which needs a lot of clues and
# makes easy puzzles; 1 allows one supposition at a time, which is what a
# competent player does routinely; 2 or more starts to feel like guessing.
# This is the difficulty dial: see cut_clues.
LOOKAHEAD_DEPTH = 1

# How many times to start over with fresh regions when a solution turns out to
# admit no deductively-solvable clue set, before giving up on that puzzle.
MAX_REGION_ATTEMPTS = 15


# How chatty to be on stderr:
#   0 -- errors, warnings, and the outcome of the run  (--quiet)
#   1 -- plus one-off progress: mesh built, puzzle N started, and so on
#   2 -- plus per-edge/per-face/per-step detail        (--verbose)
# Level 2 is genuinely voluminous: fix_boring_neighborhoods logs for every edge
# it examines, and capturing that once produced multi-gigabyte log files, so it
# is no longer part of the default output.
VERBOSITY = 1


def backend_can_display():
    """True if the current matplotlib backend can actually show a figure.

    Which decides whether the progress redraws are worth doing at all: see
    update_display.
    """
    try:
        from matplotlib.backends import backend_registry, BackendFilter
        non_interactive = backend_registry.list_builtin(BackendFilter.NON_INTERACTIVE)
    except ImportError:
        # matplotlib < 3.9, where the registry doesn't exist yet. (The attribute
        # this falls back on is deprecated from 3.9 and gone in 3.11, which is
        # why it's only the fallback.)
        from matplotlib.rcsetup import non_interactive_bk as non_interactive
    return plt.get_backend().lower() not in {b.lower() for b in non_interactive}


# Decided once: the backend comes from the environment (run_gen.py sets
# MPLBACKEND=Agg for headless runs) and doesn't change mid-run.
DISPLAY_IS_LIVE = backend_can_display()


def log(*args, level=1, **kwargs):
    """Print a diagnostic/progress message to stderr, if VERBOSITY allows it.

    stdout is reserved for the generated puzzle JSON, so that output can
    be piped or redirected cleanly; everything else goes through here.

    `level` says how chatty this particular message is; see VERBOSITY for
    what the levels mean. Messages at level 0 are always printed."""
    if level <= VERBOSITY:
        print(*args, file=sys.stderr, **kwargs)


def require_properties(properties):
    """Ensure that all required properties are present in the grid JSON."""
    for prop in properties:
        if prop not in grid_json:
            log(f"Error: Missing required property '{prop}' in grid JSON.", level=0)
            sys.exit(1)


def on_key_press(event, mesh):
    """Process key press events."""
    log('User pressed ', event.key)
    sys.stderr.flush()
    if event.key == 'x':
        update_display(mesh)


def setup_display(mesh):
    """Set up the display for the mesh."""
    global fig, ax, poly
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    fig.canvas.mpl_connect('key_press_event',
                           lambda event: on_key_press(event, mesh))
    # plt.ion() # enable interactive mode

    # draw faces
    ax.clear()
    # Build the Poly3DCollection and its labels once.
    faces = [[mesh.vertex_coordinates(vkey) for vkey in mesh.face_vertices(fkey)]
             for fkey in mesh.faces()]

    poly = Poly3DCollection(faces, edgecolor='gray', alpha=0.8, linewidths=2)
    ax.add_collection3d(poly)

    # Label each vertex
    for vkey in mesh.vertices():
        (x, y, z) = mesh.vertex_coordinates(vkey)
        ax.text(x * 1.1, y * 1.1, z * 1.1, str(vkey))

    # TODO: would be nice to be able to toggle display of face/vertex IDs by keyboard.
    # # Label each face at its centroid
    # for fkey in mesh.faces():
    #     pts = [mesh.vertex_coordinates(vkey) for vkey in mesh.face_vertices(fkey)]
    #     cx, cy, cz = centroid_points(pts)
    #     # Move these away from origin.
    #     factor = 1.00
    #     ax.text(cx * factor, cy * factor, cz * factor, str(fkey),
    #             color='black', fontsize=8, ha='center', va='center')

    (xs, ys, zs) = zip(*[mesh.vertex_coordinates(v) for v in mesh.vertices()])
    ax.auto_scale_xyz(xs, ys, zs)
    ax.set_box_aspect([1, 1, 1])

    # Remove grid and axes
    plt.grid(b=None)
    plt.axis('off')


def update_display(mesh):
    """Update the display with the current mesh, if anyone can see it.

    Called after every region repair step, to animate the coloring as it
    settles. Under a non-interactive backend that animation goes nowhere --
    plt.show() can't display it -- but the work is real: on the snub
    dodecahedron this ran 6367 times at 26 ms each, 95% of the whole run,
    rebuilding a Poly3DCollection and calling plt.draw() for a figure that was
    then thrown away. Since run_gen.py forces Agg, that was every batch run.
    """
    global fig, ax

    if not DISPLAY_IS_LIVE:
        return

    colors = [mesh.face_attribute(fkey, 'color') for fkey in mesh.faces()]
    poly.set_facecolor(colors)

    plt.draw()
    # print("Displaying mesh...")
    plt.pause(0.001)  # brief pause to refresh display


def log_mesh(mesh):
    """Log faces, edges of built mesh for debugging."""
    for (fkey) in mesh.faces():
        edges = ", ".join(str(ekey) for ekey in mesh.face_halfedges(fkey))
        log(f"Face {fkey}: {edges}", level=2)
    for (ekey) in mesh.edges():
        # Which two faces are connected by this edge?
        (f1, f2) = mesh.edge_faces(ekey)
        log(f"Edge {ekey}: f{f1} <-> f{f2}", level=2)



def build_graphs():
    """Build a graph (and its dual) from the faces and vertices loaded from the grid JSON."""
    global mesh, dualG, coloring
    # Verified that the vertex IDs are the same ones we use in the javascript game, i.e.
    #   the indices vertices. Because the game expects the solution to use those IDs.
    mesh = Mesh.from_vertices_and_faces(grid_vertices, grid_faces)
    # That was easy!
    log(f"Built mesh. F: {mesh.number_of_faces()}, V: {mesh.number_of_vertices()}, E: {mesh.number_of_edges()}")
    # log_mesh(mesh)
    normalize_vertices()

    # Now make a dual graph in nx, with nodes for the faces of the grid.
    # This will be used for connectedness queries.
    dualG = nx.Graph()
    for f in mesh.faces():
        # print(f"Adding face {f} of type {type(f)} to dual graph.")
        dualG.add_node(f) # We'll color this face node later.
        # The dual graph has an edge from each face to each of its neighbors.
        for nbr in mesh.face_neighbors(f):
            dualG.add_edge(f, nbr)
    log(f"Built dual graph. V: {dualG.number_of_nodes()} nodes, E: {dualG.number_of_edges()} edges.")

    # One coloring for the whole run: each puzzle attempt repaints it from
    # scratch (RegionColoring.generate), so there is nothing to carry over.
    coloring = RegionColoring(mesh, dualG)

    # Debugging:
    # for vertex in mesh.vertices():
    #     print(vertex)


def normalize_vertices():
    """Adjust vertices to be centered about the origin, and about 1 unit away."""
    # Compute average vertex position.
    vertex_position_total = Point(0, 0, 0)
    for v in mesh.vertices():
        vertex_position_total += mesh.vertex_point(v)
    avg_vertex_position = vertex_position_total / num_vertices
    # print(f"Average vertex position before normalizing: {avg_vertex_position}")

    # Adjust displacement, and compute distance.
    max_distance = 0
    for v in mesh.vertices():
        p = mesh.vertex_point(v) - avg_vertex_position
        mesh.set_vertex_point(v, p)
        # Squared distance from origin.
        max_distance = max(max_distance, length_vector(p))
    log(f"Max distance from origin before normalizing: {max_distance}")

    for v in mesh.vertices():
        mesh.set_vertex_point(v, mesh.vertex_point(v) / max_distance)


def process_grid_json():
    """Validate the grid JSON data and put into efficient data structures."""
    global grid_json, grid_id, grid_faces, num_faces, grid_vertices, num_vertices, puzzles_output
    # Validate required fields per json-format.md specification
    require_properties(["gridId", "gridName", "vertices", "faces"])

    grid_id = grid_json["gridId"]
    puzzles_output["gridId"] = grid_id
    puzzles_output["puzzles"] = []

    grid_vertices = grid_json["vertices"]
    num_vertices = len(grid_json["vertices"])
    # Vertex positions will be used only for debugging display.

    grid_faces = grid_json["faces"]
    num_faces = len(grid_faces)

    # Deallocate the grid JSON data.
    grid_json = None
    build_graphs()


def load_grid_file():
    """Load the grid from the specified JSON file."""
    global grid_json
    try:
        grid_json = json.load(open(grid_path, "r"))
    except FileNotFoundError:
        log(f"Error: File '{grid_path}' not found.", level=0)
        sys.exit(1)
    except json.decoder.JSONDecodeError:
        log(f"Error: File '{grid_path}' is not valid JSON.", level=0)
        sys.exit(1)
    process_grid_json()


def usage():
    """Print usage message and exit."""
    log("Usage: python3 genSliPuzzles.py [--quiet|--verbose] [--display=N] "
        "[--existing=FILE] myGrid.json [numPuzzles]", level=0)
    log("  -q, --quiet      only errors, warnings and the outcome of the run", level=0)
    log("  -v, --verbose    add per-edge/per-face detail (very wordy)", level=0)
    log("  --display=N      also generate N display-only puzzles (default "
        f"{num_display_wanted})", level=0)
    log("  --existing=FILE  keep the puzzles already in FILE, and generate "
        "puzzles distinct from them", level=0)
    sys.exit(1)


def option_value(arg, name):
    """The value of a --name=value option, or None if arg isn't that option."""
    prefix = f"--{name}="
    return arg[len(prefix):] if arg.startswith(prefix) else None


def process_args():
    """Process command-line arguments."""
    global num_puzzles_wanted, num_display_wanted, existing_puzzles_path
    global grid_path, VERBOSITY
    positional = []
    for arg in sys.argv[1:]:
        if arg in ("-q", "--quiet"):
            VERBOSITY = 0
        elif arg in ("-v", "--verbose"):
            VERBOSITY = 2
        elif (value := option_value(arg, "display")) is not None:
            try:
                num_display_wanted = int(value)
            except ValueError:
                log(f"Error: --display wants a number, not '{value}'.", level=0)
                usage()  # exits
            if num_display_wanted < 0:
                log(f"Error: --display can't be negative.", level=0)
                usage()  # exits
        elif (value := option_value(arg, "existing")) is not None:
            existing_puzzles_path = value
        elif arg.startswith("-"):
            log(f"Error: unrecognized option '{arg}'.", level=0)
            usage()  # exits
        else:
            positional.append(arg)

    if (len(positional) < 1 or len(positional) > 2):
        usage() # exits
    grid_path = positional[0]
    if (len(positional) == 2):
        num_puzzles_wanted = int(positional[1])


def load_existing_puzzles():
    """Adopt the puzzles from --existing=FILE, if one was given.

    Its puzzles go into the output as they stand, and count as already generated,
    so anything produced this run is distinct from them (up to rotation and
    reflection -- see already_generated). That makes it safe to add a display
    puzzle to a grid that already ships puzzles: the playable ones come out
    byte-identical, so nobody's bookmarked ?puzzle= number moves, and the new
    loop can't be the answer to one of them.

    Any displayPuzzles already in the file are DISCARDED, on the grounds that
    asking for display puzzles is a request to make new ones. Pass --display=0
    to keep the file's playable puzzles and drop its loop.
    """
    global existing_puzzles_path
    if existing_puzzles_path is None:
        return

    try:
        existing = json.load(open(existing_puzzles_path, "r"))
    except FileNotFoundError:
        log(f"Error: --existing file '{existing_puzzles_path}' not found.", level=0)
        sys.exit(1)
    except json.decoder.JSONDecodeError:
        log(f"Error: --existing file '{existing_puzzles_path}' is not valid JSON.",
            level=0)
        sys.exit(1)

    # A mismatched gridId means the puzzles describe a different solid: its clues
    # are indexed by ITS faces, so keeping them would silently corrupt this grid's
    # file. (build_catalogue.py warns about the same mismatch and skips the file.)
    if existing.get("gridId") != grid_id:
        log(f"Error: '{existing_puzzles_path}' has gridId "
            f"'{existing.get('gridId')}', but this grid is '{grid_id}'.", level=0)
        sys.exit(1)

    kept = existing.get("puzzles", [])
    puzzles_output["puzzles"].extend(kept)
    log(f"Keeping {len(kept)} existing puzzle(s) from {existing_puzzles_path}.")


# How many colorings to grow and discard before giving up on a grid.
#
# Each attempt is one pass over the faces plus two connectivity searches, so this
# is cheap; the limit exists to fail loudly rather than to ration work. Since
# grow_region refuses the faces that would pinch the boundary, rather than letting
# a pinch spoil the finished coloring, the only thing left to discard an attempt
# for is a disconnected second region -- so attempts rarely fail at all. Measured
# on dbD, the worst case for the old approach: 60 of 60 attempts now succeed.
COLORING_ATTEMPT_LIMIT = 2000

# How many passes over the faces improve_region may make looking for a flip that
# lengthens the loop or reduces the untouched area. It stops early as soon as a
# pass finds nothing, so this is only the ceiling -- there to keep a local search
# from becoming the sort of quiet time sink the old repair loop turned out to be.
IMPROVEMENT_ROUNDS = 12

# improve_region stops once the biggest untouched patch is down to
# faces / QUIET_PATCH_DIVISOR. A share rather than a fixed number, because what
# counts as a big blank area depends on how much surface there is: 4 untouched
# faces out of 120 is a speck, out of 12 it is a third of the solid.
QUIET_PATCH_DIVISOR = 20


class RegionColoring:
    """The red/blue two-coloring of the faces that a puzzle's solution comes from.

    The loop is the boundary between the two colors, so generating a puzzle
    starts by painting the faces: randomly at first, then repaired until each
    color forms one connected region of a reasonable size with no dull
    all-one-color neighborhoods. See generate and paint_regions.

    This owns the state that used to live in module globals -- which color still
    needs a connectedness check, and how many faces each color has. Holding it
    here rather than at module level is what lets the clue code below be called
    with a mesh of the caller's choosing, so the tests no longer have to reach
    in and monkeypatch a module global to test anything downstream.

    The face counts are DERIVED from the mesh on demand rather than tallied as
    faces are painted. Tallying is what the module globals did, and they got it
    wrong twice over: paint_face incremented the new color's count without
    decrementing the old one, and randomize_face_colors added to the counts
    without first resetting them. So the "totals" were really a count of paint
    operations, drifting further above num_faces on every attempt, and since
    adjust_populations is the one thing that reads them, its "keep each color to
    at least a third of the faces" rule quietly stopped firing after the first
    attempt. Deriving the counts costs a pass over the faces in a routine that
    already does connected-components work, and it cannot get out of step.
    """

    def __init__(self, mesh, dualG):
        self.mesh = mesh
        self.dualG = dualG
        self.num_faces = mesh.number_of_faces()
        # Face adjacency, built once. Asking the mesh for a face's neighbors is
        # the innermost operation of the whole painter, and improve_region calls
        # it thousands of times per puzzle.
        self.adjacency = grid_topology.face_adjacency(
            [mesh.face_vertices(fkey) for fkey in mesh.faces()])
        # Whether each color's region still needs its connectedness checked.
        # Painting a face one color can disconnect the other color, so painting
        # sets the OTHER color's flag; see paint_face.
        self.red_needs_check = False
        self.blue_needs_check = False

    def count(self, color):
        """How many faces currently have the given color."""
        return sum(1 for fkey in self.mesh.faces()
                   if self.mesh.face_attribute(fkey, "color") == color)

    def randomize_face_colors(self):
        """Assign red or blue randomly to each face."""
        for fkey in self.mesh.faces():
            color = random.choice([red, blue])
            self.mesh.face_attribute(fkey, "color", color)
            self.dualG.nodes[fkey]["color"] = color

    def paint_face(self, fkey, color):
        """Paint the given face the given color.
        Updates the dual graph and *_needs_check as needed."""
        self.mesh.face_attribute(fkey, "color", color)
        self.dualG.nodes[fkey]["color"] = color
        if color == red:
            self.blue_needs_check = True
        else:
            self.red_needs_check = True

    def paint_random_faces(self, color, how_many):
        """Change specified number of random faces to the given color.
        Only faces that weren't already that color are chosen.

        This used to draw a random face from a freshly built list(mesh.faces())
        and retry until it hit one of the other color -- rebuilding that list on
        every draw, and drawing repeatedly as the supply of candidates shrank.
        Since the faces it wants are exactly the ones not already this color,
        one sample of that set does the same job: the result is still a
        uniformly random set of distinct faces.
        """
        log(f"Painting {how_many} faces {color}.", level=2)
        if how_many <= 0:
            return
        candidates = [fkey for fkey in self.mesh.faces()
                      if self.mesh.face_attribute(fkey, "color") != color]
        # adjust_populations never asks for more than are available -- it asks
        # for at most a third of the faces, and every face it would count
        # against that is already this color -- but clamp rather than let
        # random.sample raise if some future caller is less careful.
        for fkey in random.sample(candidates, min(how_many, len(candidates))):
            self.paint_face(fkey, color)

    def adjust_populations(self):
        """If the number of blue or red faces is too low, increase it."""
        total_red = self.count(red)
        if total_red < self.num_faces / 3 or total_red < 1:
            self.paint_random_faces(red, round(self.num_faces / 3 - total_red))
            return
        total_blue = self.count(blue)
        if total_blue < self.num_faces / 3 or total_blue < 1:
            self.paint_random_faces(blue, round(self.num_faces / 3 - total_blue))

    def paint_neighbor_face(self, component, color):
        """Expand the given connected component, which consists of faces of the given color,
        by painting a neighbor the same color.
            component - A set containing the face keys in the connected component.
            color - The color to paint the new neighbor face."""
        # Convert set to a list for choosing randomly.
        faces = list(component)
        while True:
            face_to_grow = random.choice(faces)
            # Pick a neighbor of face_to_grow.
            neighbor = random.choice (self.mesh.face_neighbors(face_to_grow))
            # If the neighbor is already this color, try another neighbor.
            if self.mesh.face_attribute(neighbor, "color") != color:
                # If the neighbor is the same color, paint it the same color..
                self.paint_face(neighbor, color)
                return
            # Otherwise, pick a new face and a new neighbor.

    def color_components(self, color):
        """The connected groups of faces of the given color, as a list of sets.

        A plain breadth-first search over the mesh's face adjacency. This used to
        build a networkx subgraph view of the dual graph and call
        nx.connected_components on it -- once for every single face painted --
        and profiling put that at the top of the generator's cost by a wide
        margin: 8.7 million connected_components calls and 2.2 million subgraph
        constructions in one 240-second run on dtC, about two thirds of the total
        time. The graph has at most a few hundred nodes, so the library's
        generality costs far more than the search it performs.
        """
        remaining = {fkey for fkey in self.mesh.faces()
                     if self.mesh.face_attribute(fkey, "color") == color}
        components = []
        while remaining:
            group = {remaining.pop()}
            stack = list(group)
            while stack:
                for nbr in self.mesh.face_neighbors(stack.pop()):
                    if nbr in remaining:
                        remaining.discard(nbr)
                        group.add(nbr)
                        stack.append(nbr)
            components.append(group)
        return components

    def ensure_connected(self, color):
        """Check whether faces of the given color are connected.
        If not, add paint until they are.
        Return True if any faces were painted, False if the faces were already connected.

        This inner loop is self-limiting: each repair paints one more face this
        color, and once every face is one color it is trivially connected. So the
        cap that matters is on the repair PASSES in paint_regions, not here.
        """
        log(f"Ensuring connectedness of {color} faces.", level=2)
        faces_painted = False
        while True:
            components = self.color_components(color)
            is_connected = len(components) <= 1

            log(f"Connectedness of {sum(len(c) for c in components)} {color}: "
                f"{is_connected}.", level=2)
            update_display(self.mesh)

            if is_connected:
                return faces_painted

            # At this point I had thought to pick a face adjacent to one of the connected groups.
            # But it may be just as effective (and is easier) to just paint a random face.
            # paint_random_faces(color, 1)
            # No ... that seems to take interminable iterations to get to a suitable state.
            self.paint_neighbor_face(min(components, key=len), color)
            faces_painted = True

            update_display(self.mesh)

    def fix_boring_neighborhoods(self):
        """Disrupt neighborhoods of where faces are all the same color."""
        mesh = self.mesh
        # Set all faces to "boring".
        for fkey in mesh.faces():
            mesh.face_attribute(fkey, "boring", True)
        for ekey in mesh.edges():
            # For every edge, get the two faces it connects.
            (f1, f2) = mesh.edge_faces(ekey)
            log(f"Checking edge {ekey} (f{f1}, f{f2})...", level=2)
            if (mesh.face_attribute(f1, "color") != mesh.face_attribute(f2, "color")):
                log(f"Edge {ekey} has different colors on faces {f1} and {f2}.", level=2)
                # Faces that have different-colored neighbors are not "boring".
                mesh.face_attribute(f1, "boring", False)
                mesh.face_attribute(f2, "boring", False)

        # Now check for boring faces with all-boring neighbors.
        num_boring_faces = 0
        for fkey in mesh.faces():
            if mesh.face_attribute(fkey, "boring"):
                log(f"Boring face {fkey} is {mesh.face_attribute(fkey, 'color')}.", level=2)
                num_boring_faces += 1
                # Check if any of the neighbors are also boring.
                for nbr in mesh.face_neighbors(fkey):
                    if mesh.face_attribute(nbr, "boring"):
                        # We have two adjacent boring faces.
                        log(f"Boring face {fkey} has a boring neighbor {nbr}.", level=2)
                        # Paint one of them the opposite color.
                        f_to_color = random.choice([fkey, nbr])
                        old_color = mesh.face_attribute(f_to_color, "color")
                        log(f"  Painting face {f_to_color} {opposite_color[old_color]}",
                            level=2)
                        self.paint_face(f_to_color, opposite_color[old_color])
                        # Now this face is no longer boring, nor are (most of?) its neighbors.
                        mesh.face_attribute(f_to_color, "boring", False)
                        for nbr_of_changed in mesh.face_neighbors(f_to_color):
                            mesh.face_attribute(nbr_of_changed, "boring", False)
                        # Stop processing this face. Check other boring faces (continue outer loop).
                        break

    def boundary_degree(self, region, vkey):
        """How many of vkey's edges would be on the loop, if `region` were one of
        the two colors. An edge is on the loop when exactly one of its two faces
        is inside."""
        return sum(1 for nbr in self.mesh.vertex_neighbors(vkey)
                   if len({fkey for fkey in self.mesh.edge_faces((vkey, nbr))
                           if fkey is not None} & region) == 1)

    def would_pinch(self, region, fkey):
        """True if adopting `fkey` would leave one of ITS vertices with more than
        two loop edges, i.e. a boundary that crosses itself there.

        Only fkey's own vertices need checking: adopting a face changes which
        edges are on the loop solely around that face, so no other vertex's degree
        can change.
        """
        grown = region | {fkey}
        return any(self.boundary_degree(grown, vkey) not in (0, 2)
                   for vkey in self.mesh.face_vertices(fkey))

    def grow_region(self, target):
        """A random connected set of up to `target` faces, grown one face at a
        time, always at the region's TIPS and never through a pinch.

        Two choices here, and both were measured rather than guessed.

        Growing at the tips -- preferring frontier faces with the fewest
        neighbours already inside -- rather than anywhere on the frontier. It
        matters much more than it sounds, because the loop IS this region's
        boundary: filling hollows as readily as extending limbs rounds the region
        off, and a round region's boundary is a short curl around one area. That
        is what produced dbD's first puzzle with an entire hemisphere of 0 clues.

        Refusing a face that would pinch, rather than discarding the whole attempt
        afterwards. Dendritic regions keep touching themselves at a vertex, and
        the earlier code could only detect that at the end and start over -- which
        on dbD failed 2000 attempts running, forcing raggedness down to nearly
        zero and back to compact blobs. Testing each candidate first turns that
        around completely; measured on dbD, 60 attempts out of 60 now yield a
        valid coloring where fully ragged blind growth yielded none, the loop goes
        from 23 edges to 58 of a possible 62, and the largest patch of faces the
        loop never touches falls from 56 to 4.

        A refusal is only true of the region as it stands, so when a face IS
        adopted, every face sharing a vertex with it gets another chance: those
        are exactly the faces whose vertex degrees just changed. Growth therefore
        flows around an obstacle instead of stopping at it.

        Returns fewer than `target` faces if it runs out of room, which is fine --
        paint_regions judges the result on its merits, not its size. sorted()
        appears only so the choice is reproducible under a fixed seed, since set
        iteration order is not.
        """
        region = {random.choice(list(self.mesh.faces()))}
        frontier = set(self.mesh.face_neighbors(next(iter(region))))
        refused = set()
        while len(region) < target:
            available = frontier - refused
            if not available:
                break

            def already_inside(fkey):
                return sum(1 for nbr in self.mesh.face_neighbors(fkey)
                           if nbr in region)

            fewest = min(already_inside(fkey) for fkey in available)
            pick = random.choice(sorted(fkey for fkey in available
                                        if already_inside(fkey) == fewest))
            if self.would_pinch(region, pick):
                refused.add(pick)
                continue

            frontier.discard(pick)
            region.add(pick)
            for vkey in self.mesh.face_vertices(pick):
                refused -= set(self.mesh.vertex_faces(vkey))
            for neighbor in self.mesh.face_neighbors(pick):
                if neighbor not in region:
                    frontier.add(neighbor)
        return region

    def loop_length(self, region):
        """How many edges the loop would have, if `region` were one color."""
        return sum(1 for ekey in self.mesh.edges()
                   if len({fkey for fkey in self.mesh.edge_faces(ekey)
                           if fkey is not None} & region) == 1)

    def largest_quiet_patch(self, region):
        """The size of the biggest connected group of faces the loop would not
        touch at all: a field of 0 clues with nothing happening in it.

        This, rather than the total number of untouched faces, is what makes a
        puzzle look dull -- scattered single 0s are fine and even welcome, while
        one big blank area is the defect. dbD's first generated puzzle had 55 such
        faces in a single patch, a whole visible hemisphere of 0s.

        The grouping is grid_topology's, which is also what catalogue_report and
        sweep_grids use to measure a puzzle already on disk. Two definitions of
        this would drift apart silently, and it is now a quality gate;
        test_same_patch_measure_as_grid_topology pins the two together.
        """
        quiet = [fkey for fkey in self.mesh.faces()
                 if all((nbr in region) == (fkey in region)
                        for nbr in self.mesh.face_neighbors(fkey))]
        return grid_topology.largest_group(quiet, self.adjacency)

    def quiet_patch_allowance(self):
        """How big an untouched patch is acceptable, so improve_region knows when
        to stop. A share of the faces, and never less than one."""
        return max(1, self.num_faces // QUIET_PATCH_DIVISOR)

    def improve_region(self, region):
        """Hill-climb a valid region until its biggest untouched patch is small
        enough, by flipping one face at a time and keeping only flips that help.

        Growth alone leaves a blob with an interior the boundary never reaches, so
        a grown region can score badly on untouched area even when its loop is a
        respectable length. This fixes that after the fact: try flipping single
        faces, in either direction, and keep a flip when the result is still valid
        and either shrinks the biggest untouched patch or -- at equal patch size --
        lengthens the loop.

        It stops at GOOD ENOUGH, not at an optimum, and that is the important part.
        Pushing every grid towards its longest possible loop broke six of the small
        ones: on the tetrahedron the climb reaches the 4-cycle through all four
        vertices, which gives every face the clue 2, and since three different
        cycles do that, no clue set is unique and generate_minimal_clueset finds
        nothing. T, cube, O, tT, J10 and tC all failed that way. Stopping once the
        patch is within quiet_patch_allowance leaves those grids untouched -- their
        patches are already tiny -- and spends the effort only where there is a
        real blank area to break up. It also leaves a few scattered untouched
        faces, which is wanted: it reads as organic rather than mechanical.

        Bounded twice over, because an unbounded local search is exactly the kind
        of quiet time sink the old repair loop turned out to be: at most
        IMPROVEMENT_ROUNDS passes over the faces, and a pass stops early when it
        finds nothing to gain.

        Returns the improved region, never an invalid one, since a flip is only
        kept once region_is_usable has approved it.
        """
        allowance = self.quiet_patch_allowance()
        patch = self.largest_quiet_patch(region)
        for _round in range(IMPROVEMENT_ROUNDS):
            if patch <= allowance:
                break
            improved = False
            # Shuffled, so successive rounds don't keep favoring the same faces.
            candidates = list(self.mesh.faces())
            random.shuffle(candidates)
            for fkey in candidates:
                flipped = (region - {fkey}) if fkey in region else (region | {fkey})
                if not self.region_is_usable(flipped):
                    continue
                new_patch = self.largest_quiet_patch(flipped)
                better = (new_patch < patch
                          or (new_patch == patch
                              and self.loop_length(flipped) > self.loop_length(region)))
                if better:
                    (region, patch) = (flipped, new_patch)
                    improved = True
            if not improved:
                break
        return region

    def region_is_usable(self, region):
        """Whether this region would give a legal puzzle: neither color empty,
        both connected, and every vertex with 0 or 2 loop edges (so the boundary
        is a single simple loop rather than several, or one that crosses itself).

        Shared by grow_region's caller and by improve_region, so that a flip can
        never be kept unless it would have been an acceptable coloring in its own
        right.
        """
        outside = set(self.mesh.faces()) - region
        if not region or not outside:
            return False
        if any(self.boundary_degree(region, vkey) not in (0, 2)
               for vkey in self.mesh.vertices()):
            return False
        return (self.faces_are_connected(region)
                and self.faces_are_connected(outside))

    def faces_are_connected(self, faces):
        """Whether this set of faces is connected through shared edges."""
        if not faces:
            return False
        start = next(iter(faces))
        seen = {start}
        stack = [start]
        while stack:
            for nbr in self.mesh.face_neighbors(stack.pop()):
                if nbr in faces and nbr not in seen:
                    seen.add(nbr)
                    stack.append(nbr)
        return len(seen) == len(faces)

    def paint_regions(self):
        """One attempt at a usable coloring: grow a connected red region, and let
        blue be everything else.

        Returns True if the result is usable, False if this attempt should be
        thrown away -- which is the whole point of the approach. The old code
        painted every face at random and then REPAIRED the mess, growing each
        color until it was connected; but growing one color to reconnect it can
        cut the other in half, so the two repairs fought, and on dtC, dtD and dbD
        they fought forever (137,000 passes without settling, ~14 faces repainted
        per pass, while dtO settles in 9). Growing one region and discarding
        failures cannot livelock: connectivity of the region is guaranteed, and
        every other condition is a test, not a repair.

        Grow, then discard the attempt unless it is usable -- neither color empty,
        both connected, and a boundary that is one simple loop. grow_region rules
        out the self-crossing case as it goes, so in practice the only thing left
        to fail on is a second region cut in two, which is rare. Then improve what
        survives by hill-climbing, since growth alone leaves a blob whose interior
        the loop never reaches.
        """
        # Aim for between a third and two thirds of the faces, which is what
        # adjust_populations used to enforce after the fact: it keeps either color
        # from being a token sliver.
        target = random.randint(max(1, self.num_faces // 3),
                                max(1, 2 * self.num_faces // 3))
        region = self.grow_region(target)
        if not self.region_is_usable(region):
            return False
        region = self.improve_region(region)

        for fkey in self.mesh.faces():
            self.paint_face(fkey, red if fkey in region else blue)
        update_display(self.mesh)

        # improve_region only ever keeps a flip it has checked, so this should not
        # be reachable; it is the guard on the invariant everything downstream
        # assumes, and cheap next to the search above.
        try:
            check_boundary_is_single_loop(self.mesh)
        except ValueError as problem:
            log(f"Discarding coloring: {problem}", level=2)
            return False
        return True

    def generate(self, i):
        """Paint usable regions, discarding failed attempts until one works.

        i is the puzzle index, just used for logging.

        Raises RuntimeError if COLORING_ATTEMPT_LIMIT attempts all fail, so that a
        solid this cannot handle fails loudly and immediately instead of spinning.
        That distinction cost real time once already: the old repair loop's silent
        spinning on dtC was twice mistaken for a slow uniqueness proof, and read as
        evidence that the SOLVER needed more rules, when the solver was never
        reached at all.
        """
        for attempt in range(1, COLORING_ATTEMPT_LIMIT + 1):
            if self.paint_regions():
                log(f"Generated regions for puzzle {i + 1} with {self.count(red)} "
                    f"red faces and {self.count(blue)} blue faces"
                    + (f", on attempt {attempt}" if attempt > 1 else "") + ".")
                populate_num_walls(self.mesh)
                return
        raise RuntimeError(
            f"Could not grow a usable pair of regions in {COLORING_ATTEMPT_LIMIT} "
            f"attempts. Every attempt was discarded for a disconnected second "
            f"region or a self-crossing boundary; see paint_regions.")


def is_edge_boring(mesh, ekey):
    """Given an edge key, return True if the edge has two faces with the same color."""
    # Get the two faces it connects.
    (f1, f2) = mesh.edge_faces(ekey)
    return (mesh.face_attribute(f1, "color") == mesh.face_attribute(f2, "color"))


def boundary_edges(mesh):
    """The set of edges between differently-colored faces, as frozensets.

    This is the loop the coloring implies, and it is what populate_num_walls
    counts, so it -- not the walk in enumerate_solution -- is the authority on
    which edges the clues describe.
    """
    return {frozenset(ekey) for ekey in mesh.edges() if not is_edge_boring(mesh, ekey)}


def check_boundary_is_single_loop(mesh):
    """Raise ValueError unless the color boundary is one simple closed loop.

    The two-coloring of the faces guarantees an even number of boundary edges
    at every vertex, but NOT that they form a single simple cycle. Two things
    can go wrong:

      - a "pinch" vertex, where four boundary edges meet: the boundary crosses
        itself there, so it is not a simple cycle;
      - several disjoint cycles, when the coloring produces more than one
        region boundary.

    Either way the position is not a legal Slitherlink solution, and
    enumerate_solution's walk would quietly return just the piece it happened
    to start on -- while the clues, from populate_num_walls, still count every
    boundary edge. That mismatch produced puzzles whose stored solution did not
    satisfy their own clues.

    Callers treat this as a failed attempt and re-randomise the regions.
    """
    boundary = boundary_edges(mesh)
    if not boundary:
        raise ValueError("No edges found with different colors.")

    for vkey in mesh.vertices():
        degree = sum(1 for nbr in mesh.vertex_neighbors(vkey)
                     if frozenset((vkey, nbr)) in boundary)
        if degree not in (0, 2):
            raise ValueError(f"Vertex {vkey} has {degree} boundary edges, so the "
                             f"boundary is not a simple loop.")


def check_loop_covers_boundary(solution, boundary):
    """Raise ValueError unless the walked loop uses every boundary edge.

    With every vertex at boundary-degree 0 or 2 the walk cannot pinch, so the
    one remaining way to come up short is a boundary made of several disjoint
    cycles: the walk returns to its start having traced only one of them.
    """
    walked = {frozenset((solution[i], solution[(i + 1) % len(solution)]))
              for i in range(len(solution))}
    if walked != boundary:
        raise ValueError(
            f"The color boundary has {len(boundary)} edges but the loop through "
            f"them covers only {len(walked)}, so it is more than one loop.")


def enumerate_solution(mesh):
    """Express the solution as a sequence of vertex IDs that specify the loop.

    Raises ValueError if the color boundary is not a single simple loop; see
    check_boundary_is_single_loop.
    """
    check_boundary_is_single_loop(mesh)
    boundary = boundary_edges(mesh)

    solution = []
    start_vertex = None
    next_vertex = None
    for ekey in mesh.edges():
        if not is_edge_boring(mesh, ekey):
            # Remember that an edge key is just (v1, v2), that is a tuple of two vertex IDs.
            (start_vertex, next_vertex) = ekey
            break
    if start_vertex is None:
        raise ValueError("No edges found with different colors. This should never happen.")
    solution.append(start_vertex)
    solution.append(next_vertex)
    prev_vertex = start_vertex
    log(f"Solution: {solution}...", level=2)
    while next_vertex != start_vertex:
        # Get vertex neighbors of next_vertex
        neighbors = mesh.vertex_neighbors(next_vertex)
        found_next = False
        # Find the one that runs an outward edge between difference colorned faces.
        for neighbor in neighbors:
            if neighbor == prev_vertex:
                continue # Skip the previous vertex.
            log(" trying neighbor", neighbor, level=2)
            ekey = (next_vertex, neighbor)
            if not is_edge_boring(mesh, ekey):
                # Found an outgoing edge.
                log(f"Found next edge! {ekey}", level=2)
                if neighbor == start_vertex:
                    check_loop_covers_boundary(solution, boundary)
                    return solution
                solution.append(neighbor)
                log(f"   {solution}...", level=2)
                prev_vertex = next_vertex
                next_vertex = neighbor
                found_next = True
                break # out of for; continue while
        if not found_next:
            raise ValueError("No outgoing edges found with different colored faces. This should never happen.")

    # Should never reach here.
    assert False, "Should never reach this line."
    return solution


def random_face_ordering(mesh):
    """Generate a random ordering of (face, clue) pairs for the established solution.

    Faces whose every edge is on the loop (num_walls == number of sides, i.e.
    a deficit of 0) are left out. Such a clue trivialises the puzzle: it forces
    all of that face's edges, which puts two filled edges at each of its
    vertices, which rules out everything else there -- so the loop must be
    exactly that face's boundary, and the whole puzzle falls out of one clue.
    """
    clues = [(fkey, mesh.face_attribute(fkey, 'num_walls')) for fkey in mesh.faces()
             if mesh.face_attribute(fkey, 'num_walls') < len(mesh.face_vertices(fkey))]
    random.shuffle(clues)
    log(f"Clue ordering: {clues}", level=2)
    return clues


def populate_num_walls(mesh):
    """Populate the mesh's 'num_walls' attribute for each face.

    This means the number of edges that are 'filled in', i.e., part of the solution
    loop. These are the edges between faces of different colors.
    """
    for fkey in mesh.faces():
        # Note that 'boring' attribute is equivalent to 'num_walls == 0'.
        # However they're updated at different times, so they may not always
        # correspond, as it now stands.
        this_color = mesh.face_attribute(fkey, 'color')
        num_walls = sum(1 for neighbor in mesh.face_neighbors(fkey)
                        if mesh.face_attribute(neighbor, 'color') != this_color)
        mesh.face_attribute(fkey, 'num_walls', num_walls)


def clues_by_face(clues_in, num_clues_to_use, num_faces):
    """Convert the first num_clues_to_use clues from [(face, num_walls)] to [num_walls] format.

    In the returned list, the indices of the list correspond to face indices.
    So the list must be num_faces long, regardless of how few clues it contains."""
    clues_out = [-1] * num_faces
    for fkey, num_walls in itertools.islice(clues_in, num_clues_to_use):
        clues_out[fkey] = num_walls
    return clues_out


def generate_minimal_clueset(mesh) -> list[int]:
    """Using established solution, generate a fairly minimal set of clues that fit only that solution.

    In some cases this may not be possible, so the return value may be None.

    Return value: A list of integers. The indices of the list correspond to face indices
    (fkeys). The values in the list are the clues to be displayed on each face, i.e.,
    how many edges of each face that form part of the solution loop. Missing values at the
    end of the list, or -1, mean that no number should be displayed on those faces.
    """
    # cut_clues() could fail, not because there is no set of clues
    # that yields a unique solution, but because of the ordering... right?
    # Or maybe a poor ordering wouldn't make us fail but would just require more
    # clues than we could otherwise use... E.g. all of them. So...
    # We may need to iterate a bit over random orderings, before giving up...
    # but how would we know our set of clues was suboptimal?
    # Maybe try a few times and pick the best.
    # Track the BEST ordering separately so we don't return clues from
    # the last iteration's ordering (which might not be the best).
    num_faces = mesh.number_of_faces()
    min_needed = num_faces + 1   # sentinel: no successful ordering seen yet
    best_face_clues = None
    # TODO: Start these in separate threads for parallelism, and cancel if they take too long.
    for i in range(5):
        face_clues = random_face_ordering(mesh)
        num_needed = cut_clues(mesh, face_clues)
        # cut_clues returns None when no prefix of this ordering yields a
        # unique solution; skip such orderings.
        if num_needed is not None and num_needed < min_needed:
            min_needed = num_needed
            best_face_clues = face_clues

    if best_face_clues is None:
        return None   # No ordering produced a uniquely-solvable clue set.

    return clues_by_face(best_face_clues, min_needed, num_faces)


def min_prefix_satisfying(predicate, n_total, initial_guess) -> int|None:
    """Binary-search for the smallest n in [1, n_total] such that predicate(n) is True.

    Assumes the predicate is monotonic: if predicate(n) is True, then
    predicate(m) is True for every m > n. (This holds for clue prefixes:
    adding more clues can only narrow the set of possible solutions.)

    This is a pure function (no module globals) so it can be unit-tested
    with fake predicates.

    Args:
        predicate: Function taking an int n (1 <= n <= n_total), returning bool.
        n_total: The largest n to consider.
        initial_guess: Where to start probing; clamped into [1, n_total].

    Returns the smallest satisfying n, or None if even predicate(n_total)
    is False.
    """
    if n_total < 1:
        return None
    min_n = 1
    max_n = n_total
    # Clamp the initial guess into the search range.
    n = min(max(initial_guess, min_n), max_n)
    while True:
        log(f"Trying n={n}. min={min_n} max={max_n}")
        if predicate(n):
            # n satisfies the predicate, so the answer is at most n.
            max_n = n
            if n == min_n:
                # The range has closed in; n is the smallest satisfying value.
                return n
        else:
            # n doesn't satisfy, so the answer must be larger.
            min_n = n + 1
            if min_n > max_n:
                # Even n_total doesn't satisfy the predicate.
                return None
        # Floor-divide rather than round() to avoid an infinite loop when
        # min_n=1 and max_n=2: round(1.5) returns 2 (banker's rounding),
        # so n would never advance toward min_n.
        n = (min_n + max_n) // 2


def cut_clues(mesh, clues: list[tuple]) -> int|None:
    """Given a list of (face, clue) pairs, find the shortest prefix that makes
    a good puzzle. Returns None if no prefix does.

    "Good" means SOLVABLE BY DEDUCTION at LOOKAHEAD_DEPTH, not merely having a
    unique solution. That distinction turned out to matter enormously. Cutting
    to the uniqueness threshold produced puzzles that were technically fair but
    unsolvable in practice: measuring the 72 puzzles generated that way, only
    2 could be solved by reasoning at all, and 42 offered no legal first move,
    since every clue needed some edge decided before it could say anything. The
    rest could only be finished by trial and error, which is exactly the
    "not fun" this was meant to avoid.

    Requiring deductive solvability subsumes uniqueness, so nothing is lost: a
    position that sound rules determine completely admits no other solution.
    It does mean more clues than before -- that is the point.
    """
    # We now have all the clues, in a random order. We just need to determine how many
    # of them are needed.
    def prefix_is_solvable_by_deduction(num_clues):
        return slisolver.solvable_by_deduction(mesh, clues, num_clues,
                                               depth=LOOKAHEAD_DEPTH)

    # Search over the clues we actually have, which may be fewer than
    # num_faces now that random_face_ordering drops deficit-0 faces.
    # Deductive solvability needs more clues than uniqueness did, so start
    # probing higher up than the old 30% guess.
    return min_prefix_satisfying(prefix_is_solvable_by_deduction, len(clues),
                                 round(len(clues) * 0.6))


def face_symmetries():
    """Every combinatorial symmetry of the solid, as a face -> face mapping.

    These are the automorphisms of the face-adjacency graph that preserve face
    size, which for a convex polyhedron are exactly its rotations and
    reflections. Two puzzles related by one of them are the same puzzle seen
    from a different angle, however different their clue lists look.

    Computed on demand and cached: it costs up to a couple of seconds on the
    larger solids, and a run that never sees a candidate duplicate never needs
    it at all.

    A sanity check worth knowing: for every grid in data/ the group order this
    produces matches the solid's known symmetry group -- 24 for the
    tetrahedron, 48 for the cube and octahedron, 120 for the dodecahedron and
    icosahedron, and correctly 60 and 24 for the chiral snub dodecahedron and
    snub cube, which have no reflections.
    """
    global symmetries_cache
    if symmetries_cache is None:
        labelled = nx.Graph()
        for fkey in mesh.faces():
            labelled.add_node(fkey, sides=len(mesh.face_vertices(fkey)))
        for fkey in mesh.faces():
            for nbr in mesh.face_neighbors(fkey):
                labelled.add_edge(fkey, nbr)
        matcher = GraphMatcher(labelled, labelled,
                               node_match=categorical_node_match('sides', None))
        symmetries_cache = [dict(m) for m in matcher.isomorphisms_iter()]
        log(f"The solid has {len(symmetries_cache)} symmetries "
            f"(rotations and reflections).")
    return symmetries_cache


def clue_census(clues):
    """How many of each clue value a puzzle uses, ignoring which face it's on.

    A symmetry permutes the faces, so it leaves this unchanged: two puzzles
    with different censuses cannot be the same puzzle turned around. That makes
    it a cheap way to skip the symmetry scan for most candidates. It is only a
    NECESSARY condition, though, not a sufficient one -- measured over 534 pairs
    of puzzles on small grids, 5.6% shared a census while being genuinely
    different puzzles, and on the octahedron treating the census as decisive
    would have discarded half of the distinct puzzles.
    """
    return Counter(clue for clue in clues if clue != -1)


def same_puzzle_up_to_symmetry(clues_a, clues_b):
    """Is B the same puzzle as A, viewed from some other angle?"""
    return any(all(clues_b[sigma[fkey]] == clues_a[fkey]
                   for fkey in range(len(clues_a)))
               for sigma in face_symmetries())


def puzzles_so_far():
    """Every puzzle this run has kept, playable and display-only alike.

    Both lists, so that a display puzzle isn't a copy of a playable one: it would
    be an odd thing to put on the title screen, since the point of it is to show
    something other than the puzzles on offer. (Also the reason display puzzles
    are generated last: see generate_puzzles.)

    Two puzzles can still share a LOOP while differing in clues, and that's
    allowed: nothing on screen tells the player the loops match, so it gives
    nothing away.
    """
    return puzzles_output["puzzles"] + display_puzzles


def already_generated(clues):
    """Have we already produced this puzzle, up to rotation and reflection?

    Comparing clue lists face by face isn't enough: the player can turn the
    solid, so a puzzle and its mirror image, or the same puzzle rotated onto
    other faces, are one puzzle as far as they're concerned -- and data/ did
    ship such pairs (all three tetrahedron puzzles were one puzzle, and two of
    the cube's three were the same).

    Only clues are compared, never solutions: each puzzle we keep is uniquely
    solvable, so matching clues imply matching solutions.
    """
    census = clue_census(clues)
    for puzzle in puzzles_so_far():
        if clue_census(puzzle["clues"]) != census:
            continue   # Cheap: no symmetry could relate these two.
        if same_puzzle_up_to_symmetry(puzzle["clues"], clues):
            return True
    return False


def generate_puzzle(i, display=False):
    """Generate the ith puzzle, distinct from the ones already generated.

    Returns True if one was produced.

    i is just used for logging, I think.

    `display` puts the result in display_puzzles instead of the playable list.
    Nothing else changes: a display puzzle is generated by the same code, to the
    same standard (one loop, uniquely solvable by deduction), because it is shown
    with its clues and a player may well try to check it by eye.

    Some solutions admit no clue set we can solve by deduction, so we start
    over with a fresh pair of regions -- but only up to MAX_REGION_ATTEMPTS
    times, as the algorithm spec calls for ("If our attempts exceed a preset
    limit, give up on this solution and start over with A"). Without that
    limit this loop can spin indefinitely on a grid where deduction rarely
    succeeds, and since every pass logs, the log alone will eventually fill
    the disk. (It did: a 10 GB stderr file, on a J2 run.)
    """
    global solution
    clues = None
    attempts = 0
    # Attempts can fail for either of two quite different reasons, and the one
    # that stopped us is worth reporting: a grid that keeps repeating itself has
    # simply run out of distinct puzzles, which is expected on the small solids
    # and not a problem to investigate.
    duplicates_rejected = 0
    # What to call this one in the log, so a display puzzle's progress (and any
    # failure to produce one) isn't mistaken for a playable puzzle's.
    what = "display puzzle" if display else "puzzle"
    while not clues:
        if attempts >= MAX_REGION_ATTEMPTS:
            if duplicates_rejected:
                reason = (f"{duplicates_rejected} of them repeated a puzzle already "
                          f"generated, so this grid may have no more to offer")
            else:
                reason = "no set of clues for any of those solutions was solvable by deduction"
            log(f"Giving up on {what} {i} after {attempts} attempts: {reason}.",
                level=0)
            return False
        attempts += 1
        coloring.generate(i)
        try:
            solution = enumerate_solution(mesh)
        except ValueError as problem:
            # e.g. the regions came out all one color, so there are no edges
            # between differently-colored faces and hence no loop. That's a
            # failed attempt, not a reason to abandon the whole run -- which is
            # what happened before, since the exception escaped this loop and
            # killed the process, losing any puzzles already generated.
            log(f"Attempt {attempts} for {what} {i} produced no loop ({problem}); "
                f"trying again.")
            continue
        clues = generate_minimal_clueset(mesh)
        log(f"Generating clues for {what} {i} attempt {attempts} "
            f"{'succeeded' if clues else 'failed'}")
        # If we couldn't generate proper clues for this puzzle, start over from scratch.

        if clues and already_generated(clues):
            # Small grids have few distinct puzzles -- the tetrahedron has
            # exactly ONE, since the loop is always some face's boundary and
            # every face is equivalent to every other -- so drawing each puzzle
            # independently will sometimes draw the same one twice. That makes
            # the puzzle picker offer a choice that isn't one, so treat it as a
            # failed attempt. The attempt cap above stops this spinning forever
            # on a grid whose puzzles we have exhausted; hitting it means this
            # grid simply has fewer puzzles to offer, which is fine.
            log(f"Attempt {attempts} for {what} {i} repeated a puzzle already "
                f"generated (up to rotation/reflection); trying again.")
            duplicates_rejected += 1
            clues = None
            continue

    puzzle = { "clues": clues, "solution": solution }
    (display_puzzles if display else puzzles_output["puzzles"]).append(puzzle)

    plt.show()
    return True


def generate_puzzles():
    """Generate the requested puzzles, reporting any we couldn't produce.

    A puzzle that can't be generated isn't fatal: we output the ones that
    worked (see output_puzzles) rather than losing them.

    Display puzzles come last, for two reasons: they must differ from every
    playable puzzle (already_generated can only avoid what exists yet), and if
    the run is cut short it's the playable ones we want to have finished.

    On a small grid there may be no distinct puzzle left over to display -- the
    tetrahedron has exactly one puzzle in total -- so failing to produce one is
    reported and then accepted. Those grids are too small for the title screen
    anyway.
    """
    produced = 0
    for i in range(num_puzzles_wanted):
        if generate_puzzle(i):
            produced += 1
    if produced < num_puzzles_wanted:
        log(f"Produced {produced} of the {num_puzzles_wanted} puzzles requested.",
            level=0)

    displayed = 0
    for i in range(num_display_wanted):
        if generate_puzzle(i, display=True):
            displayed += 1
    if displayed < num_display_wanted:
        log(f"Produced {displayed} of the {num_display_wanted} display puzzles "
            f"requested; this grid will show no loop on the title screen.",
            level=0)


def output_puzzles():
    """Output generated puzzles in JSON format."""
    global puzzles_output
    # Only if we produced any: an empty "displayPuzzles" would be a promise of a
    # loop that isn't there, and the app treats the key's absence as "no loop"
    # (see js/puzzleLoader.js).
    if display_puzzles:
        puzzles_output["displayPuzzles"] = display_puzzles
    # One line per clue list and per solution, not one line per integer: with
    # indent=3, three puzzles on the truncated icosidodecahedron ran to 491
    # lines. (write_json ends with the newline, which also stops zsh printing a
    # confusing '%'.)
    json_format.write_json(puzzles_output, sys.stdout)


def main():
    process_args()
    load_grid_file()
    load_existing_puzzles()
    setup_display(mesh)
    # random.seed() # Uncomment once we're finished debugging.
    try:
        generate_puzzles()
    except KeyboardInterrupt:
        # Interrupted (e.g. Ctrl+C, or run_gen.py's timeout sending SIGINT).
        # Fall through and output the puzzles completed so far, rather than
        # losing them. (Only whole puzzles are ever in puzzles_output.)
        log(f"\nInterrupted; outputting the "
            f"{len(puzzles_output['puzzles'])} puzzle(s) and "
            f"{len(display_puzzles)} display puzzle(s) completed so far.",
            level=0)
    output_puzzles()


if __name__ == "__main__":
    main()
    
