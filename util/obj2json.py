#!/usr/bin/env python3
# obj2json: Convert OBJ file (export from polyHedronisme) to Slitherlink3D JSON data
# Standard library only, so plain python3 runs it.

import sys, json, re

import json_format

cells = []
vertices = []
name = "unknown"
num_edges = 0

class ParseError(SyntaxError):
    """Raised when there's trouble parsing the input."""
    pass

def process(line):
    # print("Processing", line)
    if line.startswith("#") or len(line) == 0:
        # ignore comments and blank lines
        pass
    elif line.startswith("g") or line.startswith("o"):
        # "o" for object
        # "g" for polygon group
        input_group(line)
    # Distinguish "v" from "vt", "vn", "vp"
    elif line.startswith("v "):
        input_vertex(line)
    elif line.startswith("f"):
        input_face(line)
    else:
        # We could raise warnings here. But it's probably not worth it.
        pass

def input_group(line):
    """Take the grid's name from an OBJ group line ("g Hexagonal prism").

    The whole rest of the line, not just the first word: OBJ allows several
    space-separated group names, but what a generator puts there is a name for
    the solid, and "g Random sphere B" arriving as "Random" is no use as a
    gridName. sanitize_for_id then strips the spaces for the gridId.
    """
    global name
    rest = line.split(maxsplit=1)
    if len(rest) > 1:
        name = rest[1].strip()

def input_vertex(line):
    global vertices # Not strictly necessary, as currently implemented.
    s = line.split()
    if len(s) < 4:
        raise ParseError("Malformed vertex line: '%s'" % line)
    else:
        # Trim to 6 decimal places, for compactness.
        vertex = [float("%0.6f" % float(coord))
                  for coord in s[1:]]
        # print("Appending vertex ", vertex)
        vertices.append(vertex)

def input_face(line):
    global cells, num_edges
    # 1. Split into vertex "clusters" delimited by whitespace
    # 2. Split clusters delimited by "/" and take only the first.
    # 3. Convert to integer and subtract 1, because indices are 1-based.
    vx_indices = [int(index_group.split('/')[0]) - 1
                  for index_group in line.split()[1:]]
    if len(vx_indices) < 3:
        raise ParseError("Invalid face line (not enough vertices): " + line)
    # print("Appending face ", vx_indices)
    cells.append(vx_indices)
    num_edges += len(vx_indices) / 2.0 # Because each edge belongs to 2 cells.
    # TODO maybe: Catch cases where a vertex index is out of bounds.

def sanitize_for_id(s):
    """Sanitize string for use as an ID."""
    # Allow alphanumeric ASCII characters + underscore.
    return re.sub(r"[^0-9A-Za-z_]", "", s)

def output():
    # Compact enough to load quickly, but a line per vertex and per face so a
    # person can read it. See util/json_format.py.
    print(json_format.format_json({
        "gridId": sanitize_for_id(name),  # machine-friendly ID
        "gridName": name,  # user-visible name, e.g. "Rhombille"
        # At some point, add categories like "Johnson solid" and/or "zonohedron" etc.
        # That may come after the OBJ-to-JSON conversion.
        "categories": [],
#         "nCells": len(cells),  # "cell" == "face"
#         "nEdges": int(num_edges), # Not sure why we need these counts, but they don't hurt.
#         "nVertices": len(vertices),
        "vertices": vertices,
        "faces": cells,
#         "puzzles": []
        }))
    
def usage():
    """Print how to run this, and exit. Reached when there's no filename to
    read, which used to raise IndexError from sys.argv[1] and print a traceback
    that said nothing about what was wrong."""
    print("Usage: util/obj2json.py myPolyhedron.obj > data/myGrid.json",
          file=sys.stderr)
    print("Converts an OBJ export (e.g. from polyHedronisme) to grid JSON.",
          file=sys.stderr)
    print("The grid's name and id come from the OBJ's group ('g') line, so give",
          file=sys.stderr)
    print("each solid its own; see docs/generating-grids.md.", file=sys.stderr)
    sys.exit(1)

def main():
    # One argument, the OBJ file: the JSON goes to stdout, so there's no output
    # filename to give. "-h" is worth catching separately, or we'd go looking
    # for a file called "-h".
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        usage()  # exits
    try:
        with open(sys.argv[1], "r") as f:
            for line in f:
                process(line.rstrip())
        if num_edges + 2 != len(cells) + len(vertices):
            raise ParseError("F + V != E + 2: %d + %d != %0.1f + 2" %
                             (len(cells), len(vertices), num_edges))
        output()
    except ParseError as e:
        print("Parse error: %s" % e.args, file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print("Couldn't read file: %s" % e, file=sys.stderr)
        sys.exit(1)
        
if __name__ == "__main__":
    main()
    
