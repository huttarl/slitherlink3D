#!/usr/bin/env python3
"""Generate grid JSON for uniform polyhedra (Platonic and Archimedean solids)
from exact vertex coordinates.

Complements the other two grid sources: obj2json.py converts an OBJ exported
from polyHedronisme, and genRandomPolyh.py invents random sphere-like solids.
This script instead builds solids whose coordinates are known exactly, so the
geometry is as precise as floating point allows and needs no hand-tuning.

Usage:
    python3 util/genUniformPolyh.py            # list what it can generate
    python3 util/genUniformPolyh.py tO         # write data/tO.json
    python3 util/genUniformPolyh.py --all      # write all of them
    python3 util/genUniformPolyh.py tO --check # verify only, write nothing

How it works: given a vertex list, scipy's ConvexHull produces triangles, so
coplanar triangles are merged back into the real polygonal faces (hexagons,
octagons, ...), and each face's vertices are then ordered around its centre.
Faces come out wound counterclockwise as seen from outside, as the app and
COMPAS expect.

Every solid is verified before being written (--check reports without writing):
all edges the same length, all vertices the same distance from the centre, all
faces planar, the expected face-size census, and Euler's formula. A solid that
fails any check is NOT written, since a silently wrong grid would be worse than
a missing one.

Requires numpy and scipy (as genRandomPolyh.py does).
"""
import json
import sys
from itertools import permutations
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

import grid_checks
import grid_topology
import json_format

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PHI = (1 + 5 ** 0.5) / 2   # golden ratio, pervasive in the icosahedral solids


# --------------------------------------------------------------------------
# Coordinate helpers
# --------------------------------------------------------------------------

def all_sign_variants(point):
    """Every combination of signs for the non-zero coordinates of `point`.

    Coordinates that are zero are left alone (+0 and -0 would duplicate).
    """
    variants = {()}
    for value in point:
        options = (value,) if value == 0 else (value, -value)
        variants = {prefix + (option,) for prefix in variants for option in options}
    return variants


def all_permutations_with_signs(point):
    """All coordinate orderings of `point`, with all sign combinations."""
    result = set()
    for ordering in set(permutations(point)):
        result |= all_sign_variants(ordering)
    return result


def even_permutations_with_signs(point):
    """The three cyclic ('even') orderings of `point`, with all signs."""
    (a, b, c) = point
    result = set()
    for ordering in ((a, b, c), (b, c, a), (c, a, b)):
        result |= all_sign_variants(ordering)
    return result


def union(*vertex_sets):
    """Combine coordinate sets into a list of numpy points."""
    combined = set()
    for vertex_set in vertex_sets:
        combined |= vertex_set
    return [np.array(v, dtype=float) for v in sorted(combined)]


# --------------------------------------------------------------------------
# Platonic seeds (used as the starting point for the truncations)
# --------------------------------------------------------------------------

def tetrahedron():
    return [np.array(v, dtype=float) for v in
            [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]]


def cube():
    return union(all_sign_variants((1, 1, 1)))


def octahedron():
    return union(all_permutations_with_signs((1, 0, 0)))


def dodecahedron():
    return union(all_sign_variants((1, 1, 1)),
                 even_permutations_with_signs((0, 1 / PHI, PHI)))


def icosahedron():
    return union(even_permutations_with_signs((0, 1, PHI)))


# --------------------------------------------------------------------------
# Truncation
# --------------------------------------------------------------------------

