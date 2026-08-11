#!/usr/bin/env python3
"""Generate a Goldberg polyhedron GP(m,n), or its dual the geodesic polyhedron
GD(m,n), as a grid JSON file.

Usage: util/genGoldberg.py [--geodesic] [--base=NAME] m n [gridId] [gridName]
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

--geodesic stops after step 1 and writes GD(m,n) itself, which needs no work the
Goldberg didn't already need. Being the dual, it has the same counts with faces
and vertices swapped,

    faces = 20T,  vertices = 10T + 2,  edges = 30T

all of them triangles, with 5 or 6 meeting at each vertex -- exactly 12 of 5,
those being the icosahedron's own corners, the only places a hexagonal patch
can't form. These are the solids of geodesic domes and of 3D modellers'
icospheres. Which of the three classes one belongs to is just what (m,n) says:
n = 0 is Class I, m = n is Class II, and anything else is the chiral Class III.
See https://en.wikipedia.org/wiki/Geodesic_polyhedron. GD(1,0) is the
icosahedron and GD(1,1) the pentakis dodecahedron, both of which data/ already
has (as I and dtI), so the first new one here is GD(2,0).

--base=octahedron or --base=tetrahedron subdivides one of those instead. The
lattice work is the same either way -- lattice_barycentrics places points inside
an abstract triangle and has never cared which solid's face it was -- so this is
only a matter of which base to map them onto. It is the {3,q+} of the notation in
that article: q is how many triangles meet at the base's own corners, so 5 for the
icosahedron, 4 for the octahedron, 3 for the tetrahedron. Only the counts change,
and they follow from the base rather than being written down per case:

    faces = T * (base's faces),  edges = 3/2 * faces,  vertices = 2 - faces + edges

with the base's own corners keeping their q triangles and every other vertex
getting 6. Each base's (1,0) and (1,1) are already in data/, those being the base
itself and its kis (O and dtO for the octahedron, T and dtT for the tetrahedron),
so the first new one on any base is again (2,0).

Fewer triangles at a corner means a blunter, less sphere-like solid, which is why
the icosahedron is the default and the one geodesic domes are built on. It also
shows in the edge-length spread the check reports: at (2,1) the icosahedron's
edges vary by a factor of 1.22, the octahedron's by 1.62 and the tetrahedron's by
2.56.

One combination is degenerate and the check refuses it: {3,3+}(1,1). Its points
are the tetrahedron's 4 corners plus one per face, and a tetrahedron's face
centres projected onto the sphere are the corners of the DUAL tetrahedron -- so
all 8 points together are exactly a cube's vertices. There is no triakis
tetrahedron to be had, because on the sphere the pyramid apex lands flush in the
plane of the square it should have stood on, and the hull triangulates those
squares arbitrarily instead. Nothing to fix: data/ has the real triakis
tetrahedron as dtT, whose apexes stand out because it is a Catalan solid rather
than a spherical one. The other tetrahedral cases -- (1,0), (2,0), (2,1), (3,0),
(2,2) -- all come out properly.

The
Goldberg path takes no --base: its check knows that a Goldberg polyhedron has
exactly 12 pentagons, which is true of the icosahedral family alone -- an
octahedral base would give 6 squares and hexagons, a different solid needing its
own verification, and nothing here has asked for one.

The geodesic is NOT the same shape as the Conway kis-operator solid with the same
topology, though it is easy to assume so: every vertex here sits on the sphere,
which is what keeps the edge lengths nearly equal, whereas a kis pyramid's apex
stands out from the face it was raised on. Hence the check below reports the
edge-length spread for a geodesic -- near-equal edges are the whole point of one,
and they are what makes it worth drawing.

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

# The same for the geodesics, which are the duals -- so mostly the recipe above
# with Conway's d in front. Note these recipes give the right TOPOLOGY and not
# quite this shape: polyHédronisme's dual leaves the vertices where reciprocation
# puts them, off the sphere (see the note on kis in the docstring). Good enough
# for its purpose, which is to let a player go and look at the solid.
#
# Keyed by base, since each base has its own family. The pattern is the same all
# the way down -- (1,0) is the base, (1,1) its kis, (2,0) the dual of a chamfer,
# (2,1) the dual of a whirl -- because a chamfer and a whirl are what T=4 and T=7
# amount to on the dual side. The kis spellings 'kD'/'kC'/'kT' and the dual ones
# 'dcD'/'dwC' describe the same solids by different routes; the duals are the
# spelling used past (1,1) because they need no face-size argument.
GEODESIC_RECIPES = {
    'icosahedron': {
        (1, 0): 'I',        # icosahedron
        (1, 1): 'kD',       # pentakis dodecahedron: a pyramid on each face of D
        (2, 0): 'dcD',      # dual of the chamfered dodecahedron
        (1, 2): 'dwD',      # dual of the whirled dodecahedron, either handedness
        (2, 1): 'dwD',
    },
    'octahedron': {
        (1, 0): 'O',        # octahedron
        (1, 1): 'kC',       # tetrakis hexahedron, which data/ has as dtO
        (2, 0): 'dcC',      # dual of the chamfered cube
        (1, 2): 'dwC',      # dual of the whirled cube: the tetrakis snub cube
        (2, 1): 'dwC',
    },
    'tetrahedron': {
        (1, 0): 'T',        # tetrahedron
        (1, 1): 'kT',       # triakis tetrahedron, which data/ has as dtT
        (2, 0): 'dcT',      # dual of the chamfered tetrahedron
        (1, 2): 'dwT',      # dual of the whirled tetrahedron
        (2, 1): 'dwT',
    },
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
    return (vertices, hull_faces(vertices))


def octahedron():
    """The 6 unit-sphere vertices and 8 triangles of an octahedron.

    Same contract as icosahedron(): unit vectors, faces wound counterclockwise
    seen from outside. The six vertices are the +-axes, already unit length.
    """
    vertices = np.array([(1., 0, 0), (-1., 0, 0), (0, 1., 0),
                         (0, -1., 0), (0, 0, 1.), (0, 0, -1.)])
    return (vertices, hull_faces(vertices))


def tetrahedron():
    """The 4 unit-sphere vertices and 4 triangles of a tetrahedron.

    Alternate corners of a cube, which is the shortest way to write it down.
    """
    vertices = np.array([(1., 1, 1), (1., -1, -1), (-1., 1, -1), (-1., -1, 1)])
    vertices /= np.linalg.norm(vertices, axis=1)[:, None]
    return (vertices, hull_faces(vertices))


# The bases a geodesic can be built on: the three regular solids with triangular
# faces, which is what {3,q+} in the notation means (q triangles at a base corner).
# Only these three, because subdividing a face is only well defined -- and only
# lands back on the sphere evenly -- when the face is an equilateral triangle.
BASES = {
    'icosahedron': icosahedron,
    'octahedron': octahedron,
    'tetrahedron': tetrahedron,
}


def hull_faces(vertices):
    """The triangles of the convex hull of `vertices`, wound outward.

    Every point on a sphere is a vertex of the hull of any set of points on that
    sphere, so for our purposes this loses nothing and saves writing each base's
    faces out by hand (where a mistyped index would be easy to miss).
    """
    return [orient_outward(vertices, simplex)
            for simplex in ConvexHull(vertices).simplices]


def orient_outward(vertices, face):
    """The same face, wound counterclockwise as seen from outside the solid.

    The solid is centred on the origin here, so "outside" is simply the
    direction of the face itself: the right-hand-rule normal should point the
    same way as the face's own centroid.

    Plain ints, not the numpy ones ConvexHull hands back, since a face list may
    be written straight out as JSON, which has no idea what an int32 is.
    """
    face = [int(vertex) for vertex in face]
    p = vertices[face]
    normal = np.cross(p[1] - p[0], p[2] - p[0])
    if np.dot(normal, p.mean(axis=0)) < 0:
        face.reverse()
    return face


def lattice_barycentrics(m, n):
    """Where the geodesic's vertices sit within one face of the base solid.

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


