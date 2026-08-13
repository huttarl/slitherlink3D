#!/usr/bin/env python3
"""Generate an open carbon nanotube: a cylinder of hexagons, with no ends.

Usage:
    util/genNanotube.py 8 0                 # the zigzag (8,0), to stdout
    util/genNanotube.py 6 3 --cells=1       # a chiral tube
    util/genNanotube.py --all               # every recipe below, into data/
    util/genNanotube.py 5 5 --out=data/x.json

UNLIKE every other generator here, this writes a solid that is NOT CLOSED. It is a
tube with two open rims, so the grid says `"closed": false` (see docs/json-format.md)
and grid_checks.check_closed_surface is deliberately not called; check_cylinder below
replaces it. Euler's formula gives 0 rather than 2, and the rims are left jagged --
the points of the outermost hexagons stick out, because nothing is cut off to tidy
them.

HOW IT IS BUILT: by rolling a honeycomb sheet, which is how a nanotube is actually
described. Hexagon centres sit on a triangular lattice, a1 = sqrt(3)(1,0) and
a2 = sqrt(3)(1/2, sqrt(3)/2) for a bond length of 1, and each hexagon's own corners
are at 30, 90, ... 330 degrees at radius 1 -- which is exactly what makes
neighbouring hexagons share corners rather than merely abut.

Rolling means identifying sheet points that differ by the CHIRAL VECTOR
C = n*a1 + m*a2, so |C| becomes the circumference and the tube's axis runs
perpendicular to C. That single vector is the whole classification:

    (n,0)  zigzag    -- some bonds parallel to the axis
    (n,n)  armchair  -- some bonds perpendicular to it
    else   chiral    -- neither, so the rows of hexagons spiral

and the reason a chiral tube LOOKS different is just that C points somewhere else,
so the hexagons meet the axis at another angle. Nothing in the code special-cases
the three; they are one construction asked three questions.

Length comes in whole TRANSLATION VECTORS T, the shortest lattice vector along the
axis, so the ends repeat the same way round the tube. Chiral tubes have long T --
(6,3) is 42 hexagons in a single cell -- so --cells is often 1 for those and can
afford to be more for a zigzag.

This replaces an earlier construction that took a capped fullerene tube from
genFullerene and threw its caps away. That could only ever make the armchair (5,5),
since a fullerene cap needs six pentagons arranged 5-fold, and it wasted two belts
of hexagons with the caps. Rolling the lattice reaches every (n,m), needs no
fullerene, and is truer: it puts every atom on one cylinder, so the bonds come out
within a per cent of each other where the stripped version's varied by six.

WHAT AN OPEN TUBE COSTS THE PUZZLE, and what it does not:
  - Rim edges are ORDINARY edges the loop may use. genSliPuzzles paints one set of
    faces red and takes the loop as what divides red from blue, counting the nothing
    beyond a rim as blue -- so a rim edge is on the loop exactly when its one face is
    red. The stored solutions run along plenty of them.
  - slisolver's colouring deduction (apply_color_rules) reads an edge's two faces and
    skips any edge that has only one. It stays correct, but loses its strongest
    inference at the rims, so puzzles here may want more clues or take longer.

Needs nothing but the standard library.
"""
import math
import sys
from collections import Counter
from pathlib import Path

# Our local modules. All standard-library, like this script.
import grid_checks
import grid_topology
import json_format

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

USAGE = __doc__[__doc__.index('Usage:'):__doc__.index('UNLIKE')].rstrip()

# The tubes we keep, one of each kind, chosen for shape as much as for chirality: a
# grid wants 30-odd faces and to be plainly longer than wide without being a wire.
#
# The armchair is the (5,5) that the old cap-stripping construction produced, at the
# same 40 hexagons and 100 atoms -- which is how we know the two agree.
RECIPES = {
    'nt55': {'n': 5, 'm': 5, 'cells': 4, 'kind': 'armchair'},
    'nt80': {'n': 8, 'm': 0, 'cells': 2, 'kind': 'zigzag'},
    'nt63': {'n': 6, 'm': 3, 'cells': 1, 'kind': 'chiral'},
}