def truncate(vertices, cut_fraction):
    """Truncate a solid by cutting every vertex off.

    Returns the vertices of the truncated solid: two points per edge of the
    original, at `cut_fraction` in from each end. (The caller hulls them.)

    Edges are found by hulling the seed and merging its coplanar facets into
    real faces first. Reading edges straight off the hull's simplices would be
    wrong: the hull triangulates any face with more than three sides, and those
    triangulation diagonals are not edges of the solid (a cube would appear to
    have 12 + 6 = 18 of them).

    For the result to be uniform (all edges equal) the cut fraction depends on
    the angle between edges at a vertex, i.e. on the seed's face polygon:
    a fraction of 1/(2 + 2*sin(interior_angle/2)) makes the shortened original
    edge and the new cut edge the same length -- see CUT_FRACTION_* below.
    """
    points = np.array(vertices)
    hull = ConvexHull(points)
    edges = set()
    for face in merge_coplanar_faces(points, hull):
        for i in range(len(face)):
            (a, b) = (face[i], face[(i + 1) % len(face)])
            edges.add((min(a, b), max(a, b)))

    truncated = []
    for (a, b) in edges:
        pa, pb = points[a], points[b]
        truncated.append(pa + cut_fraction * (pb - pa))
        truncated.append(pb + cut_fraction * (pa - pb))
    return truncated


# Cut fractions that make a truncation uniform, by the seed's face type.
# 2*sin(30 deg) = 1, 2*sin(45 deg) = sqrt(2), 2*sin(54 deg) = PHI.
CUT_FRACTION_TRIANGLE = 1 / 3
CUT_FRACTION_SQUARE = 1 / (2 + 2 ** 0.5)
CUT_FRACTION_PENTAGON = 1 / (2 + PHI)


# --------------------------------------------------------------------------
# The solids this script can generate
# --------------------------------------------------------------------------
# Each entry: file stem -> (name, categories, Conway recipe, vertex function,
#                           expected {face size: count})
SOLIDS = {
    # -- Platonic (the app already has T, cube, D, I; O completes the set) ---
    "O": ("Octahedron", ["Platonic solid", "deltahedron"], "O",
          octahedron, {3: 8}),

    # -- Archimedean: truncations of the Platonic solids -------------------
    "tT": ("Truncated tetrahedron", ["Archimedean solid"], "tT",
           lambda: truncate(tetrahedron(), CUT_FRACTION_TRIANGLE),
           {3: 4, 6: 4}),
    "tC": ("Truncated cube", ["Archimedean solid"], "tC",
           lambda: truncate(cube(), CUT_FRACTION_SQUARE),
           {3: 8, 8: 6}),
    "tO": ("Truncated octahedron", ["Archimedean solid", "parallelohedron"], "tO",
           lambda: truncate(octahedron(), CUT_FRACTION_TRIANGLE),
           {4: 6, 6: 8}),
    "tD": ("Truncated dodecahedron", ["Archimedean solid"], "tD",
           lambda: truncate(dodecahedron(), CUT_FRACTION_PENTAGON),
           {3: 20, 10: 12}),

    # -- Archimedean: rectifications and expansions ------------------------
    # NOTE two of these have Johnson-solid twins with exactly the same face
    # census, which we also ship: the rhombicuboctahedron (eC) vs the
    # pseudo-rhombicuboctahedron (J37, elongated square gyrobicupola), and the
    # rhombicosidodecahedron (eD) vs J75 (trigyrate rhombicosidodecahedron).
    # The twins differ only in how a band of faces is rotated, so they are easy
    # to mix up; generating these from coordinates avoids the risk entirely.
    "aC": ("Cuboctahedron", ["Archimedean solid", "quasiregular polyhedron"], "aC",
           lambda: union(all_permutations_with_signs((1, 1, 0))),
           {3: 8, 4: 6}),
    "eC": ("Rhombicuboctahedron", ["Archimedean solid"], "eC",
           lambda: union(all_permutations_with_signs((1, 1, 1 + 2 ** 0.5))),
           {3: 8, 4: 18}),
    "aD": ("Icosidodecahedron", ["Archimedean solid", "quasiregular polyhedron"], "aD",
           lambda: union(even_permutations_with_signs((0, 0, PHI)),
                         even_permutations_with_signs((1 / 2, PHI / 2, PHI ** 2 / 2))),
           {3: 20, 5: 12}),
    "eD": ("Rhombicosidodecahedron", ["Archimedean solid"], "eD",
           lambda: union(even_permutations_with_signs((1, 1, PHI ** 3)),
                         even_permutations_with_signs((PHI ** 2, PHI, 2 * PHI)),
                         even_permutations_with_signs((2 + PHI, 0, PHI ** 2))),
           {3: 20, 4: 30, 5: 12}),

    # -- Archimedean: omnitruncations, which need their own coordinates -----
    # (These are not literal truncations of the cuboctahedron /
    # icosidodecahedron: that would give rectangles rather than squares.)
    "bC": ("Truncated cuboctahedron", ["Archimedean solid"], "bC",
           lambda: union(all_permutations_with_signs(
               (1, 1 + 2 ** 0.5, 1 + 2 * 2 ** 0.5))),
           {4: 12, 6: 8, 8: 6}),
    "bD": ("Truncated icosidodecahedron", ["Archimedean solid"], "bD",
           lambda: union(
               even_permutations_with_signs((1 / PHI, 1 / PHI, 3 + PHI)),
               even_permutations_with_signs((2 / PHI, PHI, 1 + 2 * PHI)),
               even_permutations_with_signs((1 / PHI, PHI ** 2, -1 + 3 * PHI)),
               even_permutations_with_signs((2 * PHI - 1, 2, 2 + PHI)),
               even_permutations_with_signs((PHI, 3, 2 * PHI))),
           {4: 30, 6: 20, 10: 12}),
}


