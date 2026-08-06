#!/usr/bin/env python3.11
"""Generate the dual of a grid -- which is how the Catalan solids are made.

Usage:
    util/genDual.py data/aC.json            # one dual, to stdout
    util/genDual.py --all-catalan           # all 13, written into data/

The dual of a polyhedron has a vertex for each of the original's faces and a face
for each of its vertices. This computes it by POLAR RECIPROCATION about a sphere
concentric with the solid: the vertex replacing a face is the pole of that face's
plane, so the face replacing an original vertex v lies in the plane x.v = 1 and is
therefore exactly flat -- no fitting, no canonicalization.

Which is what makes this the right way to get the Catalan solids. Reciprocation
preserves the symmetry group, and an Archimedean solid is vertex-transitive: some
symmetry carries any vertex to any other. Those symmetries carry the dual's faces
to each other, so the faces come out congruent, which is the defining property of
a Catalan solid. The radius of the reciprocating sphere only scales the result, so
there is no parameter to choose and nothing to tune.

Their names are Conway's: prefix the primal's notation with d, so the dual of the
cuboctahedron aC is daC, the rhombic dodecahedron. Those work as polyHedronisme
recipes too.

Each solid is verified before being written -- Euler's formula, congruent faces,
flatness and outward winding -- and one that fails is not written. See check().

The shebang selects python3.11, the interpreter carrying numpy.
"""
import json
import sys
from pathlib import Path

import numpy as np

# Our local modules. cycle_around orders a face's corners; json_format keeps the
# output readable (one line per vertex and per face).
import json_format
from genGoldberg import cycle_around

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# The 13 Catalan solids, by the gridId of the Archimedean solid each is dual to.
# Their categories, beyond the family: the rhombic dodecahedron is one of
# Fedorov's five parallelohedra (so it isn't also labelled a zonohedron -- only
# the narrowest category is listed, see docs/json-format.md); the rhombic
# triacontahedron is a zonohedron, its faces being rhombi and so centrally
# symmetric; and the duals of the two snub solids inherit their chirality. The
# rest are triangles or kites, which are not centrally symmetric.
CATALAN = {
    'tT': ('dtT', 'Triakis tetrahedron', ['Catalan solid']),
    'aC': ('daC', 'Rhombic dodecahedron', ['Catalan solid', 'parallelohedron']),
    'tC': ('dtC', 'Triakis octahedron', ['Catalan solid']),
    'tO': ('dtO', 'Tetrakis hexahedron', ['Catalan solid']),
    'eC': ('deC', 'Deltoidal icositetrahedron', ['Catalan solid']),
    'bC': ('dbC', 'Disdyakis dodecahedron', ['Catalan solid']),
    'sC': ('dsC', 'Pentagonal icositetrahedron', ['Catalan solid', 'chiral']),
    'aD': ('daD', 'Rhombic triacontahedron', ['Catalan solid', 'zonohedron']),
    'tD': ('dtD', 'Triakis icosahedron', ['Catalan solid']),
    'tI': ('dtI', 'Pentakis dodecahedron', ['Catalan solid']),
    'eD': ('deD', 'Deltoidal hexecontahedron', ['Catalan solid']),
    'bD': ('dbD', 'Disdyakis triacontahedron', ['Catalan solid']),
    'sD': ('dsD', 'Pentagonal hexecontahedron', ['Catalan solid', 'chiral']),
}

# How far two faces may differ and still count as congruent -- separately for
# lengths and for angles, since a tolerance in one unit says nothing about the
# other. (Comparing a quarter of a degree against a length tolerance of 1e-4 is
# what first made a perfectly good pentakis dodecahedron look wrong.)
#
# Both are set by the PRIMAL's stored precision, not by this arithmetic, which is
# exact. data/ keeps coordinates to 6 decimals, or 3 for the grids that came
# through obj2json.py -- data/tI.json is one, and its vertex radii vary by 1e-3 as
# a result, which the dual inherits as about a quarter of a degree in its angles.
# Both limits stay far tighter than any real difference: two faces of a Catalan
# solid that were genuinely different shapes would differ by a tenth of their
# size, and by degrees rather than fractions of one.
LENGTH_TOLERANCE = 1e-2
ANGLE_TOLERANCE_DEGREES = 1.0
# A face's corners should be coplanar exactly -- they satisfy x.v = 1 by
# construction -- so this only has to absorb the primal's rounding.
FLATNESS_TOLERANCE = 1e-3