def geodesic_points(m, n, base='icosahedron'):
    """The vertices of the geodesic subdividing `base`, on the unit sphere.

    The base's own vertices are among them: they are the corners of every face's
    lattice triangle.

    @param base: a key of BASES
    """
    (base_vertices, base_faces) = BASES[base]()
    weights = lattice_barycentrics(m, n)

    points = {}
    for face in base_faces:
        corners = base_vertices[face]
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


def check(m, n, vertices, faces, want_geodesic, base='icosahedron'):
    """Verify the solid against what it must be, and report it.

    Cheap insurance on the lattice arithmetic: a wrong set of lattice points
    still yields *a* polyhedron, but not one with these counts.

    @returns a one-line description, or exits if anything is off
    """
    T = m * m + m * n + n * n
    sizes = grid_checks.face_census(faces)

    if want_geodesic:
        # Derived from the base rather than tabulated per case, so a new base is
        # checked as strictly as the icosahedron is. Each of the base's faces
        # becomes T triangles; every triangle has 3 edges and every edge is shared
        # by 2 of them; and Euler then fixes the vertices.
        (base_vertices, base_faces) = BASES[base]()
        face_count = T * len(base_faces)
        edge_count = 3 * face_count // 2
        expected = {'vertices': 2 - face_count + edge_count,
                    'faces': face_count, 'edges': edge_count}
        # The base's corners keep the q triangles they had, and the subdivision
        # packs everything else hexagonally -- so all triangles, degrees in
        # {q, 6}, and exactly as many q-valent vertices as the base had corners.
        # A different count means the lattice went wrong.
        corners = len(base_vertices)
        q = 3 * len(base_faces) // corners
        q_valent = sum(1 for degree in grid_topology.vertex_degrees(faces).values()
                       if degree == q)
        shape_problems = []
        if set(sizes) != {3}:
            shape_problems.append(f'only triangles expected, got {sorted(sizes)}')
        shape_problems += grid_checks.check_vertex_degrees(faces, {q, 6})
        if q_valent != corners:
            shape_problems.append(f'{corners} {q}-valent vertices expected '
                                  f'(the {base}\'s own corners), got {q_valent}')
        # {3,q+} rather than GD(m,n), which would not say which base -- and the
        # classes those names carry are per base.
        name = f'{{3,{q}+}}({m},{n})'
    else:
        name = f'GP({m},{n})'
        expected = {'vertices': 20 * T, 'faces': 10 * T + 2, 'edges': 30 * T}
        # 12 pentagons and hexagons for the rest, at three faces per vertex, is
        # what makes a solid Goldberg. Euler forces exactly 12 once no face is
        # anything but a pentagon or hexagon.
        shape_problems = []
        if sizes.get(5) != 12:
            shape_problems.append(f'12 pentagons expected, got {sizes.get(5, 0)}')
        if set(sizes) - {5, 6}:
            shape_problems.append(
                f'only pentagons and hexagons expected, got {sorted(sizes)}')
        shape_problems += grid_checks.check_vertex_degrees(faces, {3})

    problems = (
        grid_checks.check_counts(vertices, faces, expected)
        + shape_problems
        # Flatness is the point of going via the polar dual, so it is checked
        # tightly: these faces should be flat to floating-point noise. (A
        # geodesic's triangles cannot bow at all, so for those this passes for
        # free -- left in rather than skipped, since it costs nothing and would
        # catch a face that somehow came out with four corners.)
        + grid_checks.check_flat_faces(vertices, faces, 1e-9)
        + grid_checks.check_closed_surface(faces)
        + grid_checks.check_outward_winding(vertices, faces))

    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)

    report = (f'{name}: T={T}, {len(vertices)} vertices, '
              f'{len(grid_topology.edges_of(faces))} edges, '
              f'{len(faces)} faces ({grid_checks.census_text(faces)}); ')
    if want_geodesic:
        # Near-equal edges are what a geodesic is for, so report the spread
        # rather than the flatness that came free. It also decides how the app
        # draws the solid: the edge radius follows the median edge length (see
        # radiusScale in js/geometryUtils.js).
        lengths = [grid_checks.distance(vertices[a], vertices[b])
                   for (a, b) in grid_topology.edges_of(faces)]
        return (report + f'edges {min(lengths):.4f} to {max(lengths):.4f} '
                f'(ratio {max(lengths) / min(lengths):.3f})')
    worst_bow = max(grid_checks.face_bow(grid_checks.corners_of(vertices, face))
                    for face in faces)
    return report + f'faces flat to {worst_bow:.1e}'


