#!/usr/bin/env python3
"""Generate a zonohedron from a star of generating vectors, as a grid JSON file.

Usage: util/genZonohedron.py STAR [--drop=N] [gridId] [gridName]
       util/genZonohedron.py --list
Output is written to stdout; progress and the self-check go to stderr.
For the JSON format, see docs/json-format.md.

A zonohedron is a convex polyhedron all of whose faces are parallelograms. It is
built from a STAR of n vectors, and every edge of the result is a translate of one
of them -- so the edges run in exactly n directions, each direction's edges forming
a band round the solid called a zone. Two zones cross at one pair of opposite
faces, which gives the count:

    faces = n(n-1),  edges = 2 * faces,  vertices = 2 - faces + edges

If the generators are all the same length, as in every named zonohedron, every face
is a rhombus. Generators of differing lengths give general parallelograms, still a
zonohedron but not a rhombic one. See
https://www.georgehart.com/virtual-polyhedra/zonohedra-info.html, whose naming the
star presets follow: each is "the diagonals of" some solid, meaning that solid's
vertices taken one per antipodal pair.

WHY THIS EXISTS rather than converting a model from polyHédronisme. Its `jtI` is
the rhombic enneacontahedron's combinatorial type, canonicalised -- and
canonicalisation pulls the edges onto a midsphere, which for this solid is a
different shape from the zonohedral one. Measured with grid_quality.py, that model
has 90 edge directions rather than 10, and faces 8e-2 from being parallelograms:
kites, not rhombi. It plays perfectly well, but a player told that a zonohedron's
edges run in parallel families cannot see one, and that is most of the point of
having these solids at all. Here the faces are parallelograms BY CONSTRUCTION, so
the skew is floating-point noise.

How it works, per pair of generators, with no hull and nothing iterative:

    The zonohedron is every sum of t_k * v_k with each t_k in [-1/2, 1/2]. For an
    outward direction d, the face it supports is where each t_k is pushed to
    whichever end favours d. Take d = v_i x v_j: it is perpendicular to both, so
    t_i and t_j stay free while every other t_k is pinned -- and a face with two
    free parameters spanning v_i and v_j is exactly a parallelogram. So

        centre  = 1/2 * sum over k not in {i,j} of sign(d . v_k) * v_k
        corners = centre +- v_i/2 +- v_j/2

    and the opposite face is the same with d negated. n(n-1) faces, each written
    down in closed form.

DEGENERATE STARS are refused, not fudged. If a third generator lies in the plane of
two others then d . v_k is 0 for it, the two parallelograms either side become
coplanar, and they merge into one larger centrally-symmetric polygon -- Hart's
36-zone example has six 24-gons among its rhombi. The counts above stop holding and
the faces are no longer all parallelograms, so check() rejects it and says which
generators were at fault.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grid_checks  # noqa: E402
import grid_topology  # noqa: E402
import json_format  # noqa: E402
from grid_checks import cross, dot, norm, wound_outward  # noqa: E402

# Coordinates are compared after rounding to this many decimals, to weld the
# corners that neighbouring faces share. The same slack genGoldberg.py uses, and
# well inside the gap between distinct vertices of any star we would generate.
WELD_DECIMALS = 6

# Below this, two generators count as parallel (their cross product vanishing) and
# there is no face between them at all. Parallel generators are a mistake rather
# than a degeneracy: they would be one zone written twice.
PARALLEL_EPSILON = 1e-9

# Below this, a generator counts as lying in the plane of two others, which is the
# degenerate case the docstring describes. Generous next to PARALLEL_EPSILON: a
# near-miss here still merges faces to within rounding, and reporting that as a
# degenerate star is more useful than emitting a solid with two nearly-coplanar
# faces the app would draw as one.
COPLANAR_EPSILON = 1e-7

# The golden ratio, which the icosahedral stars are written in.
PHI = (1 + 5 ** 0.5) / 2


def normalized(vectors):
    """Unit vectors, so that all the faces come out rhombic."""
    return [[component / norm(v) for component in v] for v in vectors]


def golden_spiral_star(n, first=0.7):
    """n generators up a hemisphere, spaced by the golden angle in azimuth.

    The one star here that is NOT the diagonals of some symmetric solid, and that
    is the whole point of it. Every other star has a symmetry group, which fixes
    the pairwise angles into a few classes and so makes the faces a few repeated
    rhombi -- the rhombic triacontahedron's six axes are all 63.43 degrees apart,
    so all thirty faces are the same golden rhombus. That reads as crystalline,
    because it is.

    Here, instead: equal-area steps in z, so the directions don't bunch toward the
    pole, and an azimuth step of 2*pi/phi^2 -- an irrational fraction of a turn,
    so no two generators are ever related by a rotation. (The same reasoning as
    the tumble's irrational rate ratio in SceneManager.js: an irrational step
    never comes back into phase, so the pattern never closes.) The result has no
    rotational symmetry at all, only the central inversion that every zonohedron
    has, and the pairwise angles come out spread rather than clustered.

    A HEMISPHERE, not a sphere: a vector and its negative are one zone, so the
    generators want spreading over directions-without-sign. z runs over (0, 1).

    Measured at n=9 against the alternatives, since the choice is not obvious.
    Repelling the directions apart gives a better sharpest corner (42.3 vs 37.2
    degrees) but clumps the angles -- five faces at 51 degrees, seven near 88, and
    only 7 visually distinct rhombi against this star's 11 spread smoothly from 37
    to 88. Evenness tends toward symmetry, which is the thing being avoided.

    TWO NUMBERS decide a star here, and they pull against each other: the SHARPEST
    face corner, which is the smallest angle between any two generators (a slim
    rhombus has little room for its clue digit), and how many distinct rhombus
    SHAPES result, which is the whole point. `first`, the offset of the first z
    step, trades one for the other. Swept over 0.1 to 0.9:

        n   faces   best `first`   sharpest   shapes
        6      30       0.8          48.7     11 of 15
        7      42       0.8          45.0     13 of 21
        8      56       0.8          42.1     13 of 28
        9      72       0.7          37.2     11 of 36
        10     90       0.8          34.6      9 of 45

    Both numbers improve as n FALLS, which was not what I expected: fewer lines
    through one origin can spread further apart, so the corners are blunter, and
    the angles that remain are more thoroughly separated, so more of the pairs give
    visually distinct rhombi. n=7 gets 13 shapes out of 21 possible -- 62% of them
    distinct, against n=10's 20%. The pull the other way is simply that a bigger
    grid is a bigger puzzle.

    At n=9, first=0.8 would give 38.5 degrees but only 8 shapes, so 0.7 is chosen
    there for the variety; everywhere else 0.8 wins on both counts. For scale,
    data/jtI.json (the rhombic enneacontahedron, 90 faces) ships at 41.8 degrees,
    and n=6 is worth noting for having the same 30 faces as the rhombic
    triacontahedron (data/daD.json) while using 11 different rhombi where that uses
    one -- the same solid size, the opposite character.

    @param n - how many generators, giving n(n-1) faces
    @param first - offset of the first z step; see the table above
    """
    from math import cos, sin, sqrt
    turn = 2 * 3.141592653589793 / PHI ** 2
    star = []
    for k in range(n):
        z = (k + first) / n
        r = sqrt(max(0.0, 1 - z * z))
        star.append([r * cos(k * turn), r * sin(k * turn), z])
    return normalized(star)


# The stars, named for the solid whose diagonals they are: its vertices, one taken
# from each antipodal pair, since a vector and its negative are one zone. Every
# preset is a set of equal-length vectors, hence rhombic faces throughout.
#
# The comment on each says what it generates, and note how few are new: three of
# the five are already in data/ by other routes, which is a useful check on this
# script rather than a duplication (see --list and the report from check()).
STARS = {
    # 3 zones -> the cube. Also the smallest zonohedron there is; with fewer than
    # three generators there is no solid.
    'octahedron': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    # 4 zones -> the rhombic dodecahedron (data/daC.json).
    'cube': normalized([[1.0, 1.0, 1.0], [1.0, -1.0, -1.0],
                        [-1.0, 1.0, -1.0], [-1.0, -1.0, 1.0]]),
    # 6 zones -> the rhombic triacontahedron (data/daD.json). The icosahedron's 12
    # vertices in 6 pairs, which are its five-fold axes. Drop one of them
    # (--drop=1) and the remaining five give the rhombic icosahedron: the dropped
    # axis is the pole and the other five stand round it like umbrella ribs, which
    # is how Hart describes that star.
    'icosahedron': normalized([[0.0, 1.0, PHI], [0.0, -1.0, PHI],
                               [1.0, PHI, 0.0], [-1.0, PHI, 0.0],
                               [PHI, 0.0, 1.0], [PHI, 0.0, -1.0]]),
    # 10 zones -> the rhombic enneacontahedron. The dodecahedron's 20 vertices in
    # 10 pairs: eight cube corners give four, and the three rectangles give six.
    'dodecahedron': normalized([[1.0, 1.0, 1.0], [1.0, 1.0, -1.0],
                                [1.0, -1.0, 1.0], [1.0, -1.0, -1.0],
                                [0.0, 1 / PHI, PHI], [0.0, -1 / PHI, PHI],
                                [1 / PHI, PHI, 0.0], [-1 / PHI, PHI, 0.0],
                                [PHI, 0.0, 1 / PHI], [PHI, 0.0, -1 / PHI]]),
    # Not solids' diagonals, and the only stars here with no symmetry at all; see
    # golden_spiral_star for what they are, why, and where each offset comes from.
    'spiral7': golden_spiral_star(7, 0.8),      # 42 rhombi
    'spiral8': golden_spiral_star(8, 0.8),      # 56 rhombi
    'spiral9': golden_spiral_star(9, 0.7),      # 72 rhombi
    'spiral10': golden_spiral_star(10, 0.8),    # 90 rhombi
}

# Conway notation for the ones that have it, for the optional "recipe" field (see
# docs/json-format.md), which links a grid to polyHédronisme. Keyed by (star,
# dropped). The rhombic icosahedron has no such name -- it is not an operator
# applied to a Platonic solid, but a zone removed from one that is.
#
# Note a recipe here shows the right SOLID and not necessarily this shape:
# polyHédronisme canonicalises, which is the very difference the docstring is
# about. Fine for its purpose, which is to let a player go and look.
RECIPES = {
    ('octahedron', 0): 'C',      # cube
    ('cube', 0): 'daC',          # rhombic dodecahedron
    ('icosahedron', 0): 'daD',   # rhombic triacontahedron
    ('dodecahedron', 0): 'jtI',  # rhombic enneacontahedron
}

# What each star is called when it comes out, for the default gridName. Anything
# not here falls back to a description built from the star and the zone count.
NAMES = {
    ('octahedron', 0): 'Cube',
    ('cube', 0): 'Rhombic dodecahedron',
    ('icosahedron', 0): 'Rhombic triacontahedron',
    ('icosahedron', 1): 'Rhombic icosahedron',
    ('dodecahedron', 0): 'Rhombic enneacontahedron',
    ('spiral7', 0): 'Seven-zone rhombic spiral',
    ('spiral8', 0): 'Eight-zone rhombic spiral',
    ('spiral9', 0): 'Nine-zone rhombic spiral',
    ('spiral10', 0): 'Ten-zone rhombic spiral',
}


def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def face_of(generators, i, j, sense):
    """One face of the zonohedron: the parallelogram where zones i and j cross.

    @param sense: +1 or -1, for the two opposite faces of the pair
    @returns (corners, outward normal), or (None, the offending generator) if a
        third generator lies in this face's plane
    """
    normal = cross(generators[i], generators[j])
    outward = [sense * component for component in normal]

    # Push every other generator to whichever end of its range favours `outward`.
    centre = [0.0, 0.0, 0.0]
    for k in range(len(generators)):
        if k in (i, j):
            continue
        side = dot(outward, generators[k])
        if abs(side) <= COPLANAR_EPSILON:
            return (None, k)
        step = 0.5 if side > 0 else -0.5
        centre = [centre[axis] + step * generators[k][axis] for axis in range(3)]

    # The four corners, walked round rather than in some arbitrary order.
    (u, v) = (generators[i], generators[j])
    corners = [[centre[axis] + a * u[axis] / 2 + b * v[axis] / 2
                for axis in range(3)]
               for (a, b) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return (corners, outward)


def zonohedron(generators):
    """The zonohedron of a star, as (vertices, faces).

    Scaled to a circumradius of 1, matching the rest of data/: the app's camera
    distances and its edge and vertex radii are all chosen for a solid that size.
    Uniform scaling leaves the edges parallel and equal, so nothing that makes this
    a zonohedron is disturbed by it.
    """
    count = len(generators)
    for i in range(count):
        for j in range(i + 1, count):
            if norm(cross(generators[i], generators[j])) <= PARALLEL_EPSILON:
                log(f'Error: generators {i} and {j} are parallel; each zone should '
                    'appear once.')
                sys.exit(1)

    # Weld as we go: a corner is reached once from every face around it.
    indices = {}
    vertices = []
    faces = []
    for i in range(count):
        for j in range(i + 1, count):
            for sense in (1, -1):
                (corners, outward) = face_of(generators, i, j, sense)
                if corners is None:
                    log(f'Error: generator {outward} lies in the plane of '
                        f'generators {i} and {j}, so their faces merge instead of '
                        'staying parallelograms. This star is degenerate; see the '
                        'note in the docstring.')
                    sys.exit(1)
                # Origin-centred by construction, so "outward" is simply away from
                # the origin -- the same test genGoldberg's orient_outward makes.
                if not wound_outward(corners, [0.0, 0.0, 0.0]):
                    corners = list(reversed(corners))
                face = []
                for corner in corners:
                    key = tuple(round(component, WELD_DECIMALS)
                                for component in corner)
                    if key not in indices:
                        indices[key] = len(vertices)
                        vertices.append(corner)
                    face.append(indices[key])
                faces.append(face)

    longest = max(norm(vertex) for vertex in vertices)
    return ([[component / longest for component in vertex] for vertex in vertices],
            faces)


def check(generators, vertices, faces):
    """Verify the solid against what a zonohedron on this star must be.

    @returns a one-line description, or exits if anything is off
    """
    n = len(generators)
    face_count = n * (n - 1)
    edge_count = 2 * face_count
    sizes = grid_checks.face_census(faces)

    problems = (
        grid_checks.check_counts(vertices, faces,
                                 {'vertices': 2 - face_count + edge_count,
                                  'faces': face_count, 'edges': edge_count})
        + ([f'only quadrilaterals expected, got {sorted(sizes)}']
           if set(sizes) != {4} else [])
        # The two that say "zonohedron", and the reason this script exists. Checked
        # tightly, because a closed-form construction has no excuse for missing
        # them by more than rounding.
        + grid_checks.check_parallelogram_faces(vertices, faces, 1e-9)
        + grid_checks.check_direction_classes(vertices, faces, n, 1e-9)
        + grid_checks.check_flat_faces(vertices, faces, 1e-9)
        + grid_checks.check_closed_surface(faces)
        + grid_checks.check_outward_winding(vertices, faces))

    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)

    zones = grid_checks.direction_classes(vertices, faces, 1e-9)
    corners = [grid_checks.corners_of(vertices, face) for face in faces]
    worst_ratio = max(grid_checks.side_ratio(face) for face in corners)
    shape = 'all rhombi' if worst_ratio < 1 + 1e-9 else \
        f'parallelograms, sides up to x{worst_ratio:.3f}'
    return (f'{n} zones: {len(vertices)} vertices, '
            f'{len(grid_topology.edges_of(faces))} edges, {len(faces)} faces; '
            f'{len(zones)} edge directions of {len(zones[0])} edges each; '
            f'{shape}')


def usage():
    log(__doc__.split('\n\n')[0])
    log('')
    log(f'STAR is one of: {", ".join(STARS)}')
    log('--drop=N leaves off the last N generators, which removes that many zones.')
    log('--list shows what each star produces.')


def show_list():
    """What each star and each useful --drop gives, so the choices are visible."""
    log(f'{"star":<14} {"drop":>4} {"zones":>5} {"faces":>6}  produces')
    for star in STARS:
        for dropped in (0, 1):
            n = len(STARS[star]) - dropped
            if n < 3:
                continue        # fewer than three generators is not a solid
            name = NAMES.get((star, dropped), '')
            log(f'{star:<14} {dropped:>4} {n:>5} {n * (n - 1):>6}  {name}')


def main():
    options = [arg for arg in sys.argv[1:] if arg.startswith('--')]
    argv = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    dropped = 0
    for option in options:
        if option == '--list':
            show_list()
            return
        if option.startswith('--drop='):
            dropped = int(option.split('=', 1)[1])
        else:
            log(f'Error: unknown option {option}.')
            usage()
            sys.exit(1)

    if len(argv) < 1:
        usage()
        sys.exit(1)
    star = argv[0]
    if star not in STARS:
        log(f'Error: unknown star {star!r}; expected one of {", ".join(STARS)}.')
        sys.exit(1)

    generators = STARS[star][:len(STARS[star]) - dropped] if dropped else STARS[star]
    if len(generators) < 3:
        log(f'Error: {len(generators)} generator(s) after dropping {dropped}; '
            'three is the fewest that make a solid.')
        sys.exit(1)

    n = len(generators)
    default_name = NAMES.get((star, dropped),
                             f'Zonohedron on {n} of the {star}\'s diagonals')
    grid_id = argv[1] if len(argv) > 1 else f'z{star[:3]}{n}'
    grid_name = argv[2] if len(argv) > 2 else default_name

    (vertices, faces) = zonohedron(generators)
    log(check(generators, vertices, faces))

    # "Miscellaneous" is the family for a solid in none of the classical ones, the
    # picker having to file every solid under exactly one family. Some of these
    # stars produce a solid that IS in one -- the cube is Platonic, the rhombic
    # dodecahedron and triacontahedron Catalan -- but this script is not how those
    # got into data/, so the caller overrides the categories by hand if it ever is.
    categories = ['Miscellaneous', 'zonohedron']

    # Built key by key to keep data/'s usual order, with the optional fields in the
    # middle where the other grid files have them.
    grid = {'gridId': grid_id, 'gridName': grid_name, 'categories': categories}
    if (star, dropped) in RECIPES:
        grid['recipe'] = RECIPES[(star, dropped)]
    # So the file says where it came from, and can be reproduced exactly -- from argv,
    # so a new option cannot be forgotten here (see json_format.source_line).
    grid['source'] = json_format.source_line()
    grid['vertices'] = [[round(component, 6) for component in vertex]
                        for vertex in vertices]
    grid['faces'] = faces
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