def log(*args):
    """Progress and diagnostics, on stderr: stdout may carry the JSON."""
    print(*args, file=sys.stderr)


def face_pole(points, face):
    """The pole of a face's plane: the point p with p.v = 1 for every corner v.

    Least squares over all the corners rather than just three, so a face whose
    corners are only nearly coplanar still gives the best plane rather than
    whichever three came first.
    """
    corners = np.array([points[v] for v in face], dtype=float)
    (pole, *_) = np.linalg.lstsq(corners, np.ones(len(face)), rcond=None)
    return pole


def dual(points, faces):
    """The polar dual: (vertices, faces), one vertex per face and vice versa."""
    points = np.array(points, dtype=float)
    poles = np.array([face_pole(points, face) for face in faces])

    # Which faces meet at each vertex: those become the corners of the face
    # replacing that vertex.
    around = [[] for _ in range(len(points))]
    for (f, face) in enumerate(faces):
        for v in face:
            around[v].append(f)

    dual_faces = [cycle_around(points[v], poles[corners], corners)
                  for (v, corners) in enumerate(around)]
    return (poles, dual_faces)


def normalized(vertices):
    """Scaled to a circumradius of 1, as the rest of data/ is."""
    vertices = np.array(vertices, dtype=float)
    return vertices / np.abs(np.linalg.norm(vertices, axis=1)).max()


def face_shape(vertices, face):
    """A face's edge lengths and corner angles, both sorted.

    Two congruent faces have the same pair of lists. (Sorted, so the comparison
    doesn't depend on which corner each face starts from or which way round it
    is wound. That makes this a necessary rather than sufficient test for
    congruence -- but a face with the same edges and the same angles as another,
    on a solid built by reciprocating a uniform one, is congruent to it.)
    """
    corners = np.array([vertices[v] for v in face], dtype=float)
    edges = sorted(float(np.linalg.norm(corners[i] - corners[(i + 1) % len(face)]))
                   for i in range(len(face)))
    angles = []
    for i in range(len(face)):
        (u, v) = (corners[i - 1] - corners[i],
                  corners[(i + 1) % len(face)] - corners[i])
        cosine = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
        angles.append(float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))))
    return (edges, sorted(angles))


def check(vertices, faces, primal_points, primal_faces):
    """Verify the dual, and return a one-line description.

    Congruence is the point: it is what makes a dual of a uniform solid a Catalan
    solid, and it would be the first thing to go wrong if the reciprocation were
    off. Flatness is exact by construction (every corner of the face replacing
    vertex v satisfies x.v = 1), so it is checked as a guard on the arithmetic
    rather than as something that might be approximate.
    """
    edges = {frozenset((face[i], face[(i + 1) % len(face)]))
             for face in faces for i in range(len(face))}
    problems = []
    if len(vertices) != len(primal_faces):
        problems.append(f'{len(primal_faces)} vertices expected (one per primal '
                        f'face), got {len(vertices)}')
    if len(faces) != len(primal_points):
        problems.append(f'{len(primal_points)} faces expected (one per primal '
                        f'vertex), got {len(faces)}')
    if len(vertices) - len(edges) + len(faces) != 2:
        problems.append(f"Euler's formula fails: {len(vertices)} - {len(edges)} "
                        f'+ {len(faces)} != 2')

    shapes = [face_shape(vertices, face) for face in faces]
    (first_edges, first_angles) = shapes[0]
    (worst_length, worst_angle) = (0.0, 0.0)
    for (i, (edges_i, angles_i)) in enumerate(shapes[1:], start=1):
        if len(edges_i) != len(first_edges):
            problems.append(f'face {i} has {len(edges_i)} sides, face 0 has '
                            f'{len(first_edges)}')
            continue
        worst_length = max(worst_length,
                           max(abs(a - b) for (a, b) in zip(edges_i, first_edges)))
        worst_angle = max(worst_angle,
                          max(abs(a - b) for (a, b) in zip(angles_i, first_angles)))
    if worst_length > LENGTH_TOLERANCE:
        problems.append(f'faces differ in shape: edges by up to {worst_length:.2e}')
    if worst_angle > ANGLE_TOLERANCE_DEGREES:
        problems.append(f'faces differ in shape: angles by up to '
                        f'{worst_angle:.2f} degrees')

    centre = np.mean(vertices, axis=0)
    for (f, face) in enumerate(faces):
        corners = np.array([vertices[v] for v in face])
        normal = np.cross(corners[1] - corners[0], corners[2] - corners[1])
        if np.dot(normal, corners.mean(axis=0) - centre) <= 0:
            problems.append(f'face {f} is wound the wrong way')
        plane = normal / np.linalg.norm(normal)
        bow = max(abs(np.dot(plane, corner - corners[0])) for corner in corners)
        if bow > FLATNESS_TOLERANCE:
            problems.append(f'face {f} is not flat (bow {bow:.2e})')

    if problems:
        for problem in problems[:5]:
            log(f'Error: {problem}.')
        sys.exit(1)

    sides = len(first_edges)
    return (f'{len(vertices)} vertices, {len(edges)} edges, {len(faces)} faces, '
            f'all congruent {sides}-gons with edges '
            f'{first_edges[0]:.4f}-{first_edges[-1]:.4f} and angles '
            f'{first_angles[0]:.1f}-{first_angles[-1]:.1f} degrees '
            f'(agreeing to {worst_length:.0e} and {worst_angle:.2f} degrees)')


