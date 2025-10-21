# obj2json: Convert OBJ file (export from polyHedronisme) to Slitherlink3D JSON data

import sys, json, re

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
    global name
    s = line.split()
    if len(s) > 1:
        name = s[1]

def input_vertex(line):
    global vertices # Not strictly necessary, as currently implemented.
    s = line.split()
    if len(s) < 4:
        raise ParseError("Malformed vertex line: '%s'" % line)
    else:
        # Trim to 3 decimal places, for compactness.
        vertex = [float("%0.3f" % float(coord))
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
    # Make output format compact, so that it loads quickly.
    print(json.dumps({
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
        }, separators=(',',':')))
    
def main():
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
    
