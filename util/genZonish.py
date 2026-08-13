#!/usr/bin/env python3
"""Generate a zonish polyhedron: a seed solid expanded by zones.

Usage: util/genZonish.py SEED SOURCE [--pick=SPEC] [gridId] [gridName]
       util/genZonish.py --preset=NAME [gridId] [gridName]
       util/genZonish.py --list
Output is written to stdout; progress and the self-check go to stderr.
For the JSON format, see docs/json-format.md.

Where a ZONOHEDRON is built from a star of vectors alone (util/genZonohedron.py), a
ZONISH polyhedron starts from any convex seed and adds zones to it. See
https://www.georgehart.com/virtual-polyhedra/zonish_polyhedra.html. The seed need
not be centrally symmetric, so the result usually isn't either -- which is why these
are "zonish" rather than zonohedra, and why the seed's own odd-sided faces survive.

It is the Minkowski sum of the seed with one segment per zone: every point of the
seed, plus half of each zone vector either way. Three kinds of face come out, and
Hart's six-zone figure shows all three:

  * the SEED's own faces, translated outward -- 12 pentagons and 20 triangles of the
    icosidodecahedron;
  * one parallelogram per zone per SILHOUETTE edge, an edge whose two faces lie on
    opposite sides of that zone's direction. The silhouette is a closed cycle, ten
    edges long for a five-fold axis on this seed, giving 6 x 10 = 60 squares;
  * one pair of parallelograms per PAIR of zones, as in a plain zonohedron:
    C(6,2) x 2 = 30 golden rhombi.

122 faces in all, which is what Hart reports, and that arithmetic is what check()
verifies rather than merely restating. Every face that is not the seed's is spanned
by two directions and so is centrally symmetric, which check() also insists on.

ZONE DIRECTIONS COME FROM THE SEED, which is not a convenience but a requirement.
Hart notes that seed and star must share a symmetry group for a symmetric result,
and sharing a group means sharing an ORIENTATION: the first version of this script
took its axes from genZonohedron's canonical stars, and because data/aD.json is
turned differently from the (0, +-1, phi) icosahedron those axes lay across the
seed's symmetry instead of along it. The solid that came out was a legitimate
Minkowski sum and nothing like Hart's figure -- 46 vertices where the one-zone
result wants 40, and a silhouette of 8 edges rather than 10. Taking the normals of
the seed's own pentagons cannot go wrong that way.

So SOURCE says where to take them from:

    faces        every face normal of the seed
    faces:N      the normals of its N-sided faces -- faces:5 on the
                 icosidodecahedron is exactly the six five-fold axes
    vertices     the directions of its vertices

Each is reduced to one vector per antipodal pair, since a direction and its reverse
are one zone, and sorted so that --pick indices mean the same thing every run.

OBLATE AND PROLATE differ in WHICH axes are taken, not in any length -- both of
Hart's three-zone figures use three five-fold axes at the seed's own edge length.
The distinction is combinatorial rather than angular: as unsigned axes every pair of
five-fold axes is inclined at the same 63.4 degrees, so the angles cannot tell them
apart. What separates them is whether the three can be signed to point into a common
direction, which happens exactly when they surround a common triangle of the seed.

Those three CLUSTER about that common direction, so summing segments along them
stretches the solid along it: one long axis, which is PROLATE. The other triple points
every which way and spreads the solid instead, into two long axes and one short, which
is OBLATE. See surrounds_triangle, and --pick=oblate3 / --pick=prolate3, which search
for such a triple rather than trusting a hard-coded index.

WHY A HULL HERE, when genZonohedron.py writes its faces down in closed form: there
the faces come in one kind, indexed by pairs of generators, while here they come in
three and the silhouette kind needs the seed's edge-to-face adjacency plus a side
test per zone. Taking the convex hull of the sum's candidate corners and merging its
coplanar facets gets all three at once with no case analysis. The face census being
checked against the formula is what earns the shortcut.
"""
import json
import sys
from itertools import combinations, product
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grid_checks  # noqa: E402
import grid_topology  # noqa: E402
import json_format  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# Coordinates are compared after rounding to this many decimals, to weld candidate
# corners that arrive at one point by different routes, and to group directions that
# are the same axis. The same slack the other generators use.
WELD_DECIMALS = 6

