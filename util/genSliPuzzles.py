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


def generate_puzzles():
    pass


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
    