def build(primal_path, grid_id=None, grid_name=None, categories=None):
    """The dual of the grid in primal_path, as a grid dict ready to write."""
    primal = json.loads(Path(primal_path).read_text())
    (vertices, faces) = dual(primal['vertices'], primal['faces'])
    vertices = normalized(vertices)
    log(f'{primal["gridName"]} -> {grid_name or "dual"}: '
        + check(vertices, faces, primal['vertices'], primal['faces']))

    grid = {'gridId': grid_id or f'd{primal["gridId"]}',
            'gridName': grid_name or f'Dual of {primal["gridName"].lower()}'}
    if categories:
        grid['categories'] = categories
    grid['recipe'] = f'd{primal.get("recipe", primal["gridId"])}'
    grid['_comment'] = (f'Generated by util/genDual.py from '
                        f'{Path(primal_path).name} (polar reciprocation).')
    grid['vertices'] = [[round(float(c), 6) for c in v] for v in vertices]
    grid['faces'] = faces
    return grid


def all_catalan():
    """Write all 13 Catalan solids into data/, from the Archimedean solids there."""
    written = []
    for (primal_id, (grid_id, grid_name, categories)) in CATALAN.items():
        primal_path = DATA_DIR / f'{primal_id}.json'
        if not primal_path.exists():
            log(f'Skipping {grid_name}: {primal_path.name} is not in data/.')
            continue
        grid = build(primal_path, grid_id, grid_name, categories)
        path = DATA_DIR / f'{grid_id}.json'
        with open(path, 'w') as out:
            json_format.write_json(grid, out)
        written.append(grid_id)
    log(f'\nWrote {len(written)} Catalan solids: {", ".join(written)}')
    log('Now generate puzzles for them (util/fill_puzzles.py) and rebuild the '
        'catalogue (util/build_catalogue.py).')


def main():
    args = sys.argv[1:]
    if args == ['--all-catalan']:
        all_catalan()
        return
    if not args or args[0].startswith('-'):
        log('Usage: util/genDual.py <grid.json> [gridId] [gridName]')
        log('       util/genDual.py --all-catalan')
        sys.exit(1)

    # A named primal gets its Catalan name and categories for free.
    primal_id = json.loads(Path(args[0]).read_text())['gridId']
    (known_id, known_name, known_categories) = CATALAN.get(primal_id,
                                                          (None, None, None))
    grid = build(args[0],
                 args[1] if len(args) > 1 else known_id,
                 args[2] if len(args) > 2 else known_name,
                 known_categories)
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