# How close two hull facets' planes must be to count as one face. Coplanar facets
# come back from QHull agreeing to near machine precision, and the nearest genuinely
# different plane on these solids is degrees away, so there is margin either side.
COPLANAR_DECIMALS = 6

# A point counts as a corner only if it is a corner of some facet AND not merely
# sitting on a face. QHull reports points that lie in a facet's plane among that
# facet's vertices when they are within its own tolerance, and including one would
# put a spurious corner in the middle of a face's boundary -- which is how the first
# version turned a pentagon into a decagon. A point is kept only if the faces
# meeting there do not all share one plane.
ON_FACE_EPSILON = 1e-7

# Hart's figures, so the ones his page shows can be reproduced by name, as
# (seed, source, pick, gridId, gridName, categories). Categories of None take the
# default below; only one of these needs otherwise.
PRESETS = {
    # A Johnson solid, J43, and not a coincidence: adding one five-fold zone to the
    # icosidodecahedron inserts a band of ten squares, which is precisely a
    # decagonal prism, and the icosidodecahedron IS the pentagonal gyrobirotunda.
    # So the result is that birotunda elongated. Its family is therefore Johnson
    # rather than Miscellaneous, and zonish is the cross-cutting attribute.
    'one-zone': ('aD', 'faces:5', '0', 'J43',
                 'Elongated pentagonal gyrobirotunda (J43)',
                 ['Johnson solid', 'zonish']),
    'two-zone': ('aD', 'faces:5', '0,1', 'zonaD2',
                 'Two-zone icosidodecahedron', None),
    'oblate': ('aD', 'faces:5', 'oblate3', 'zonaD3o',
               'Oblate three-zone icosidodecahedron', None),
    'prolate': ('aD', 'faces:5', 'prolate3', 'zonaD3p',
                'Prolate three-zone icosidodecahedron', None),
    'six-zone': ('aD', 'faces:5', 'all', 'zonaD6',
                 'Six-zone icosidodecahedron', None),
    # Hart's "pleasing pentacontahedron": 50 faces, from the cuboctahedron and the
    # four three-fold axes, which are the normals of its eight triangles. 14 seed
    # faces + 4 x 6 swept + C(4,2) x 2 = 50, and the 6 seed squares plus the 24 swept
    # ones are the 30 squares he counts, the 12 crossings being root-two rhombi.
    'pentacontahedron': ('aC', 'faces:3', 'all', 'zonaC4',
                         'Four-zone cuboctahedron', None),
}

# Zonish, not zonohedral: a zonohedron's every face is centrally symmetric, while
# here the seed's own faces are not, so the solid as a whole usually isn't either
# and the 'zonohedron' category would be a false claim. "Miscellaneous" is the
# family for a solid in none of the classical ones, the picker having to file every
# solid under exactly one family.
DEFAULT_CATEGORIES = ['Miscellaneous', 'zonish']