# --------------------------------------------------------------------------
# Hull -> polygonal faces
# --------------------------------------------------------------------------

def merge_coplanar_faces(points, hull, plane_tolerance=6):
    """Recover the real polygonal faces from a hull's triangulation.

    Groups the hull's simplices by their (outward) plane equation, then orders
    each group's vertices around the face. Returns a list of vertex-index
    lists, each wound counterclockwise as seen from outside the solid.

    plane_tolerance is the number of decimal places used to decide that two
    simplices lie in the same plane.
    """
    groups = {}
    for (simplex, equation) in zip(hull.simplices, hull.equations):
        key = tuple(np.round(equation, plane_tolerance))
        groups.setdefault(key, set()).update(int(i) for i in simplex)

    faces = []
    for (equation, vertex_indices) in groups.items():
        normal = np.array(equation[:3], dtype=float)   # points outward
        normal /= np.linalg.norm(normal)
        indices = list(vertex_indices)
        centre = np.mean([points[i] for i in indices], axis=0)

        # Build a 2D frame (u, v) in the face's plane with u x v = normal, so
        # that sorting by angle gives counterclockwise-from-outside order.
        seed = points[indices[0]] - centre
        u = seed - np.dot(seed, normal) * normal
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)

        def angle_of(index):
            offset = points[index] - centre
            return np.arctan2(np.dot(offset, v), np.dot(offset, u))

        faces.append(sorted(indices, key=angle_of))
    return faces


def build_solid(vertex_function):
    """Turn a vertex-list function into (points, faces) with polygonal faces."""
    vertices = vertex_function()
    points = np.array(vertices, dtype=float)
    # Centre on the origin and scale so the outermost vertex sits at radius 1,
    # matching what the app's normalizeVertices() would do anyway.
    points -= points.mean(axis=0)
    points /= np.max(np.linalg.norm(points, axis=1))
    hull = ConvexHull(points)
    faces = merge_coplanar_faces(points, hull)
    return (points, faces)


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