# Decimals for welding wrapped points that have come round to the same place. Well
# inside a bond length, and well outside the rounding of the arithmetic.
WELD_DECIMALS = 5

# A hexagon's corners, as angles about its centre. 30 degrees off the lattice's own
# directions, which is what puts a corner where three hexagons meet.
CORNER_ANGLES = [math.radians(30 + 60 * corner) for corner in range(6)]


def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def kind_of(n, m):
    """Which of the three families an (n,m) tube belongs to."""
    if m == 0:
        return 'zigzag'
    if n == m:
        return 'armchair'
    return 'chiral'


def rolled_tube(n, m, cells):
    """An (n,m) tube of `cells` unit cells, as (vertices, faces).

    Vertices are welded by position, so a hexagon that wraps round onto itself shares
    its corners properly rather than gaining a second copy.
    """
    root3 = math.sqrt(3)
    (a1, a2) = ((root3, 0.0), (root3 / 2, 1.5))

    chiral = (n * a1[0] + m * a2[0], n * a1[1] + m * a2[1])
    circumference = math.hypot(*chiral)
    around = (chiral[0] / circumference, chiral[1] / circumference)
    # The axis, across the chiral vector in the sheet. Its sign decides which way the
    # tube is built, not what it is.
    axis = (-around[1], around[0])
    radius = circumference / (2 * math.pi)

    # The translation vector: the shortest lattice vector along the axis, which is
    # what makes a whole number of cells end the same way all round.
    divisor = math.gcd(2 * m + n, 2 * n + m)
    (t1, t2) = ((2 * m + n) // divisor, -(2 * n + m) // divisor)
    translation = (t1 * a1[0] + t2 * a2[0], t1 * a1[1] + t2 * a2[1])
    length = math.hypot(*translation) * cells

    def roll(point):
        """A sheet point wrapped onto the cylinder, with the axis along y.

        y is up on screen (see CAMERA_HEIGHT in js/constants.js), so a tube built
        this way stands up rather than pointing at the viewer.
        """
        along = point[0] * around[0] + point[1] * around[1]
        up = point[0] * axis[0] + point[1] * axis[1]
        angle = along / radius
        return (radius * math.cos(angle), up, radius * math.sin(angle))

    # Enumerate lattice points generously and keep the hexagons whose CENTRES fall in
    # one tube length; welding sorts out those that wrap onto each other, and corners
    # straying past the ends are the jagged rim.
    reach = int(2 * (n + m + length / root3)) + 4
    points = {}
    faces = {}
    for i in range(-reach, reach + 1):
        for j in range(-reach, reach + 1):
            centre = (i * a1[0] + j * a2[0], i * a1[1] + j * a2[1])
            up = centre[0] * axis[0] + centre[1] * axis[1]
            if not (-1e-9 <= up < length - 1e-9):
                continue
            face = []
            for angle in CORNER_ANGLES:
                corner = (centre[0] + math.cos(angle), centre[1] + math.sin(angle))
                welded = tuple(round(c, WELD_DECIMALS) for c in roll(corner))
                face.append(points.setdefault(welded, len(points)))
            # Keyed by its corner set, so a hexagon reached twice round the tube is
            # stored once.
            faces[frozenset(face)] = face

    vertices = [list(point) for point in points]
    return (vertices, [outward(vertices, face) for face in faces.values()])


def outward(vertices, face):
    """The face wound counterclockwise seen from outside the tube.

    Every face is on the barrel, so "outside" is straight out from the axis: compare
    the face's normal with the direction from the axis to its middle. Which way the
    sheet's corners came out wound depends on the sign chosen for the axis above, so
    this is settled by measuring rather than by reasoning about that choice.
    """
    corners = [vertices[v] for v in face]
    normal = grid_checks.face_normal(corners)
    middle = grid_checks.centroid(corners)
    # Radially outward at the middle: the axis is y, so ignore that component.
    radial = [middle[0], 0.0, middle[2]]
    return face if grid_checks.dot(normal, radial) > 0 else face[::-1]


def boundary_cycles(faces):
    """The rims: cycles of edges that have only one face.

    @returns a list of cycles, each a list of vertex ids in order round the rim
    """
    per_edge = Counter()
    for face in faces:
        for (a, b) in grid_topology.face_edges(list(face)):
            per_edge[grid_topology.edge_key(a, b)] += 1
    rim_edges = [edge for (edge, count) in per_edge.items() if count == 1]

    neighbors = {}
    for (a, b) in rim_edges:
        neighbors.setdefault(a, []).append(b)
        neighbors.setdefault(b, []).append(a)
    walked = set()
    cycles = []
    for start in neighbors:
        if start in walked:
            continue
        cycle = [start]
        walked.add(start)
        while True:
            onward = [v for v in neighbors[cycle[-1]] if v not in walked]
            if not onward:
                break
            cycle.append(onward[0])
            walked.add(onward[0])
        cycles.append(cycle)
    return cycles


def check_cylinder(vertices, faces, n, m, cells):
    """The checks a tube must pass, in place of the closed-surface ones.

    A closed solid is checked by Euler = 2 and every edge having two faces. Neither
    holds here, so what is checked instead is that this is a cylinder and not some
    other torn thing: nothing but hexagons, Euler 0, exactly two rims of equal
    length, and every atom with two or three bonds -- two on a rim, three inside. An
    atom with ONE bond would matter: a loop needs two edges at every vertex it
    visits, so that bond could never be filled.

    The face count is checked against the theory too: a unit cell holds
    2(n^2+nm+m^2)/gcd(2m+n, 2n+m) hexagons, so a wrong lattice or a bad weld shows up
    as a count that doesn't match rather than as a plausible-looking tube.

    @returns a list of problems, empty if all is well
    """
    problems = []
    census = Counter(len(face) for face in faces)
    if set(census) != {6}:
        problems.append(f'only hexagons expected, got {dict(sorted(census.items()))}')

    divisor = math.gcd(2 * m + n, 2 * n + m)
    expected = cells * 2 * (n * n + n * m + m * m) // divisor
    if len(faces) != expected:
        problems.append(f'{expected} hexagons expected for ({n},{m}) x{cells}, '
                        f'got {len(faces)}')

    edges = grid_topology.edges_of([list(face) for face in faces])
    euler = len(vertices) - len(edges) + len(faces)
    if euler != 0:
        problems.append(f'Euler characteristic {euler}, but a cylinder wants 0 '
                        f'({len(vertices)} - {len(edges)} + {len(faces)})')

    rims = boundary_cycles(faces)
    if len(rims) != 2:
        problems.append(f'{len(rims)} rim(s), expected 2 '
                        f'(lengths {[len(rim) for rim in rims]})')
    elif len(rims[0]) != len(rims[1]):
        problems.append(f'rims of different lengths: {[len(r) for r in rims]}')

    # edge_degrees, not vertex_degrees: the two differ here, and it is the BONDS that
    # matter. A rim atom belongs to one hexagon and so counts 1 face, while having the
    # 2 edges a loop could pass along.
    degrees = grid_topology.edge_degrees([list(face) for face in faces])
    stray = sorted({degree for degree in degrees.values()} - {2, 3})
    if stray:
        problems.append(f'atoms with {stray} bonds; a tube wants 2 (on a rim) or 3')
    if len(degrees) != len(vertices):
        problems.append(f'{len(vertices) - len(degrees)} atom(s) in no face at all')

    problems += grid_checks.check_outward_winding(vertices, faces)
    return problems


def nanotube(n, m, cells):
    """An (n,m) tube as (vertices, faces), scaled to a circumradius of 1.

    The scale matches the rest of data/: the app's camera distance and its edge and
    vertex radii all suit a solid about that size.
    """
    (vertices, faces) = rolled_tube(n, m, cells)
    middle = grid_checks.centroid(vertices)
    centred = [[v[axis] - middle[axis] for axis in range(3)] for v in vertices]
    furthest = max(grid_checks.norm(v) for v in centred)
    return ([[c / furthest for c in v] for v in centred], faces)


def describe(vertices, faces, n, m):
    """One line about the tube, for the log."""
    edges = grid_topology.edges_of([list(face) for face in faces])
    lengths = [grid_checks.distance(vertices[a], vertices[b]) for (a, b) in edges]
    on_a_rim = sum(len(rim) for rim in boundary_cycles(faces))
    heights = [v[1] for v in vertices]
    width = 2 * max(math.hypot(v[0], v[2]) for v in vertices)
    bow = max(grid_checks.face_bow(grid_checks.corners_of(vertices, list(face)))
              for face in faces)
    return (f'({n},{m}) {kind_of(n, m)}: {len(faces)} hexagons, {len(vertices)} '
            f'atoms, {len(edges)} bonds ({on_a_rim} on a rim, and playable like any '
            f'other); bonds {min(lengths):.4f} to {max(lengths):.4f} '
            f'(ratio {max(lengths) / min(lengths):.3f}); '
            f'length/width {(max(heights) - min(heights)) / width:.3f}; '
            f'faces bowed {bow:.1e}')


def build(grid_id, n, m, cells):
    """One grid, as the dict that goes into the JSON file."""
    (vertices, faces) = nanotube(n, m, cells)
    rounded = [[round(c, 6) for c in v] for v in vertices]
    problems = check_cylinder(rounded, faces, n, m, cells)
    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)
    log(describe(rounded, faces, n, m))

    kind = kind_of(n, m)
    return {
        'gridId': grid_id,
        'gridName': f'Nanotube ({n},{m}) {kind}',
        # No 'fullerene': that is a closed cage, and this is open at both ends. The
        # kind is an attribute of its own, since it is the interesting thing about
        # having three of them.
        'categories': ['Miscellaneous', 'nanotube'],
        # See docs/json-format.md: the one thing in data/ that isn't a closed surface.
        'closed': False,
        # n, m and cells spelled out even when defaulted, since all three decide the
        # geometry and argv would be silent about a default. See
        # json_format.source_line.
        'source': json_format.source_line([str(n), str(m), f'--cells={cells}']),
        'vertices': rounded,
        'faces': faces,
    }