def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def load_seed(stem):
    """A seed's vertices and faces, from data/.

    Scaled so its edges are 1 long, because the zone vectors are unit vectors:
    Hart chooses the zonal edge length equal to the seed's, which is what makes the
    new faces squares rather than rectangles.
    """
    path = stem if Path(stem).suffix == '.json' else DATA_DIR / f'{stem}.json'
    grid = json.loads(Path(path).read_text())
    lengths = [grid_checks.distance(grid['vertices'][a], grid['vertices'][b])
               for (a, b) in grid_topology.edges_of(grid['faces'])]
    median = sorted(lengths)[len(lengths) // 2]
    return (np.array(grid['vertices'], dtype=float) / median, grid['faces'],
            grid.get('gridName', stem))


def zone_directions(seed_vertices, seed_faces, source):
    """Unit zone directions taken from the seed, one per antipodal pair.

    Sorted, so that a --pick index means the same thing on every run.
    """
    if source == 'vertices':
        raw = [np.array(vertex) for vertex in seed_vertices]
    elif source == 'faces' or source.startswith('faces:'):
        sides = int(source.split(':', 1)[1]) if ':' in source else None
        raw = [np.array(grid_checks.face_normal([seed_vertices[i] for i in face]))
               for face in seed_faces if sides is None or len(face) == sides]
    else:
        log(f'Error: unknown source {source!r}; expected faces, faces:N or '
            'vertices.')
        sys.exit(1)

    unique = {}
    for vector in raw:
        length = np.linalg.norm(vector)
        if length == 0:
            continue
        unit = vector / length
        # One of the two senses, chosen the same way each time, so a direction and
        # its reverse collapse to one zone.
        for component in unit:
            if abs(component) > 1e-9:
                if component < 0:
                    unit = -unit
                break
        unique.setdefault(tuple(np.round(unit, WELD_DECIMALS)), unit)
    return [unique[key] for key in sorted(unique)]


def surrounds_triangle(zones):
    """Whether these axes can be signed to point into a common direction.

    Which is what "surrounding a common triangle of the seed" means, and the
    difference between Hart's oblate and prolate three-zone figures: true for the
    PROLATE triple, since axes that cluster about one direction stretch the solid
    along it. As unsigned axes, any two five-fold axes are inclined at the same angle,
    so the angles say nothing; this does. Brute force over the sign patterns, of which there are few
    and only 2^(n-1) that differ (negating every vector changes nothing).
    """
    for signs in product((1, -1), repeat=len(zones) - 1):
        signed = [zones[0]] + [sign * zone
                               for (sign, zone) in zip(signs, zones[1:])]
        if all(np.dot(u, v) > 0 for (u, v) in combinations(signed, 2)):
            return True
    return False


def pick_zones(directions, spec):
    """The subset of `directions` a --pick spec asks for.

    'all', a comma-separated list of indices, or oblate3 / prolate3, which search
    for a triple that does or does not surround a common triangle. Searching rather
    than hard-coding an index keeps the presets right if the sort order ever moves.
    """
    if spec == 'all':
        return list(range(len(directions)))
    if spec in ('oblate3', 'prolate3'):
        # PROLATE is the triple that surrounds a triangle. Signing those three axes
        # into a common direction is what says they cluster about it, and summing
        # segments along a cluster stretches the solid that way -- one long axis. The
        # other triple spreads instead, giving two long axes and one short: oblate.
        # This mapping was the wrong way round at first, and the two solids shipped
        # with each other's names; the shapes now say which is which (see the
        # principal spans in the report below).
        want = (spec == 'prolate3')
        for triple in combinations(range(len(directions)), 3):
            if surrounds_triangle([directions[i] for i in triple]) == want:
                return list(triple)
        log(f'Error: no triple of these {len(directions)} axes '
            f'{"surrounds" if want else "avoids"} a common triangle.')
        sys.exit(1)
    try:
        picked = [int(part) for part in spec.split(',')]
    except ValueError:
        log(f'Error: cannot read --pick={spec}; expected all, oblate3, prolate3 or '
            'a list like 0,2,4.')
        sys.exit(1)
    for index in picked:
        if index < 0 or index >= len(directions):
            log(f'Error: this source gives {len(directions)} directions, numbered 0 '
                f'to {len(directions) - 1}.')
            sys.exit(1)
    if len(set(picked)) != len(picked):
        log('Error: a zone is listed twice; each zone should appear once.')
        sys.exit(1)
    return picked


def zonish(seed_vertices, zones):
    """The candidate corners of the Minkowski sum: seed plus a segment per zone.

    Not all of these are corners of the result; the hull discards the rest.
    """
    offsets = [np.sum(np.array(signs)[:, None] * np.array(zones) / 2, axis=0)
               for signs in product((-1, 1), repeat=len(zones))]
    unique = {}
    for vertex in seed_vertices:
        for offset in offsets:
            point = vertex + offset
            unique.setdefault(tuple(np.round(point, WELD_DECIMALS)), point)
    return np.array(list(unique.values()))


def merge_coplanar(points):
    """The convex hull of `points`, its coplanar facets merged back into faces.

    QHull triangulates, so a square face arrives as two triangles and a decagon as
    eight. Grouping facets by plane equation reassembles each face, and sorting a
    group's corners by angle about the plane's normal turns the set into a polygon --
    counterclockwise seen from outside, because QHull's normals point that way.

    A point that merely LIES on a face is dropped rather than treated as a corner of
    it: every plane through such a point is the same one, so it adds a spurious
    vertex in the middle of an edge. That is what turned this construction's
    pentagons into decagons before the test was added.

    @returns (vertices, faces) using only the points that are really corners
    """
    hull = ConvexHull(points)
    groups = {}
    for (facet, equation) in zip(hull.simplices, hull.equations):
        key = tuple(np.round(equation, COPLANAR_DECIMALS))
        if key not in groups:
            groups[key] = (equation, set())
        groups[key][1].update(int(index) for index in facet)

    # Which planes meet at each point: a real corner has at least three, or two that
    # are distinct; a point sitting inside a face has only the one.
    planes_at = {}
    for (key, (_, corners)) in groups.items():
        for index in corners:
            planes_at.setdefault(index, set()).add(key)
    corners_only = {index for (index, planes) in planes_at.items()
                    if len(planes) > 1}

    used = sorted(corners_only)
    renumbered = {old: new for (new, old) in enumerate(used)}
    vertices = [points[index] for index in used]

    faces = []
    for (equation, corners) in groups.values():
        normal = np.array(equation[:3])
        kept = [index for index in corners if index in corners_only]
        middle = np.mean([points[index] for index in kept], axis=0)
        # Any direction across the normal will do as the zero of the angle; a frame
        # right-handed about the OUTWARD normal makes the sort counterclockwise seen
        # from outside.
        seed = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(seed, normal)) > 0.9:
            seed = np.array([0.0, 1.0, 0.0])
        axis1 = np.cross(normal, seed)
        axis1 /= np.linalg.norm(axis1)
        axis2 = np.cross(normal, axis1)

        def angle(index):
            offset = points[index] - middle
            return np.arctan2(np.dot(offset, axis2), np.dot(offset, axis1))

        faces.append([renumbered[index] for index in sorted(kept, key=angle)])
    return (vertices, faces)


