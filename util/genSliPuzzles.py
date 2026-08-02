"""Generate Slitherlink3D puzzles (in JSON) for a given grid (input from JSON).
Usage: python3 genSliPuzzles.py myGrid.json
Output is written to stdout; diagnostic/progress messages go to stderr.
For JSON format specifications, see docs/json-format.md."""
import itertools, json, random, sys, math

import matplotlib.pyplot as plt
import networkx as nx
from compas.datastructures import Mesh
from compas.geometry import Point, length_vector
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Our local module
import slisolver

# Global variables
grid_json: dict|None = None
grid_id: str|None = None
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

# Puzzle generation state
total_red = 0
total_blue = 0
# If a face has been painted blue, we need to check whether the red faces are still connected; and v.v.
red_needs_check = False
blue_needs_check = False
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


def log(*args, **kwargs):
    """Print a diagnostic/progress message to stderr.

    stdout is reserved for the generated puzzle JSON, so that output can
    be piped or redirected cleanly; everything else goes through here."""
    print(*args, file=sys.stderr, **kwargs)


def require_properties(properties):
    """Ensure that all required properties are present in the grid JSON."""
    for prop in properties:
        if prop not in grid_json:
            log(f"Error: Missing required property '{prop}' in grid JSON.")
            sys.exit(1)


def on_key_press(event):
    """Process key press events."""
    log('User pressed ', event.key)
    sys.stderr.flush()
    if event.key == 'x':
        update_display()


def setup_display():
    """Set up the display for the mesh."""
    global fig, ax, poly
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    fig.canvas.mpl_connect('key_press_event', on_key_press)
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


def update_display():
    """Update the display with the current mesh."""
    global fig, ax

    colors = [mesh.face_attribute(fkey, 'color') for fkey in mesh.faces()]
    poly.set_facecolor(colors)

    plt.draw()
    # print("Displaying mesh...")
    plt.pause(0.001)  # brief pause to refresh display


def log_mesh():
    """Log faces, edges of built mesh for debugging."""
    for (fkey) in mesh.faces():
        edges = ", ".join(str(ekey) for ekey in mesh.face_halfedges(fkey))
        log(f"Face {fkey}: {edges}")
    for (ekey) in mesh.edges():
        # Which two faces are connected by this edge?
        (f1, f2) = mesh.edge_faces(ekey)
        log(f"Edge {ekey}: f{f1} <-> f{f2}")



def build_graphs():
    """Build a graph (and its dual) from the faces and vertices loaded from the grid JSON."""
    global mesh, dualG
    # Verified that the vertex IDs are the same ones we use in the javascript game, i.e.
    #   the indices vertices. Because the game expects the solution to use those IDs.
    mesh = Mesh.from_vertices_and_faces(grid_vertices, grid_faces)
    # That was easy!
    log(f"Built mesh. F: {mesh.number_of_faces()}, V: {mesh.number_of_vertices()}, E: {mesh.number_of_edges()}")
    # log_mesh()
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
        grid_json = json.load(open(sys.argv[1], "r"))
    except FileNotFoundError:
        log(f"Error: File '{sys.argv[1]}' not found.")
        sys.exit(1)
    except json.decoder.JSONDecodeError:
        log(f"Error: File '{sys.argv[1]}' is not valid JSON.")
        sys.exit(1)
    process_grid_json()


def usage():
    """Print usage message and exit."""
    log("Usage: python3 genSliPuzzles.py myGrid.json [numPuzzles]")
    sys.exit(1)


def process_args():
    """Process command-line arguments."""
    global num_puzzles_wanted
    if (len(sys.argv) < 2 or len(sys.argv) > 3):
        usage() # exits
    if (len(sys.argv) == 3):
        num_puzzles_wanted = int(sys.argv[2])


def paint_random_faces(color, how_many):
    """Change specified number of random faces to the given color.
    Checks that the chosen faces weren't already that color.
    Adjusts totals, and updates dual graph and *_needs_check as needed."""
    global red_needs_check, blue_needs_check, total_red, total_blue
    log(f"Painting {how_many} faces {color}.")
    for i in range(how_many):
        while True:
            fkey = random.choice(list(mesh.faces()))
            if mesh.face_attribute(fkey, "color") != color:
                paint_face(fkey, color)
                break # out of 'while', continue 'for'


