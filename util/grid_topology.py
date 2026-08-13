"""Topology of a grid, and of a puzzle on it, straight from the JSON.

A library, not a command: no shebang and not executable, as with slisolver.py.
In util/, a shebang means the file can be run.

The shared helpers that several scripts had each grown their own copy of: a
breadth-first search over face adjacency existed in four places, `edges_of` in
two, and "largest patch of faces the loop never touches" in two — the last being
the one that mattered, since it is now a puzzle-quality gate and two definitions
of it would drift apart unnoticed.

**Standard library only, and deliberately so.** It works on the raw lists from the
JSON (`vertices`, `faces`, and a puzzle's `solution`), not on a COMPAS mesh,
because `catalogue_report.py`, `grid_quality.py` and `build_catalogue.py` are all
meant to run under a plain `python3` with nothing installed. Anything here that
needed compas or numpy would take that away from them.

An **edge** here is always a `tuple(sorted((u, v)))`, so the same edge compares
equal however it was written. That matches `edge_id` in `slisolver.py`, which
solves the same problem for the solver's own structures.

Faces are referred to by index into the `faces` list, which is also their ID
everywhere else in the project (see `docs/json-format.md`).
"""
import json
from pathlib import Path


def load_grid(path):
    """The parsed grid JSON at `path`."""
    return json.loads(Path(path).read_text())


def edge_key(vertex1, vertex2):
    """The canonical form of the edge between two vertices."""
    return (vertex1, vertex2) if vertex1 < vertex2 else (vertex2, vertex1)


def face_edges(face):
    """A face's edges, in order round it."""
    return [edge_key(face[i], face[(i + 1) % len(face)]) for i in range(len(face))]


def edges_of(faces):
    """Every edge of the solid, as a set."""
    return {ekey for face in faces for ekey in face_edges(face)}


def vertex_degrees(faces):
    """Vertex index -> how many faces (equivalently, edges) meet there.

    Every edge is shared by exactly two faces on a closed solid, so a vertex's
    face count equals its edge count. NOT so on a surface with a boundary, where a
    corner of a single face has two edges and one face -- see edge_degrees, which
    counts edges either way.
    """
    degrees = {}
    for face in faces:
        for vertex in face:
            degrees[vertex] = degrees.get(vertex, 0) + 1
    return degrees


def edge_degrees(faces):
    """Vertex index -> how many distinct EDGES meet there.

    The same numbers as vertex_degrees on a closed solid, and deliberately separate
    because they part company on an open one: the open nanotube's rim atoms belong to
    one hexagon apiece and so count 1 there, while what matters for play is that they
    have 2 edges. Which is the number a loop cares about -- it needs two edges at
    every vertex it visits, so a vertex with only one edge has an edge that can never
    be filled.
    """
    degrees = {}
    for (first, second) in edges_of(faces):
        degrees[first] = degrees.get(first, 0) + 1
        degrees[second] = degrees.get(second, 0) + 1
    return degrees


def face_adjacency(faces):
    """Face index -> the set of face indices sharing an edge with it.

    Built once and passed around, which is both clearer and faster than asking a
    mesh for a face's neighbors inside a loop.
    """
    owners = {}
    for (index, face) in enumerate(faces):
        for ekey in face_edges(face):
            owners.setdefault(ekey, []).append(index)
    adjacency = {index: set() for index in range(len(faces))}
    for sharers in owners.values():
        for index in sharers:
            adjacency[index].update(other for other in sharers if other != index)
    return adjacency


def connected_groups(members, adjacency):
    """Partition `members` into connected groups, as a list of sets.

    Only the members given are traversed: a group may well continue outside the
    set, and stops at its edge. `adjacency` maps a member to its neighbors, and
    neighbors not in `members` are ignored.
    """
    remaining = set(members)
    groups = []
    while remaining:
        group = {remaining.pop()}
        stack = list(group)
        while stack:
            for neighbor in adjacency[stack.pop()]:
                if neighbor in remaining:
                    remaining.discard(neighbor)
                    group.add(neighbor)
                    stack.append(neighbor)
        groups.append(group)
    return groups


def is_connected(members, adjacency):
    """Whether `members` forms a single connected group. Empty is not connected."""
    return len(connected_groups(members, adjacency)) == 1


def largest_group(members, adjacency):
    """The size of the biggest connected group within `members`; 0 if empty."""
    groups = connected_groups(members, adjacency)
    return max((len(group) for group in groups), default=0)


def loop_edges(solution):
    """A puzzle solution's edges, as a set.

    `solution` is the stored form: vertex indices in order round the loop, with
    the first NOT repeated at the end (see docs/json-format.md).
    """
    return {edge_key(solution[i], solution[(i + 1) % len(solution)])
            for i in range(len(solution))}


def walls_per_face(faces, loop):
    """Face index -> how many of its edges the loop uses. That count IS the
    face's clue, for the faces that carry one."""
    return {index: sum(1 for ekey in face_edges(face) if ekey in loop)
            for (index, face) in enumerate(faces)}


def quiet_faces(faces, loop):
    """The faces the loop does not touch at all — the ones whose clue is 0."""
    return {index for (index, walls) in walls_per_face(faces, loop).items()
            if walls == 0}


def largest_quiet_patch(faces, loop, adjacency=None):
    """The size of the biggest connected group of faces the loop never touches.

    This is the measure of how DULL a puzzle looks. Scattered single 0s are fine,
    and a few are wanted — they read as organic. One big blank area is the defect:
    the first generated puzzle for the disdyakis triacontahedron had 55 such faces
    in one patch, a whole visible hemisphere of 0 clues with nothing to work on.

    Pass `adjacency` to reuse one already built for the same faces.
    """
    return largest_group(quiet_faces(faces, loop),
                         adjacency if adjacency is not None
                         else face_adjacency(faces))


def loop_ceiling(faces):
    """The longest loop this solid could possibly have: its vertex count.

    The loop is a simple cycle through vertices, so it can use at most one edge
    per vertex. Worth reporting a loop length against, since "42 edges" means
    nothing until you know whether the maximum is 62 or 140.
    """
    return len(vertex_degrees(faces))
