"""Generate Slitherlink3D puzzles (in JSON) for a given grid (input from JSON).
Usage: python3 genSliPuzzles.py myGrid.json
Output is written to stdout.
For JSON format specifications, see docs/json-format.md."""

import json, sys
from compas.datastructures import Mesh
from compas_viewer import Viewer

# Global variables
grid_json: dict|None = None
grid_id: str|None = None
num_puzzles_wanted: int = 1
puzzles_output: dict = {}
grid_vertices: list|None = None
num_vertices: int = 0
grid_faces: list|None = None
num_faces: int = 0
puzzles: list = []
mesh: Mesh|None = None
viewer = Viewer()

def require_properties(properties):
    """Ensure that all required properties are present in the grid JSON."""
    for prop in properties:
        if prop not in grid_json:
            print(f"Error: Missing required property '{prop}' in grid JSON.")
            sys.exit(1)


def build_graph():
    """Build a graph from the faces and vertices loaded from the grid JSON."""
    global mesh
    # TODO: verify that the vertex IDs are the same ones we use in the javascript game, i.e.
    #   the indices vertices. Because the game expects the solution to use those IDs.
    mesh = Mesh.from_vertices_and_faces(grid_vertices, grid_faces)
    print("faces", mesh.number_of_faces())
    print("edges", mesh.number_of_edges())
    print("vertices", mesh.number_of_vertices())
    for vertex in mesh.vertices():
        print(vertex)

    # Display mesh, for debugging
    viewer.scene.add(mesh)
    viewer.show()
    print("Finished showing mesh.")

    # for face in grid_faces:
    #     for i in range(len(face)):
    #         G.add_edge(face[i], face[(i + 1) % len(face)])
    #
    # print("edges", G.edges)
    # print("vertices", G.nodes)
    #
    # PG = planarity.PGraph(G)
    # print("Graph is planar?", planarity.is_planar(PG))
    # # print("Faces", PG.faces()) # no such method


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
    build_graph()


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


def generate_puzzle(i):
    """Generate the ith puzzle."""
    # Here are some thoughts for a fun strategy.
    # A. Create a region of red faces and one of blue faces.
        # 1. Pick two random (not necessarily uncolored) faces. Color one red, and the other blue.
        #   Keep count of how many faces are red and blue, accounting for colors being overwritten.
        # 2. Repeat #1 until all of the faces are colored. (Maybe do the last few not by picking random faces,
        # but by iterating over faces and coloring uncolored faces.)
        # 3. Pick a blue face at random and call that your initial blue region. Check whether it's connected to all other blue faces.
        # If not, grow your blue region by coloring an adjacent red face blue. Repeat #3 until all blue
        # faces are connected.
        # 4. Do likewise with red faces until they are all connected.
        # 5. Repeat #3 and #4 until both red and blue regions are all connected, without changes.
        # 5.5. Try not to let the number of red faces or blue faces fall below a certain threshold.
        #   If they do, sprinkle more red or blue paint and repeat #3 and #4.
        # 6. Fill in every edge that is between red and blue faces. Now we have a loop (solution).
        # 7. Optional: check how many faces we have that have zero edges filled. A high percentage
        #   would indicate a "boring" puzzle. Even worse: zero-edge-filled faces surrounded by other
        #   zero-edge-filled faces. In a case like that, just change the color of that face and go
        #   back to step 3.
    # B. Generate clues
        # 1. Pick a random face. Give it a clue corresponding to the number of adjacent filled edges.
        # 2. Repeat #1 for a certain percentage of the faces (adjustable heuristic).
        # 3. Attempt to solve the puzzle using the clues:
            # a. If there is no solution, remove one of the clues and try again. But this should never
                # happen, because the clues are based on an actual, valid solution.
            # b. If there are multiple solutions, add a new clue and try again. We could even do
                # a binary search to find the best number of clues: Maintain a min and max number
                # of clues from previous tries. Zero in until we find clues that give a unique solution.
            # c. If there is only one solution, we have a successful puzzle; record it.
                # To make an easier puzzle (adjustable difficulty level), we could add more clues.
            # d. If our attempts exceed a preset limit, give up on this solution and start over with A.


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
    generate_puzzles()
    output_puzzles()


if __name__ == "__main__":
    main()
    
