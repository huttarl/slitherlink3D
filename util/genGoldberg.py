#!/usr/bin/env python3.11
"""Generate a Goldberg polyhedron GP(m,n) as a grid JSON file.

Usage: util/genGoldberg.py m n [gridId] [gridName]
Output is written to stdout; progress and the self-check go to stderr.
For the JSON format, see docs/json-format.md.

A Goldberg polyhedron GP(m,n) has 12 pentagons and everything else hexagons,
with three faces at every vertex. Its size is set by the triangulation number
T = m^2 + mn + n^2:

    faces = 10T + 2,  vertices = 20T,  edges = 30T

GP(1,0) is the dodecahedron and GP(1,1) the truncated icosahedron, so the
first one this script produces that we don't already have is GP(1,2) (T = 7).
GP(m,n) with m != n and n != 0 is chiral; this script produces one of the two
mirror images, whichever the construction below happens to land on.

In Conway notation GP(1,2) and its mirror image GP(2,1) are the whirl of the
dodecahedron, "wD" -- whirl keeps the 12 original faces and adds two hexagons
per edge, which is 12 + 60 faces and 20 + 4*30 vertices, exactly T = 7. So
https://levskaya.github.io/polyhedronisme/?recipe=wD shows this solid, up to
handedness. Larger ones have no such short recipe, which is why this script
works from (m,n) instead.

How it works, in two steps, because each is easy while building the Goldberg
polyhedron's hexagons directly is not:

 1. Build the GEODESIC polyhedron GD(m,n), the Goldberg's dual: subdivide each
    face of an icosahedron along the triangular lattice, using the lattice
    vector (m,n) as one side of the subdivided triangle, and push the resulting
    points out onto the unit sphere. Its triangles then come free, as the convex
    hull of those points.

 2. Take the POLAR DUAL of that hull about the unit sphere: each triangle
    becomes a vertex, and each of the geodesic's vertices becomes a face. Polar
    reciprocation rather than "join the face centroids", because it gives
    exactly FLAT faces -- every vertex of the face around geodesic vertex v
    satisfies v.x = 1, which is a plane. Centroids projected back onto the
    sphere would leave the hexagons very slightly saddle-shaped.

The counts above are then checked against what came out (see main), so a
mistake in the lattice can't quietly produce a plausible-looking solid.
"""
import json
import sys

import numpy as np
from scipy.spatial import ConvexHull

# Our local modules
import grid_checks
import grid_topology
import json_format

# Coordinates are compared after rounding to this many decimals, to weld the
# lattice points that neighbouring icosahedron faces share along an edge.
# Well inside the gap between distinct points on any grid we would generate.
WELD_DECIMALS = 6

# Slack for "is this lattice point inside the triangle": points exactly on an
# edge are wanted, and land on the boundary only up to rounding error.
INSIDE_EPSILON = 1e-9

# Conway notation for the small cases, for the optional "recipe" field (see
# docs/json-format.md), which links a grid to polyHédronisme. Only the ones with
# a short recipe: GP(1,2) is the whirl of the dodecahedron (whirl keeps the 12
# original faces and adds two hexagons per edge -- 72 faces, 140 vertices), and
# for a chiral pair either handedness answers to the same recipe. Bigger ones
# have no such notation, which is why this script works from (m,n) instead.
RECIPES = {
    (1, 0): 'D',        # dodecahedron
    (1, 1): 'tI',       # truncated icosahedron
    (2, 0): 'cD',       # chamfered dodecahedron
    (1, 2): 'wD',       # whirled dodecahedron, and its mirror image GP(2,1)
    (2, 1): 'wD',
}


def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def icosahedron():
    """The 12 unit-sphere vertices and 20 triangles of an icosahedron.

    Returns (vertices, faces) with each face wound counterclockwise seen from
    outside, which is the convention grid files follow (see docs/json-format.md).
    """
    phi = (1 + 5 ** 0.5) / 2
    # The three cyclic permutations of (0, +-1, +-phi).
    points = []
    for (a, b) in [(1, phi), (-1, phi), (1, -phi), (-1, -phi)]:
        points += [(0, a, b), (a, b, 0), (b, 0, a)]
    vertices = np.array(points, dtype=float)
    vertices /= np.linalg.norm(vertices, axis=1)[:, None]
    faces = [orient_outward(vertices, simplex)
             for simplex in ConvexHull(vertices).simplices]
    return (vertices, faces)