def main():
    options = [arg for arg in sys.argv[1:] if arg.startswith('--')]
    argv = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    cells = None
    out = None
    write_all = False
    for option in options:
        if option == '--all':
            write_all = True
        elif option.startswith('--cells='):
            cells = int(option.split('=', 1)[1])
        elif option.startswith('--out='):
            out = Path(option.split('=', 1)[1])
        else:
            log(f'Error: unknown option {option}.\n{USAGE}')
            sys.exit(1)

    if write_all:
        for (grid_id, recipe) in RECIPES.items():
            grid = build(grid_id, recipe['n'], recipe['m'],
                         cells or recipe['cells'])
            path = DATA_DIR / f'{grid_id}.json'
            with open(path, 'w') as handle:
                json_format.write_json(grid, handle)
            log(f'Wrote {path}')
        return

    if len(argv) != 2:
        log(f'{USAGE}\n\nNamed recipes: '
            + ', '.join(f'{k} = ({r["n"]},{r["m"]}) {r["kind"]}'
                        for (k, r) in RECIPES.items()))
        sys.exit(1)
    (n, m) = (int(argv[0]), int(argv[1]))
    if n < 1 or m < 0 or m > n:
        # m > n is the mirror image of m < n, the same tube wound the other way, so
        # the convention is to name it with n first.
        log(f'Error: ({n},{m}) is not a tube; wants n >= 1 and 0 <= m <= n.')
        sys.exit(1)

    grid = build(f'nt{n}{m}', n, m, cells or 1)
    if out:
        with open(out, 'w') as handle:
            json_format.write_json(grid, handle)
        log(f'Wrote {out}')
    else:
        json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