def goldberg(m, n):
    """GP(m,n) as (vertices, faces), scaled to a circumradius of 1.

    The scale matches the rest of data/: the app's camera distances and its
    edge and vertex radii are all chosen for a solid about that size.
    """
    (vertices, faces) = polar_dual(geodesic_points(m, n))
    return (vertices / np.abs(np.linalg.norm(vertices, axis=1)).max(), faces)


def geodesic(m, n, base='icosahedron'):
    """The geodesic as (vertices, faces): step 1 of the construction, on its own.

    No scaling to do, unlike goldberg() above: geodesic_points pushed every point
    onto the unit sphere, so the circumradius is already the 1 that the rest of
    data/ uses.
    """
    points = geodesic_points(m, n, base)
    return (points, hull_faces(points))


USAGE = ('Usage: python3 genGoldberg.py [--geodesic] [--base=NAME] m n '
         '[gridId] [gridName]\n'
         f'       --base is one of {", ".join(BASES)} (default icosahedron), '
         'and needs --geodesic.')


def main():
    # The options are taken out of the arguments first, so the positional ones
    # keep the places the usage message gives them wherever the flags are written.
    options = [arg for arg in sys.argv[1:] if arg.startswith('--')]
    argv = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    want_geodesic = '--geodesic' in options
    base = 'icosahedron'
    for option in options:
        if option.startswith('--base='):
            base = option.split('=', 1)[1]
        elif option != '--geodesic':
            log(f'Error: unknown option {option}.\n{USAGE}')
            sys.exit(1)

    if len(argv) < 2:
        log(USAGE)
        sys.exit(1)
    (m, n) = (int(argv[0]), int(argv[1]))
    if m < 1 or n < 0:
        log('Error: (m,n) wants m >= 1 and n >= 0.')
        sys.exit(1)
    if base not in BASES:
        log(f'Error: unknown base {base!r}; expected one of {", ".join(BASES)}.')
        sys.exit(1)
    # Refused rather than ignored: the Goldberg check insists on 12 pentagons,
    # which only the icosahedral family has, so any other base would either fail
    # that check or -- worse, if it were relaxed -- write out a solid nothing had
    # actually verified. See the docstring.
    if base != 'icosahedron' and not want_geodesic:
        log(f'Error: --base={base} needs --geodesic; the Goldberg polyhedra here '
            'are the icosahedral family only.')
        sys.exit(1)

    kind = 'gd' if want_geodesic else 'gp'
    # The default id and name carry the base unless it is the usual icosahedron,
    # whose geodesics are just "GD(m,n)" -- so gd21 stays gd21 rather than
    # becoming gd521 now that other bases exist.
    suffix = '' if base == 'icosahedron' else f'-{base}'
    default_name = (f'Geodesic GD({m},{n}){suffix}' if want_geodesic
                    else f'Goldberg GP({m},{n})')
    grid_id = argv[2] if len(argv) > 2 else f'{kind}{m}{n}{suffix}'
    grid_name = argv[3] if len(argv) > 3 else default_name

    (vertices, faces) = (geodesic(m, n, base) if want_geodesic
                         else goldberg(m, n))
    log(check(m, n, vertices, faces, want_geodesic, base))

    # "Miscellaneous" is the family for a solid in none of the classical ones,
    # the picker having to file every solid under exactly one family. The (1,0)
    # and (1,1) of every family are the exceptions -- GP(1,0) and GP(1,1) are the
    # dodecahedron and the truncated icosahedron, so Platonic and Archimedean,
    # while each base's own geodesics start with the base (Platonic) and its kis
    # (Catalan). This script isn't how any of those got into data/.
    categories = ['Miscellaneous', 'geodesic' if want_geodesic else 'Goldberg']
    # Chiral unless the solid is its own mirror image, which happens only along
    # the two symmetric edges of the (m,n) family. A dual has whatever symmetry
    # its primal has, so the same test settles the geodesic.
    if n != 0 and m != n:
        categories.append('chiral')

    # Built key by key to keep data/'s usual order, with the optional fields in
    # the middle where the other grid files have them.
    grid = {'gridId': grid_id, 'gridName': grid_name, 'categories': categories}
    recipes = GEODESIC_RECIPES[base] if want_geodesic else RECIPES
    if (m, n) in recipes:
        grid['recipe'] = recipes[(m, n)]
    # So the file says where it came from, and can be reproduced exactly.
    flags = ''.join(f'{option} ' for option in
                    (['--geodesic'] if want_geodesic else [])
                    + ([f'--base={base}'] if base != 'icosahedron' else []))
    grid['_comment'] = f'Generated by util/genGoldberg.py {flags}{m} {n}.'
    grid['vertices'] = [[round(float(c), 6) for c in v] for v in vertices]
    grid['faces'] = faces
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