def paint_face(fkey, color):
    """Paint the given face the given color.
    Adjusts totals, and updates dual graph and *_needs_check as needed."""
    global total_red, total_blue, red_needs_check, blue_needs_check
    mesh.face_attribute(fkey, "color", color)
    dualG.nodes[fkey]["color"] = color
    if color == red:
        total_red += 1
        blue_needs_check = True
    else:
        total_blue += 1
        red_needs_check = True


def adjust_populations():
    """If the number of blue or red faces is too low, increase it."""
    if total_red < num_faces / 3 or total_red < 1:
        paint_random_faces(red, round(num_faces / 3 - total_red))
    elif total_blue < num_faces / 3 or total_blue < 1:
        paint_random_faces(blue, round(num_faces / 3 - total_blue))


def paint_neighbor_face(component, color):
    """Expand the given connected component, which consists of faces of the given color,
    by painting a neighbor the same color.
    Adjusts totals, and updates dual graph and *_needs_check as needed.
        component - A set containing the face keys in the connected component.
        color - The color to paint the new neighbor face."""
    # Convert set to a list for choosing randomly.
    faces = list(component)
    while True:
        face_to_grow = random.choice(faces)
        # Pick a neighbor of face_to_grow.
        neighbor = random.choice (mesh.face_neighbors(face_to_grow))
        # If the neighbor is already this color, try another neighbor.
        if mesh.face_attribute(neighbor, "color") != color:
            # If the neighbor is the same color, paint it the same color..
            paint_face(neighbor, color)
            return
        # Otherwise, pick a new face and a new neighbor.


def ensure_connected(color):
    """Check whether faces of the given color are connected.
    If not, add paint until they are.
    Return True if any faces were painted, False if the faces were already connected."""
    log(f"Ensuring connectedness of {color} faces.")
    faces_painted = False
    while True:
        # Collect face nodes of the given color.
        # p = dualG.nodes(data=True)
        # print(f"Dual graph has {len(p)} nodes") # {repr(p)}
        this_color_face_nodes = [f for f, d in dualG.nodes(data=True) if d['color'] == color]
        subgraph = dualG.subgraph(this_color_face_nodes)
        # is_connected = nx.is_connected(subgraph)
        # Find the smallest connected component.
        smallest_cc = min(nx.connected_components(subgraph), key=len)
        is_connected = (len(smallest_cc) == len(this_color_face_nodes))

        log(f"Connectedness of {len(this_color_face_nodes)} {color}: {is_connected}.")
        update_display()

        if is_connected:
            return faces_painted

        # At this point I had thought to pick a face adjacent to one of the connected groups.
        # But it may be just as effective (and is easier) to just paint a random face.
        # paint_random_faces(color, 1)
        # No ... that seems to take interminable iterations to get to a suitable state.
        paint_neighbor_face(smallest_cc, color)
        faces_painted = True

        update_display()


def fix_boring_neighborhoods():
    """Disrupt neighborhoods of where faces are all the same color."""
    # Set all faces to "boring".
    for fkey in mesh.faces():
        mesh.face_attribute(fkey, "boring", True)
    for ekey in mesh.edges():
        # For every edge, get the two faces it connects.
        (f1, f2) = mesh.edge_faces(ekey)
        log(f"Checking edge {ekey} (f{f1}, f{f2})...")
        if (mesh.face_attribute(f1, "color") != mesh.face_attribute(f2, "color")):
            log(f"Edge {ekey} has different colors on faces {f1} and {f2}.")
            # Faces that have different-colored neighbors are not "boring".
            mesh.face_attribute(f1, "boring", False)
            mesh.face_attribute(f2, "boring", False)

    # Now check for boring faces with all-boring neighbors.
    num_boring_faces = 0
    for fkey in mesh.faces():
        if mesh.face_attribute(fkey, "boring"):
            log(f"Boring face {fkey} is {mesh.face_attribute(fkey, 'color')}.")
            num_boring_faces += 1
            # Check if any of the neighbors are also boring.
            for nbr in mesh.face_neighbors(fkey):
                if mesh.face_attribute(nbr, "boring"):
                    # We have two adjacent boring faces.
                    log(f"Boring face {fkey} has a boring neighbor {nbr}.")
                    # Paint one of them the opposite color.
                    f_to_color = random.choice([fkey, nbr])
                    old_color = mesh.face_attribute(f_to_color, "color")
                    log(f"  Painting face {f_to_color} {opposite_color[old_color]}")
                    paint_face(f_to_color, opposite_color[old_color])
                    # Now this face is no longer boring, nor are (most of?) its neighbors.
                    mesh.face_attribute(f_to_color, "boring", False)
                    for nbr_of_changed in mesh.face_neighbors(f_to_color):
                        mesh.face_attribute(nbr_of_changed, "boring", False)
                    # Stop processing this face. Check other boring faces (continue outer loop).
                    break