def orient_outward(vertices, face):
    """The same face, wound counterclockwise as seen from outside the solid.

    The solid is centred on the origin here, so "outside" is simply the
    direction of the face itself: the right-hand-rule normal should point the
    same way as the face's own centroid.
    """
    face = list(face)
    p = vertices[face]
    normal = np.cross(p[1] - p[0], p[2] - p[0])
    if np.dot(normal, p.mean(axis=0)) < 0:
        face.reverse()
    return face


def lattice_barycentrics(m, n):
    """Where the geodesic's vertices sit within one icosahedron face.

    Each face is mapped onto the triangle whose corners are the lattice points
    0, (m,n) and (m,n) turned 60 degrees -- the equilateral triangle that the
    Goldberg construction cuts out of the hexagonal lattice. Every lattice point
    inside or on that triangle is a vertex of the geodesic polyhedron.

    Returned as barycentric weights, so the caller can place them on any face.
    Points on a shared edge come out at the same place from either face (the
    fractions along an edge are symmetric), and the weld in geodesic_points
    then merges them.

    @returns list of (wA, wB, wC), each summing to 1
    """
    # A basis for the hexagonal lattice: two unit vectors 60 degrees apart.
    u = np.array([1.0, 0.0])
    v = np.array([0.5, 3 ** 0.5 / 2])
    # Turning (m,n) by 60 degrees takes u to v and v to v - u, hence:
    corner1 = m * u + n * v
    corner2 = -n * u + (m + n) * v
    # Barycentric coordinates within (origin, corner1, corner2).
    to_barycentric = np.linalg.inv(np.column_stack([corner1, corner2]))

    # The triangle fits inside this range of lattice steps either way, with a
    # step of slack; the containment test below does the real work.
    reach = m + n + 1
    weights = []
    for i in range(-reach, reach + 1):
        for j in range(-reach, reach + 1):
            (s, t) = to_barycentric @ (i * u + j * v)
            if (s >= -INSIDE_EPSILON and t >= -INSIDE_EPSILON
                    and s + t <= 1 + INSIDE_EPSILON):
                weights.append((1 - s - t, s, t))
    return weights


def geodesic_points(m, n):
    """The vertices of GD(m,n), on the unit sphere.

    The icosahedron's own 12 vertices are among them: they are the corners of
    every face's lattice triangle.
    """
    (ico_vertices, ico_faces) = icosahedron()
    weights = lattice_barycentrics(m, n)

    points = {}
    for face in ico_faces:
        corners = ico_vertices[face]
        for w in weights:
            p = np.array(w) @ corners
            p /= np.linalg.norm(p)
            # Weld: neighbouring faces generate the shared edge's points twice.
            points[tuple(np.round(p, WELD_DECIMALS))] = p
    return np.array(list(points.values()))


def polar_dual(points):
    """The polar dual of the convex hull of `points`, about the unit sphere.

    @param points: on the unit sphere, so every hull face's plane misses the
        origin and has a pole
    @returns (vertices, faces) -- one vertex per hull triangle, one face per
        input point, each face flat and wound counterclockwise seen from outside
    """
    hull = ConvexHull(points)

    # The pole of a face's plane: the point p with p.a = p.b = p.c = 1, for the
    # face's three corners. Every dual vertex of the face around `a` then
    # satisfies a.p = 1, which is what makes that face flat.
    poles = np.array([np.linalg.solve(points[simplex], np.ones(3))
                      for simplex in hull.simplices])

    # Which hull triangles meet at each point: those are the corners of that
    # point's face in the dual.
    around = [[] for _ in range(len(points))]
    for (t, simplex) in enumerate(hull.simplices):
        for vertex in simplex:
            around[vertex].append(t)

    faces = [cycle_around(points[v], poles[corners], corners)
             for (v, corners) in enumerate(around)]
    return (poles, faces)


def cycle_around(axis, corners, corner_ids):
    """Put a face's corners in order around the axis pointing out through it.

    ConvexHull hands back the triangles at a vertex in no particular order,
    while a face is a cycle. Sorting them by angle in the plane across the axis
    puts them in order, and measuring that angle in a frame that is right-handed
    about the (outward) axis makes the result counterclockwise seen from outside.
    """
    axis = axis / np.linalg.norm(axis)
    # Any direction across the axis will do as the zero of the angle.
    seed = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(seed, axis)) > 0.9:
        seed = np.array([0.0, 1.0, 0.0])
    e1 = np.cross(axis, seed)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)

    def angle(corner):
        d = corner - axis * np.dot(corner, axis)
        return np.arctan2(np.dot(d, e2), np.dot(d, e1))

    order = sorted(range(len(corner_ids)), key=lambda k: angle(corners[k]))
    return [int(corner_ids[k]) for k in order]


