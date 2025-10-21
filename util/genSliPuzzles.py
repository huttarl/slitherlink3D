"""Generate Slitherlink3D puzzles (in JSON) for a given grid (input from JSON).
Usage: python3 genSliPuzzles.py myGrid.json
Output is written to stdout.
For JSON format specifications, see docs/json-format.md."""

import json, random, sys, math, random

import matplotlib.pyplot as plt
import networkx as nx
from compas.datastructures import Mesh
from compas.geometry import centroid_points, Point, length_vector
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

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
# for Matplotlib
fig: Figure|None = None
ax: Axes3D|None = None
poly: Poly3DCollection|None = None

# Puzzle generation state
total_red = 0
total_blue = 0
red_needs_check = False
blue_needs_check = False
# Symbols for our colors, so that we don't risk typos.
red = "red"
blue = "blue"
opposite_color = {red: blue, blue: red}


def require_properties(properties):
    """Ensure that all required properties are present in the grid JSON."""
    for prop in properties:
        if prop not in grid_json:
            print(f"Error: Missing required property '{prop}' in grid JSON.")
            sys.exit(1)


def on_key_press(event):
    """Process key press events."""
    print('User pressed ', event.key)
    sys.stdout.flush()
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

    # Label each face at its centroid
    for fkey in mesh.faces():
        pts = [mesh.vertex_coordinates(vkey) for vkey in mesh.face_vertices(fkey)]
        cx, cy, cz = centroid_points(pts)
        # Move these away from origin.
        factor = 1.15
        ax.text(cx * factor, cy * factor, cz * factor, str(fkey),
                color='black', fontsize=8, ha='center', va='center')

    xs, ys, zs = zip(*[mesh.vertex_coordinates(v) for v in mesh.vertices()])
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
        print(f"Face {fkey}: {edges}")
    for (ekey) in mesh.edges():
        # Which two faces are connected by this edge?
        (f1, f2) = mesh.edge_faces(ekey)
        print(f"Edge {ekey}: f{f1} <-> f{f2}")



def build_graphs():
    """Build a graph (and its dual) from the faces and vertices loaded from the grid JSON."""
    global mesh, dualG
    # Verified that the vertex IDs are the same ones we use in the javascript game, i.e.
    #   the indices vertices. Because the game expects the solution to use those IDs.
    mesh = Mesh.from_vertices_and_faces(grid_vertices, grid_faces)
    # That was easy!
    print(f"Built mesh. F: {mesh.number_of_faces()}, V: {mesh.number_of_vertices()}, E: {mesh.number_of_edges()}")
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
    print(f"Built dual graph. V: {dualG.number_of_nodes()} nodes, E: {dualG.number_of_edges()} edges.")

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
    print(f"Max distance from origin before normalizing: {max_distance}")

    for v in mesh.vertices():
        mesh.set_vertex_point(v, mesh.vertex_point(v) / max_distance)


def process_grid_json():
    """Validate the grid JSON data and put into efficient data structures."""
    global grid_json, grid_id, grid_faces, num_faces, grid_vertices, num_vertices, puzzles_output
    # Validate required fields per json-format.md specification
    require_properties(["gridId", "gridName", "vertices", "faces"])

    grid_id = grid_json["gridId"]
    puzzles_output["gridId"] = grid_id

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
        print(f"Error: File '{sys.argv[1]}' not found.")
        sys.exit(1)
    except json.decoder.JSONDecodeError:
        print(f"Error: File '{sys.argv[1]}' is not valid JSON.")
        sys.exit(1)
    process_grid_json()


def usage():
    """Print usage message and exit."""
    print("Usage: python3 genSliPuzzles.py myGrid.json [numPuzzles]")
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
    print(f"Painting {how_many} faces {color}.")
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
    into a new neighbor, painting it the same color.
    Adjusts totals, and updates dual graph and *_needs_check as needed.
    :param component: A set of face keys in the connected component.
    :param color: The color to paint the new neighbor face."""
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
    print(f"Ensuring connectedness of {color} faces.")
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

        print(f"Connectedness of {len(this_color_face_nodes)} {color}: {is_connected}.")
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
        print(f"Checking edge {ekey} (f{f1}, f{f2})...")
        if (mesh.face_attribute(f1, "color") != mesh.face_attribute(f2, "color")):
            print(f"Edge {ekey} has different colors on faces {f1} and {f2}.")
            # Faces that have different-colored neighbors are not "boring".
            mesh.face_attribute(f1, "boring", False)
            mesh.face_attribute(f2, "boring", False)

    # Now check for boring faces with all-boring neighbors.
    num_boring_faces = 0
    for fkey in mesh.faces():
        if mesh.face_attribute(fkey, "boring"):
            print(f"Boring face {fkey} is {mesh.face_attribute(fkey, 'color')}.")
            num_boring_faces += 1
            # Check if any of the neighbors are also boring.
            for nbr in mesh.face_neighbors(fkey):
                if mesh.face_attribute(nbr, "boring"):
                    # We have two adjacent boring faces.
                    print(f"Boring face {fkey} has a boring neighbor {nbr}.")
                    # Paint one of them the opposite color.
                    f_to_color = random.choice([fkey, nbr])
                    old_color = mesh.face_attribute(f_to_color, "color")
                    print(f"  Painting face {f_to_color} {opposite_color[old_color]}")
                    paint_face(f_to_color, opposite_color[old_color])
                    # Now this face is no longer boring, nor are (most of?) its neighbors.
                    mesh.face_attribute(f_to_color, "boring", False)
                    for nbr_of_changed in mesh.face_neighbors(f_to_color):
                        mesh.face_attribute(nbr_of_changed, "boring", False)
                    # Stop processing this face. Check other boring faces (continue outer loop).
                    break


def generate_puzzle(i):
    """Generate the ith puzzle."""
    global total_red, total_blue, blue_needs_check, red_needs_check
    randomize_face_colors()
    print(f"Generated puzzle {i+1} with {total_red} red faces and {total_blue} blue faces.")
    update_display()
    finished = False
    blue_needs_check = True
    red_needs_check = True
    iterations = 0
    while not finished:
        adjust_populations() # Could trigger red_needs_check or blue_needs_check.
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
        finished = not(blue_needs_check or red_needs_check)
        iterations += 1
        print(f"{iterations} steps. Needs check: blue={blue_needs_check} red={red_needs_check}")

    print("Achieved acceptable red and blue connected regions!")
    plt.show()

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
    """Generate puzzles."""
    for i in range(num_puzzles_wanted):
        generate_puzzle(i)


def output_puzzles():
    """Output generated puzzles in JSON format."""
    global puzzles_output
    json.dump(puzzles_output, sys.stdout, indent=3)
    # Output a newline, or else zsh will display a confusing '%' character.
    print()


def main():
    process_args()
    load_grid_file()
    setup_display()
    generate_puzzles()
    output_puzzles()


if __name__ == "__main__":
    main()
    