def is_edge_boring(ekey):
    """Given an edge key, return True if the edge has two faces with the same color."""
    # Get the two faces it connects.
    (f1, f2) = mesh.edge_faces(ekey)
    return (mesh.face_attribute(f1, "color") == mesh.face_attribute(f2, "color"))


def boundary_edges():
    """The set of edges between differently-colored faces, as frozensets.

    This is the loop the coloring implies, and it is what populate_num_walls
    counts, so it -- not the walk in enumerate_solution -- is the authority on
    which edges the clues describe.
    """
    return {frozenset(ekey) for ekey in mesh.edges() if not is_edge_boring(ekey)}


def check_boundary_is_single_loop():
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
    boundary = boundary_edges()
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


def enumerate_solution():
    """Express the solution as a sequence of vertex IDs that specify the loop.

    Raises ValueError if the color boundary is not a single simple loop; see
    check_boundary_is_single_loop.
    """
    check_boundary_is_single_loop()
    boundary = boundary_edges()

    solution = []
    start_vertex = None
    next_vertex = None
    for ekey in mesh.edges():
        if not is_edge_boring(ekey):
            # Remember that an edge key is just (v1, v2), that is a tuple of two vertex IDs.
            (start_vertex, next_vertex) = ekey
            break
    if start_vertex is None:
        raise ValueError("No edges found with different colors. This should never happen.")
    solution.append(start_vertex)
    solution.append(next_vertex)
    prev_vertex = start_vertex
    log(f"Solution: {solution}...")
    while next_vertex != start_vertex:
        # Get vertex neighbors of next_vertex
        neighbors = mesh.vertex_neighbors(next_vertex)
        found_next = False
        # Find the one that runs an outward edge between difference colorned faces.
        for neighbor in neighbors:
            if neighbor == prev_vertex:
                continue # Skip the previous vertex.
            log(" trying neighbor", neighbor)
            ekey = (next_vertex, neighbor)
            if not is_edge_boring(ekey):
                # Found an outgoing edge.
                log(f"Found next edge! {ekey}")
                if neighbor == start_vertex:
                    check_loop_covers_boundary(solution, boundary)
                    return solution
                solution.append(neighbor)
                log(f"   {solution}...")
                prev_vertex = next_vertex
                next_vertex = neighbor
                found_next = True
                break # out of for; continue while
        if not found_next:
            raise ValueError("No outgoing edges found with different colored faces. This should never happen.")

    # Should never reach here.
    assert False, "Should never reach this line."
    return solution


def random_face_ordering():
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
    log(f"Clue ordering: {clues}")
    return clues


def populate_num_walls():
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


def clues_by_face(clues_in, num_clues_to_use):
    """Convert the first num_clues_to_use clues from [(face, num_walls)] to [num_walls] format.

    In the returned list, the indices of the list correspond to face indices.
    So the list must be num_faces long, regardless of how few clues it contains."""
    clues_out = [-1] * num_faces
    for fkey, num_walls in itertools.islice(clues_in, num_clues_to_use):
        clues_out[fkey] = num_walls
    return clues_out


def generate_minimal_clueset() -> list[int]:
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
    min_needed = num_faces + 1   # sentinel: no successful ordering seen yet
    best_face_clues = None
    # TODO: Start these in separate threads for parallelism, and cancel if they take too long.
    for i in range(5):
        face_clues = random_face_ordering()
        num_needed = cut_clues(face_clues)
        # cut_clues returns None when no prefix of this ordering yields a
        # unique solution; skip such orderings.
        if num_needed is not None and num_needed < min_needed:
            min_needed = num_needed
            best_face_clues = face_clues

    if best_face_clues is None:
        return None   # No ordering produced a uniquely-solvable clue set.

    return clues_by_face(best_face_clues, min_needed)


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