def silhouette_sizes(seed_vertices, seed_faces, zones):
    """How many edges of the seed each zone sweeps into a face.

    An edge sweeps only if its two faces lie on opposite sides of the zone's
    direction -- the silhouette of the seed seen along that direction. Counted, not
    used to build: it is what makes check()'s face total a prediction.
    """
    normals = [np.array(grid_checks.face_normal([seed_vertices[i] for i in face]))
               for face in seed_faces]
    faces_by_edge = {}
    for (index, face) in enumerate(seed_faces):
        for i in range(len(face)):
            edge = tuple(sorted((face[i], face[(i + 1) % len(face)])))
            faces_by_edge.setdefault(edge, []).append(index)

    sizes = []
    for zone in zones:
        sizes.append(sum(1 for touching in faces_by_edge.values()
                         if len(touching) == 2
                         and np.dot(normals[touching[0]], zone)
                         * np.dot(normals[touching[1]], zone) < 0))
    return sizes


def check(seed_faces, zones, vertices, faces, silhouettes):
    """Verify the result against what the construction must give.

    @returns a one-line description, or exits if anything is off
    """
    n = len(zones)
    expected = len(seed_faces) + sum(silhouettes) + n * (n - 1)

    # Every face that is not the seed's is spanned by two directions, hence
    # centrally symmetric -- the property that makes the result zonish. The seed's
    # own faces here are odd-sided, so checking the even ones checks the new ones.
    skewed = [index for (index, face) in enumerate(faces)
              if len(face) % 2 == 0
              and grid_checks.face_skew(grid_checks.corners_of(vertices, face))
              > 1e-6]

    # Surrounding a triangle means the axes cluster, which stretches: prolate. This
    # said the opposite, as pick_zones did.
    shape = ('prolate' if n == 3 and surrounds_triangle(zones)
             else 'oblate' if n == 3 else '')
    report = (f'{n} zone(s){", " + shape if shape else ""}: {len(vertices)} '
              f'vertices, {len(grid_topology.edges_of(faces))} edges, '
              f'{len(faces)} faces ({grid_checks.census_text(faces)}); '
              f'expected {expected} = {len(seed_faces)} from the seed + '
              f'{sum(silhouettes)} along zones + {n * (n - 1)} where zones cross')

    problems = (
        grid_checks.check_counts(vertices, faces, {'faces': expected})
        + grid_checks.check_euler(vertices, faces)
        + ([f'{len(skewed)} even-sided face(s) not centrally symmetric: '
            f'{skewed[:5]}'] if skewed else [])
        + grid_checks.check_flat_faces(vertices, faces, 1e-6)
        + grid_checks.check_closed_surface(faces)
        + grid_checks.check_outward_winding(vertices, faces))

    if problems:
        # The census first: when a merge goes wrong it is what says how.
        log(report)
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)
    return report