def check(m, n, vertices, faces):
    """Verify the solid against what GP(m,n) must be, and report it.

    Cheap insurance on the lattice arithmetic: a wrong set of lattice points
    still yields *a* polyhedron, but not one with these counts.

    @returns a one-line description, or exits if anything is off
    """
    T = m * m + m * n + n * n
    sizes = grid_checks.face_census(faces)

    problems = (
        grid_checks.check_counts(vertices, faces,
                                 {'vertices': 20 * T, 'faces': 10 * T + 2,
                                  'edges': 30 * T})
        # 12 pentagons and hexagons for the rest, at three faces per vertex, is
        # what makes a solid Goldberg. Euler forces exactly 12 once no face is
        # anything but a pentagon or hexagon.
        + ([f'12 pentagons expected, got {sizes.get(5, 0)}']
           if sizes.get(5) != 12 else [])
        + ([f'only pentagons and hexagons expected, got {sorted(sizes)}']
           if set(sizes) - {5, 6} else [])
        + grid_checks.check_vertex_degrees(faces, {3})
        # Flatness is the point of going via the polar dual, so it is checked
        # tightly: these faces should be flat to floating-point noise.
        + grid_checks.check_flat_faces(vertices, faces, 1e-9)
        + grid_checks.check_closed_surface(faces)
        + grid_checks.check_outward_winding(vertices, faces))

    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)

    worst_bow = max(grid_checks.face_bow(grid_checks.corners_of(vertices, face))
                    for face in faces)
    return (f'GP({m},{n}): T={T}, {len(vertices)} vertices, '
            f'{len(grid_topology.edges_of(faces))} edges, '
            f'{len(faces)} faces ({grid_checks.census_text(faces)}); '
            f'faces flat to {worst_bow:.1e}')


def goldberg(m, n):
    """GP(m,n) as (vertices, faces), scaled to a circumradius of 1.

    The scale matches the rest of data/: the app's camera distances and its
    edge and vertex radii are all chosen for a solid about that size.
    """
    (vertices, faces) = polar_dual(geodesic_points(m, n))
    return (vertices / np.abs(np.linalg.norm(vertices, axis=1)).max(), faces)


def main():
    if len(sys.argv) < 3:
        log('Usage: python3 genGoldberg.py m n [gridId] [gridName]')
        sys.exit(1)
    (m, n) = (int(sys.argv[1]), int(sys.argv[2]))
    if m < 1 or n < 0:
        log('Error: GP(m,n) wants m >= 1 and n >= 0.')
        sys.exit(1)
    grid_id = sys.argv[3] if len(sys.argv) > 3 else f'gp{m}{n}'
    grid_name = sys.argv[4] if len(sys.argv) > 4 else f'Goldberg GP({m},{n})'

    (vertices, faces) = goldberg(m, n)
    log(check(m, n, vertices, faces))

    # "Miscellaneous" is the family for a solid in none of the classical ones,
    # the picker having to file every solid under exactly one family. GP(1,0) and
    # GP(1,1) are the exceptions -- they're the dodecahedron and the truncated
    # icosahedron, so they're Platonic and Archimedean respectively -- and this
    # script isn't how those two got into data/.
    categories = ['Miscellaneous', 'Goldberg']
    # GP(m,n) is chiral unless it is its own mirror image, which happens only
    # along the two symmetric edges of the (m,n) family.
    if n != 0 and m != n:
        categories.append('chiral')

    # Built key by key to keep data/'s usual order, with the optional fields in
    # the middle where the other grid files have them.
    grid = {'gridId': grid_id, 'gridName': grid_name, 'categories': categories}
    if (m, n) in RECIPES:
        grid['recipe'] = RECIPES[(m, n)]
    # So the file says where it came from, and can be reproduced exactly.
    grid['_comment'] = f'Generated by util/genGoldberg.py {m} {n}.'
    grid['vertices'] = [[round(float(c), 6) for c in v] for v in vertices]
    grid['faces'] = faces
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
