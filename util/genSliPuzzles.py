"""Generate Slitherlink3D puzzles (in JSON) for a given grid (input from JSON).
Usage: python3 genSliPuzzles.py [--quiet|--verbose] myGrid.json [numPuzzles]
Output is written to stdout; diagnostic/progress messages go to stderr.
--quiet keeps only errors, warnings and the outcome; --verbose adds per-edge
detail. See VERBOSITY.
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
import json_format
import slisolver

# Global variables
grid_json: dict|None = None
grid_id: str|None = None
# Path to the grid file, from the command line. Not read straight out of
# sys.argv, because the flags may come before or after it.
grid_path: str|None = None
num_puzzles_wanted: int = 1
puzzles_output: dict = {}

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
    log("Usage: python3 genSliPuzzles.py [--quiet|--verbose] myGrid.json [numPuzzles]",
        level=0)
    log("  -q, --quiet    only errors, warnings and the outcome of the run", level=0)
    log("  -v, --verbose  add per-edge/per-face detail (very wordy)", level=0)
    sys.exit(1)


def process_args():
    """Process command-line arguments."""
    global num_puzzles_wanted, grid_path, VERBOSITY
    positional = []
    for arg in sys.argv[1:]:
        if arg in ("-q", "--quiet"):
            VERBOSITY = 0
        elif arg in ("-v", "--verbose"):
            VERBOSITY = 2
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


class RegionColoring:
    """The red/blue two-coloring of the faces that a puzzle's solution comes from.

    The loop is the boundary between the two colors, so generating a puzzle
    starts by painting the faces: randomly at first, then repaired until each
    color forms one connected region of a reasonable size with no dull
    all-one-color neighborhoods. See generate.

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

    def ensure_connected(self, color):
        """Check whether faces of the given color are connected.
        If not, add paint until they are.
        Return True if any faces were painted, False if the faces were already connected."""
        log(f"Ensuring connectedness of {color} faces.", level=2)
        faces_painted = False
        while True:
            # Collect face nodes of the given color.
            this_color_face_nodes = [f for f, d in self.dualG.nodes(data=True)
                                     if d['color'] == color]
            subgraph = self.dualG.subgraph(this_color_face_nodes)
            # Find the smallest connected component.
            smallest_cc = min(nx.connected_components(subgraph), key=len)
            is_connected = (len(smallest_cc) == len(this_color_face_nodes))

            log(f"Connectedness of {len(this_color_face_nodes)} {color}: {is_connected}.",
                level=2)
            update_display(self.mesh)

            if is_connected:
                return faces_painted

            # At this point I had thought to pick a face adjacent to one of the connected groups.
            # But it may be just as effective (and is easier) to just paint a random face.
            # paint_random_faces(color, 1)
            # No ... that seems to take interminable iterations to get to a suitable state.
            self.paint_neighbor_face(smallest_cc, color)
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

    def generate(self, i):
        """Paint fresh random regions and repair them into usable ones.

        Makes sure each region is connected, reasonably large, and not boring.
        i is the puzzle index, just used for logging."""
        self.randomize_face_colors()
        update_display(self.mesh)
        finished = False
        self.blue_needs_check = True
        self.red_needs_check = True
        iterations = 0
        while not finished:
            self.adjust_populations()  # Could set red_needs_check or blue_needs_check.
            if self.blue_needs_check:
                # Make sure blue is connected.
                added_blue = self.ensure_connected(blue)
                self.blue_needs_check = False
                # If that required painting faces blue...
                if added_blue:
                    self.red_needs_check = True
            if self.red_needs_check:
                # Make sure red is connected.
                added_red = self.ensure_connected(red)
                self.red_needs_check = False
                # If that required painting faces red...
                if added_red:
                    self.blue_needs_check = True
            self.fix_boring_neighborhoods()
            finished = not (self.blue_needs_check or self.red_needs_check)
            iterations += 1
            log(f"{iterations} steps. Needs check: blue={self.blue_needs_check} "
                f"red={self.red_needs_check}", level=2)

        log(f"Generated regions for puzzle {i + 1} with {self.count(red)} red faces "
            f"and {self.count(blue)} blue faces, in {iterations} steps.")
        populate_num_walls(self.mesh)


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
    for puzzle in puzzles_output["puzzles"]:
        if clue_census(puzzle["clues"]) != census:
            continue   # Cheap: no symmetry could relate these two.
        if same_puzzle_up_to_symmetry(puzzle["clues"], clues):
            return True
    return False


def generate_puzzle(i):
    """Generate the ith puzzle, distinct from the ones already generated.

    Returns True if one was produced.

    i is just used for logging, I think.

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
    while not clues:
        if attempts >= MAX_REGION_ATTEMPTS:
            if duplicates_rejected:
                reason = (f"{duplicates_rejected} of them repeated a puzzle already "
                          f"generated, so this grid may have no more to offer")
            else:
                reason = "no set of clues for any of those solutions was solvable by deduction"
            log(f"Giving up on puzzle {i} after {attempts} attempts: {reason}.",
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
            log(f"Attempt {attempts} for puzzle {i} produced no loop ({problem}); "
                f"trying again.")
            continue
        clues = generate_minimal_clueset(mesh)
        log(f"Generating clues for puzzle {i} attempt {attempts} "
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
            log(f"Attempt {attempts} for puzzle {i} repeated a puzzle already "
                f"generated (up to rotation/reflection); trying again.")
            duplicates_rejected += 1
            clues = None
            continue

    puzzle = { "clues": clues, "solution": solution }
    puzzles_output["puzzles"].append(puzzle)

    plt.show()
    return True


def generate_puzzles():
    """Generate the requested puzzles, reporting any we couldn't produce.

    A puzzle that can't be generated isn't fatal: we output the ones that
    worked (see output_puzzles) rather than losing them.
    """
    produced = 0
    for i in range(num_puzzles_wanted):
        if generate_puzzle(i):
            produced += 1
    if produced < num_puzzles_wanted:
        log(f"Produced {produced} of the {num_puzzles_wanted} puzzles requested.",
            level=0)


def output_puzzles():
    """Output generated puzzles in JSON format."""
    global puzzles_output
    # One line per clue list and per solution, not one line per integer: with
    # indent=3, three puzzles on the truncated icosidodecahedron ran to 491
    # lines. (write_json ends with the newline, which also stops zsh printing a
    # confusing '%'.)
    json_format.write_json(puzzles_output, sys.stdout)


def main():
    process_args()
    load_grid_file()
    setup_display(mesh)
    # random.seed() # Uncomment once we're finished debugging.
    try:
        generate_puzzles()
    except KeyboardInterrupt:
        # Interrupted (e.g. Ctrl+C, or run_gen.py's timeout sending SIGINT).
        # Fall through and output the puzzles completed so far, rather than
        # losing them. (Only whole puzzles are ever in puzzles_output.)
        log(f"\nInterrupted; outputting the "
            f"{len(puzzles_output['puzzles'])} puzzle(s) completed so far.",
            level=0)
    output_puzzles()


if __name__ == "__main__":
    main()
    