def cut_clues(clues: list[tuple]) -> int|None:
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


def generate_puzzle(i):
    """Generate the ith puzzle. Returns True if one was produced.

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
    while not clues:
        if attempts >= MAX_REGION_ATTEMPTS:
            log(f"Giving up on puzzle {i} after {attempts} attempts: no set of "
                f"clues for any of those solutions was solvable by deduction.")
            return False
        attempts += 1
        generate_regions(i)
        try:
            solution = enumerate_solution()
        except ValueError as problem:
            # e.g. the regions came out all one color, so there are no edges
            # between differently-colored faces and hence no loop. That's a
            # failed attempt, not a reason to abandon the whole run -- which is
            # what happened before, since the exception escaped this loop and
            # killed the process, losing any puzzles already generated.
            log(f"Attempt {attempts} for puzzle {i} produced no loop ({problem}); "
                f"trying again.")
            continue
        clues = generate_minimal_clueset()
        log(f"Generating clues for puzzle {i} attempt {attempts} "
            f"{'succeeded' if clues else 'failed'}")
        # If we couldn't generate proper clues for this puzzle, start over from scratch.

    puzzle = { "clues": clues, "solution": solution }
    puzzles_output["puzzles"].append(puzzle)

    plt.show()
    return True


def generate_regions(i):
    """Generate random red and blue regions, which will determine the solution.

    Makes sure each region is connected, reasonably large, and not boring.
    i is the puzzle index, just used for logging."""
    global total_red, total_blue, blue_needs_check, red_needs_check
    randomize_face_colors()
    update_display()
    finished = False
    blue_needs_check = True
    red_needs_check = True
    iterations = 0
    while not finished:
        adjust_populations()  # Could trigger red_needs_check or blue_needs_check.
        if blue_needs_check:
            # Make sure blue is connected.
            added_blue = ensure_connected(blue)
            blue_needs_check = False
            # If that required painting faces blue...
            if added_blue:
                red_needs_check = True
        if red_needs_check:
            # Make sure red is connected.
            added_red = ensure_connected(red)
            red_needs_check = False
            # If that required painting faces red...
            if added_red:
                blue_needs_check = True
        fix_boring_neighborhoods()
        finished = not (blue_needs_check or red_needs_check)
        iterations += 1
        log(f"{iterations} steps. Needs check: blue={blue_needs_check} red={red_needs_check}")

    log(f"Generated regions for puzzle {i + 1} with {total_red} red faces and {total_blue} blue faces, in {iterations} steps.")
    populate_num_walls()


def randomize_face_colors():
    """Assign red or blue randomly to each face."""
    global total_red, total_blue
    for fkey in mesh.faces():
        color = random.choice([red, blue])
        if color == red:
            total_red += 1
        else:
            total_blue += 1
        mesh.face_attribute(fkey, "color", color)
        dualG.nodes[fkey]["color"] = color


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
        log(f"Produced {produced} of the {num_puzzles_wanted} puzzles requested.")


def output_puzzles():
    """Output generated puzzles in JSON format."""
    global puzzles_output
    json.dump(puzzles_output, sys.stdout, indent=3)
    # Output a newline, or else zsh will display a confusing '%' character.
    # (Deliberately print, not log: the newline terminates the JSON on stdout.)
    print()


def main():
    process_args()
    load_grid_file()
    setup_display()
    # random.seed() # Uncomment once we're finished debugging.
    try:
        generate_puzzles()
    except KeyboardInterrupt:
        # Interrupted (e.g. Ctrl+C, or run_gen.py's timeout sending SIGINT).
        # Fall through and output the puzzles completed so far, rather than
        # losing them. (Only whole puzzles are ever in puzzles_output.)
        log(f"\nInterrupted; outputting the "
            f"{len(puzzles_output['puzzles'])} puzzle(s) completed so far.")
    output_puzzles()


if __name__ == "__main__":
    main()
    
