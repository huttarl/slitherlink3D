"""Generate Slitherlink3D puzzles (in JSON) for a given grid (input from JSON).
Usage: python3 genSliPuzzles.py myGrid.json
Output is written to stdout.
For JSON format specifications, see docs/json-format.md."""

import json, sys

# Global variables
grid_json: dict|None = None
grid_id: str|None = None
num_puzzles_wanted: int = 1
puzzles_output: dict = {}
# Unneeded: grid_vertices: list|None = None
num_vertices: int = 0
grid_faces: list|None = None
num_faces: int = 0
puzzles: list = []


def require_properties(properties):
    for prop in properties:
        if prop not in grid_json:
            print(f"Error: Missing required property '{prop}' in grid JSON.")
            sys.exit(1)


def process_grid_json():
    """Validate the grid JSON data and put into efficient data structures."""
    global grid_json, grid_id, grid_faces, puzzles_output, num_vertices, num_faces
    # Validate required fields per json-format.md specification
    require_properties(["gridId", "gridName", "vertices", "faces"])

    grid_id = grid_json["gridId"]
    puzzles_output["gridId"] = grid_id

    num_vertices = len(grid_json["vertices"])
    # We're not actually going to need any vertex positions. Just their indices.

    grid_faces = grid_json["faces"]
    num_faces = len(grid_faces)

    # Deallocate the grid JSON data.
    grid_json = None


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
        #   If they do, start over with A.
        # 6. Fill in every edge that is between red and blue faces. Now we have a loop (solution).
    # B. Generate clues
        # 1. Pick a random face. Give it a clue corresponding to the number of adjacent filled edges.
        # 2. Repeat #1 for a certain percentage of the faces (adjustable heuristic).
        # 3. Attempt to solve the puzzle using the clues:
            # a. If there is no solution, remove one of the clues and try again.
            # b. If there are multiple solutions, add a new clue and try again.
            # c. If there is exactly one solution, we have a successful puzzle; record it.
            # d. If our attempts exceed a preset limit, give up on this solution and start over with A.


def generate_puzzles():
    """Generate puzzles."""
    for i in range(num_puzzles_wanted):
        generate_puzzle(i)


def output_puzzles():
    global puzzles_output
    json.dump(puzzles_output, sys.stdout, indent=3)
    # Output a newline, or else zsh will display a confusing '%' character.
    print()


def main():
    global num_puzzles
    process_args()
    load_grid_file()
    generate_puzzles()
    output_puzzles()


if __name__ == "__main__":
    main()
    