def verify(stem, points, faces, expected_census, tolerance=1e-6):
    """Check that a generated solid really is the uniform polyhedron wanted.

    Uniformity is the distinguishing property: every edge the same length and
    every vertex the same distance from the centre, which holds for every Platonic
    and Archimedean solid and for almost nothing else. The rest -- census, Euler,
    flat faces, a closed and outward-wound surface -- any solid here must satisfy.

    Radii are measured from the ORIGIN rather than from the centroid, since these
    coordinates are built centred there; using the centroid would hide a solid
    that came out lopsided.

    Returns (ok, list of message strings) -- messages are reported either way,
    since the measurements are informative even when everything passes.

    (`tolerance` used to default to 1e-9 and then be ignored, the body having
    three hardcoded 1e-6 tests. It now means what it says, at the value that was
    really in force.)
    """
    problems = (grid_checks.check_census(faces, expected_census)
                + grid_checks.check_euler(points, faces)
                + grid_checks.check_equal_edge_lengths(points, faces, tolerance)
                + grid_checks.check_equal_vertex_radii(points, tolerance,
                                                       centre=[0.0, 0.0, 0.0])
                + grid_checks.check_flat_faces(points, faces, tolerance)
                + grid_checks.check_closed_surface(faces)
                + grid_checks.check_outward_winding(points, faces,
                                                    centre=[0.0, 0.0, 0.0]))

    edges = grid_topology.edges_of(faces)
    lengths = [grid_checks.distance(points[a], points[b]) for (a, b) in edges]
    worst_bow = max(grid_checks.face_bow(grid_checks.corners_of(points, face))
                    for face in faces)
    summary = (f"V={len(points)} E={len(edges)} F={len(faces)} "
               f"faces={grid_checks.face_census(faces)} "
               f"edge={min(lengths):.6f} planarity={worst_bow:.2g}")
    return (not problems, problems + [summary])


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def write_grid(stem, points, faces):
    """Write data/<stem>.json in the app's grid format."""
    (name, categories, recipe, _, _) = SOLIDS[stem]
    grid = {
        "gridId": stem,
        "gridName": name,
        "categories": categories,
        "recipe": recipe,
        # Where the coordinates came from (see docs/json-format.md). Unusually
        # among the generators, this one really is a command you can paste back:
        # the name and categories come from SOLIDS above rather than the command
        # line, so there is nothing a re-run could quietly drop.
        # Spelled out rather than taken from argv, since --all writes all of them and
        # each file should name the command that makes IT. See
        # json_format.source_line.
        "source": json_format.source_line([stem]),
        # Round to a sane precision: the app normalizes anyway, and shorter
        # numbers keep the data files small and readable.
        "vertices": [[round(float(c), 9) for c in point] for point in points],
        "faces": [[int(i) for i in face] for face in faces],
    }
    path = DATA_DIR / f"{stem}.json"
    with open(path, "w") as f:
        # One line per vertex and per face, rather than the whole grid on one
        # line: these files get read by people. See util/json_format.py.
        json_format.write_json(grid, f)
    return path


def usage():
    print(__doc__.strip().split("\n\n")[0])
    print("\nAvailable solids:")
    for (stem, (name, categories, recipe, _, census)) in SOLIDS.items():
        print(f"  {stem:4s} {name:32s} {categories[0]:18s} faces={census}")
    print("\nUsage: python3 util/genUniformPolyh.py [--all|<stem>...] [--check]")
    sys.exit(1)


def main():
    args = [a for a in sys.argv[1:]]
    check_only = "--check" in args
    args = [a for a in args if a != "--check"]

    if not args:
        usage()  # exits
    stems = list(SOLIDS) if args == ["--all"] else args

    failures = 0
    for stem in stems:
        if stem not in SOLIDS:
            print(f"{stem}: unknown; run with no arguments to list the choices.",
                  file=sys.stderr)
            failures += 1
            continue
        (name, _, _, vertex_function, census) = SOLIDS[stem]
        (points, faces) = build_solid(vertex_function)
        (ok, messages) = verify(stem, points, faces, census)
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {stem:4s} {name}")
        for message in messages:
            print(f"         {message}")
        if not ok:
            failures += 1
            print(f"         not written, because verification failed")
        elif not check_only:
            print(f"         wrote {write_grid(stem, points, faces)}")

    if failures:
        print(f"\n{failures} solid(s) failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