def show_list():
    log(f'{"preset":<10} {"seed":<5} {"source":<9} {"pick":<9} produces')
    for (name, (seed, source, pick, produces)) in PRESETS.items():
        log(f'{name:<10} {seed:<5} {source:<9} {pick:<9} {produces}')
    log('')
    log('SOURCE is faces, faces:N or vertices -- zone directions taken from the')
    log('seed itself, one per antipodal pair. SEED is a data/ file stem.')
    log('--pick is all, oblate3, prolate3, or a list like 0,2,4.')


def main():
    options = [arg for arg in sys.argv[1:] if arg.startswith('--')]
    argv = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    (preset, spec) = (None, 'all')
    for option in options:
        if option == '--list':
            show_list()
            return
        if option.startswith('--preset='):
            preset = option.split('=', 1)[1]
        elif option.startswith('--pick='):
            spec = option.split('=', 1)[1]
        else:
            log(f'Error: unknown option {option}.')
            sys.exit(1)

    (preset_id, preset_name, categories) = (None, None, None)
    if preset is not None:
        if preset not in PRESETS:
            log(f'Error: unknown preset {preset!r}; expected one of '
                f'{", ".join(PRESETS)}.')
            sys.exit(1)
        (seed_stem, source, spec, preset_id, preset_name,
         categories) = PRESETS[preset]
    elif len(argv) >= 2:
        (seed_stem, source) = (argv[0], argv[1])
        argv = argv[2:]
    else:
        log('Usage: util/genZonish.py SEED SOURCE [--pick=SPEC] '
            '[gridId] [gridName]')
        log('       util/genZonish.py --preset=NAME [gridId] [gridName]')
        log('       util/genZonish.py --list')
        sys.exit(1)

    (seed_vertices, seed_faces, seed_name) = load_seed(seed_stem)
    directions = zone_directions(seed_vertices, seed_faces, source)
    picked = pick_zones(directions, spec)
    zones = [directions[index] for index in picked]

    (vertices, faces) = merge_coplanar(zonish(seed_vertices, zones))
    log(check(seed_faces, zones, vertices, faces,
              silhouette_sizes(seed_vertices, seed_faces, zones)))

    longest = max(float(np.linalg.norm(vertex)) for vertex in vertices)
    vertices = [vertex / longest for vertex in vertices]

    grid_id = argv[0] if len(argv) > 0 else (
        preset_id or f'zon{seed_stem}{len(zones)}')
    grid_name = argv[1] if len(argv) > 1 else (
        preset_name or f'{len(zones)}-zone {seed_name.lower()}')

    grid = {'gridId': grid_id, 'gridName': grid_name,
            'categories': categories or DEFAULT_CATEGORIES,
            # From argv, so a new option cannot be forgotten here. See
            # json_format.source_line.
            'source': json_format.source_line(),
            'vertices': [[round(float(component), 6) for component in vertex]
                         for vertex in vertices],
            'faces': faces}
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
