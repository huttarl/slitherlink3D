"""Generate Slitherlink3D puzzles (in JSON) for a given grid (input from JSON).
Usage: python3 genSliPuzzles.py myGrid.json
Output is written to stdout.
For JSON format specifications, see docs/json-format.md."""

import json, sys
import time, random

from compas.datastructures import Mesh
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.figure import Figure, FigureBase
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

# Puzzle generation state
total_red = 0
total_blue = 0
red_needs_check = False
blue_needs_check = False

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
    global fig, ax
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    fig.canvas.mpl_connect('key_press_event', on_key_press)
    plt.ion() # enable interactive mode


def update_display():
    """Update the display with the current mesh."""
    global fig, ax

    # draw faces
    ax.clear()
    # TODO: since the V/E/F don't change, only their colors, it would be better
    # not to rebuild the mesh, but just update the colors.
    faces = [[mesh.vertex_coordinates(vkey) for vkey in mesh.face_vertices(fkey)]
             for fkey in mesh.faces()]
    colors = [mesh.face_attribute(fkey, 'color') for fkey in mesh.faces()]

    poly = Poly3DCollection(faces, facecolors=colors, edgecolor='gray', alpha=0.8, linewidths=2)
    ax.add_collection3d(poly)
    xs, ys, zs = zip(*[mesh.vertex_coordinates(v) for v in mesh.vertices()])
    ax.auto_scale_xyz(xs, ys, zs)
    ax.set_box_aspect([1, 1, 1])

    # Remove grid and axes
    plt.grid(b=None)
    plt.axis('off')

    plt.draw()
    print("Displaying mesh...")
    plt.pause(0.01)  # brief pause to refresh display


def build_graphs():
    """Build a graph (and its dual) from the faces and vertices loaded from the grid JSON."""
    global mesh, dualG
    # Verified that the vertex IDs are the same ones we use in the javascript game, i.e.
    #   the indices vertices. Because the game expects the solution to use those IDs.
    mesh = Mesh.from_vertices_and_faces(grid_vertices, grid_faces)
    # That was easy!
    print(f"Built mesh. F: {mesh.number_of_faces()}, V: {mesh.number_of_vertices()}, E: {mesh.number_of_edges()}")
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


def process_grid_json():
    """Validate the grid JSON data and put into efficient data structures."""
    global grid_json, grid_id, grid_faces, num_faces, grid_vertices, num_vertices, puzzles_output
    # Validate required fields per json-format.md specification
    require_properties(["gridId", "gridName", "vertices", "faces"])

    grid_id = grid_json["gridId"]
    puzzles_output["gridId"] = grid_id

    grid_vertices = grid_json["vertices"]
    num_vertices = len(grid_json["vertices"])
    # We're not actually going to need any vertex positions. Just their indices.

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
                mesh.face_attribute(fkey, "color", color)
                dualG.nodes[fkey]["color"] = color
                break # out of 'while', continue 'for'
    if color == "red":
        total_red += how_many
        blue_needs_check = True
    else:
        total_blue += how_many
        red_needs_check = True


def adjust_populations():
    """If the number of blue or red faces is too low, increase it."""
    if total_red < num_faces / 3 or total_red < 1:
        paint_random_faces('red', round(num_faces / 3 - total_red))
    elif total_blue < num_faces / 3 or total_blue < 1:
        paint_random_faces('blue', round(num_faces / 3 - total_blue))


def ensure_connected(color):
    """Check whether faces of the given color are connected.
    If not, add paint until they are.
    Return True if they were already connected, False if we had to paint any faces."""
    print(f"Ensuring connectedness of faces of color {color}.")
    failed = False
    while True:
        # Collect face nodes of the given color.
        p = dualG.nodes(data=True)
        print(f"Dual graph has {len(p)} nodes: {repr(p)}")
        this_color_face_nodes = [f for f, d in dualG.nodes(data=True) if d['color'] == color]
        is_connected = nx.is_connected(dualG.subgraph(this_color_face_nodes))
        print(f"Connectedness of {len(this_color_face_nodes)} {color}: {is_connected}.")
        update_display()

        if is_connected:
            return not failed
        else:
            failed = True
        # At this point I had thought to pick a face adjacent to one of the connected groups.
        # But it may be just as effective (and is easier) to just paint a random face.
        paint_random_faces(color, 1)
        # TODO: re-collecting color face nodes in order to re-check connectedness is inefficient.
        # Instead, add the just-painted face to the face node collection.
        update_display()


def generate_puzzle(i):
    """Generate the ith puzzle."""
    global total_red, total_blue, blue_needs_check, red_needs_check
    randomize_face_colors()
    print(f"Generated puzzle {i+1} with {total_red} red faces and {total_blue} blue faces.")
    finished = False
    blue_needs_check = True
    red_needs_check = True
    while not finished:
        adjust_populations()
        if blue_needs_check:
            while not ensure_connected('blue'):
                red_needs_check = True
        if red_needs_check:
            while not ensure_connected('red'):
                blue_needs_check = True
        finished = not(blue_needs_check or red_needs_check)

    # Display...
    for step in range(10):
        # ... modify your mesh here (e.g., move vertices, change topology) ...
        update_display()
        time.sleep(0.2)  # simulate computation time

    plt.show()

def randomize_face_colors():
    """Assign red or blue randomly to each face."""
    global total_red, total_blue
    for fkey in mesh.faces():
        color = random.choice(["red", "blue"])
        if color == "red":
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
    
