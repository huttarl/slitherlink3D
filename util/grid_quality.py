#!/usr/bin/env python3
"""Report the geometric quality of grid files: the things that make a solid
awkward to look at or to play on.

Usage:
    util/grid_quality.py [stem_or_path ...]

With no arguments, every data/*.json grid. Otherwise the ones named, by file stem
(`randD`) or path (`data/randD.json`, or a file anywhere).

What it measures, and why each one matters:

  edges       shortest / median / longest. A very short edge is hard to see and
              its two vertices read as one blob, since a vertex sphere's radius
              is a good fraction of a typical edge (VERTEX_RADIUS and
              EDGE_RADIUS in js/constants.js).
  sharpest    the sharpest corner angle of any face. A sliver face has almost no
              room for its clue digit, which clueRenderer sizes to the face's
              inscribed circle.
  inradius    smallest and largest face inscribed radius, which is directly the
              range of clue digit sizes.
  bow         how far a face's corners stray from flat, in units where the
              solid's circumradius is 1. Exactly 0 for a solid built from exact
              coordinates. util/obj2json.py trims to 6 decimals, which costs
              around 1e-6; a converted grid showing far more than that was
              rounded harder somewhere earlier -- data/tI.json sat at 3 decimals
              until it was reconverted, which cost it 5e-4 and was enough to put
              vertices measurably outside their neighbours' face planes.
  flattest    the smallest angle between the outward normals of two faces sharing
              an edge -- so 0 would mean the two are coplanar and read as one
              larger, faintly creased face.

              AESTHETIC, not a matter of correctness or of legibility. A solid may
              be perfectly convex with a dihedral angle of exactly 180 degrees: it
              loses STRICT convexity, not convexity. And the boundary stays plain
              to see whatever the angle, since edges are drawn as their own shaded
              cylinders rather than being left to the shading of the faces either
              side. What suffers is only the look: on a solid whose whole appeal
              is that its rhombi are all different, a pair that reads as one
              flattish blob is a wasted face.

              Reported because it was missed by eye on the wrong grid:
              data/spiral8.json had six edges under a degree while the complaint
              was made about spiral6, whose flattest is 5.7. For scale, the
              symmetric rhombic zonohedra are nowhere near -- daD 36 degrees,
              jtI 15.5 -- since a symmetry group keeps their faces apart.
  zones       how many directions the edges run in, and -- when every face has an
              even number of sides -- how far the worst face is from being
              centrally symmetric, plus (for quadrilaterals) its longest side over
              its shortest. This is the zonohedron test: a zonohedron is a sum of
              line segments, so its edges are translates of a few generating
              vectors, and every face is itself centrally symmetric. Directions are
              therefore few and skew 0, with the ratio 1 for the rhombic ones.
              Being told that a zonohedron's edges run in parallel families is no
              use if the solid on screen doesn't show it.

              An odd-sided face settles it with no measuring, since such a face
              cannot be centrally symmetric. Even faces are NOT only quadrilaterals:
              the truncated octahedron and truncated cuboctahedron are zonohedra
              whose hexagons and octagons are centrally symmetric, which is the
              degenerate case where coplanar generators merge two parallelograms
              into one larger face.
  shape       how far the solid is from having no distinguished axis: the width
              along each of its three principal axes, longest first. One long axis
              and two alike is PROLATE, a rugby ball; two alike and one short is
              OBLATE, a discus. Reported because two grids shipped under each
              other's names -- zonaD3o was the prolate one -- and a NAME has no
              invariant to violate, so nothing caught it. Where the name claims
              either word, this now checks it and says so when they disagree.
  degrees     how many faces meet at each vertex. Slitherlink's vertex rule says
              0 or 2 of a vertex's edges are used, so a 3-valent vertex leaves
              four possibilities and a 10-valent one forty-six: high degree means
              weak propagation, and puzzle generation feels it.
  winding     every face should be counterclockwise seen from outside, which the
              renderer and the picking code both assume.

Reporting only, and standard library only. Verification proper lives in the test
suites and in each generator's own checks.
"""
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grid_checks import (  # noqa: E402
    centroid, direction_classes, distance, dot, face_bow, face_normal,
    face_skew, inscribed_radius, sharpest_corner, side_ratio, subtract,
    wound_outward,
)
import grid_topology  # noqa: E402
from grid_topology import (boundary_cycles, edge_degrees, edges_of,  # noqa: E402
                           vertex_degrees)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# How far apart two edge directions may be and still be called the same one, for
# the zones line. Loose on purpose: a grid converted by obj2json has its
# coordinates rounded, which moves a unit vector by roughly the same few
# thousandths that shows up as bow, and calling those separate directions would
# report a rhombic triacontahedron as having sixty zones instead of six.
DIRECTION_TOLERANCE = 5e-3


# How much longer one principal axis must be than the next before the solid counts as
# having a distinguished one. Every polyhedron's widths differ a little just from
# faceting -- the rhombic triacontahedron, about as round as they come, still varies by
# 11% -- so a threshold under that would call half of data/ prolate. The three-zone
# pair sit at 26% and 38%, and the capsid at 85%, so this separates them comfortably.
AXIS_RATIO = 1.15

# Below this, two faces sharing an edge are near enough to coplanar that the pair
# reads as one face on screen. A degree is generous: the symmetric rhombic
# zonohedra sit at 15 to 36 degrees, and the asymmetric spirals that raised the
# question at 1.6 to 2.1, so anything under a degree is in a class of its own.
FLAT_EDGE_DEGREES = 1.0


def flattest_edge(vertices, faces):
    """The smallest angle between the outward normals of two faces sharing an edge.

    @returns (that angle in degrees, how many shared edges are under
        FLAT_EDGE_DEGREES). 180 and 0 for a grid with no shared edges at all.
    """
    middle = centroid(vertices)
    normals = []
    for face in faces:
        corners = [vertices[i] for i in face]
        normal = face_normal(corners)
        length = math.sqrt(dot(normal, normal))
        normal = [component / length for component in normal]
        # Orient outward. Safe here in a way it would not be on a torus: every
        # grid this measures encloses the origin. See ideas/genus-1-objects.md.
        if dot(normal, subtract(centroid(corners), middle)) < 0:
            normal = [-component for component in normal]
        normals.append(normal)

    owners = {}
    for (index, face) in enumerate(faces):
        for ekey in grid_topology.face_edges(face):
            owners.setdefault(ekey, []).append(index)

    flattest = 180.0
    flat_count = 0
    for sharers in owners.values():
        if len(sharers) != 2:
            continue        # a rim edge has one face; nothing to compare
        (a, b) = sharers
        # Clamp: a dot product of 1.0000000002 is a domain error in acos.
        cosine = max(-1.0, min(1.0, dot(normals[a], normals[b])))
        angle = math.degrees(math.acos(cosine))
        flattest = min(flattest, angle)
        if angle < FLAT_EDGE_DEGREES:
            flat_count += 1
    return (flattest, flat_count)


def principal_spans(vertices):
    """How wide the solid is along each principal axis, and what shape that makes it.

    The axes come from the covariance of the vertices, which is where the solid's own
    symmetry puts them; the widths are then measured along those axes and sorted, since
    the widest axis is not always the one with the most variance.

    Stdlib only, like the rest of this script, so the eigenvectors are found by
    Jacobi rotations on the 3x3 covariance -- a dozen sweeps is ample at this size.

    @returns (widths longest-first, 'prolate' | 'oblate' | 'no distinguished axis')
    """
    middle = centroid(vertices)
    moved = [[v[axis] - middle[axis] for axis in range(3)] for v in vertices]
    covariance = [[sum(p[i] * p[j] for p in moved) for j in range(3)]
                  for i in range(3)]
    axes = jacobi_axes(covariance)
    widths = sorted((max(dot(p, axis) for p in moved) - min(dot(p, axis) for p in moved)
                     for axis in axes), reverse=True)
    (long, middling, short) = widths
    # Which ratio stands out: one long axis, or one short one.
    if max(long / middling, middling / short) < AXIS_RATIO:
        return (widths, 'no distinguished axis')
    return (widths, 'prolate' if long / middling > middling / short else 'oblate')


def jacobi_axes(matrix, sweeps=12):
    """Eigenvectors of a symmetric 3x3, as three unit vectors.

    The classic Jacobi rotation: zero the largest off-diagonal entry, repeat. Written
    out because this script imports nothing but the standard library, and numpy would
    be the only reason to break that.
    """
    a = [row[:] for row in matrix]
    axes = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(sweeps):
        (p, q) = max(((i, j) for i in range(3) for j in range(i + 1, 3)),
                     key=lambda pair: abs(a[pair[0]][pair[1]]))
        if abs(a[p][q]) < 1e-15:
            break
        theta = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        (c, s) = (math.cos(theta), math.sin(theta))
        for k in range(3):
            (akp, akq) = (a[k][p], a[k][q])
            a[k][p] = c * akp - s * akq
            a[k][q] = s * akp + c * akq
        for k in range(3):
            (apk, aqk) = (a[p][k], a[q][k])
            a[p][k] = c * apk - s * aqk
            a[q][k] = s * apk + c * aqk
        for k in range(3):
            (kp, kq) = (axes[k][p], axes[k][q])
            axes[k][p] = c * kp - s * kq
            axes[k][q] = s * kp + c * kq
    # The columns are the eigenvectors; take them as rows.
    return [[axes[row][col] for row in range(3)] for col in range(3)]


def report(path):
    grid = json.loads(path.read_text())
    V = grid['vertices']
    F = grid['faces']
    edges = edges_of(F)
    lengths = sorted(distance(V[a], V[b]) for (a, b) in edges)
    median = statistics.median(lengths)
    faces = [[V[i] for i in face] for face in F]
    centre = centroid(V)
    sizes = {}
    for face in F:
        sizes[len(face)] = sizes.get(len(face), 0) + 1

    inradii = [inscribed_radius(f) for f in faces]
    # An open grid says so (see docs/json-format.md), and the two expectations that
    # depend on it are Euler's formula and what a vertex's degree means.
    #
    # Euler is not simply 0 for an open surface: it is 2 - (however many rims), so a
    # closed solid wants 2, a capsid with one portal wants 1 and a tube open at both
    # ends wants 0. Counting them rather than assuming is what tells those apart --
    # this said "want 0" to the capsid before it counted.
    closed = grid.get('closed', True)
    rims = 0 if closed else len(boundary_cycles(F))
    wanted_euler = 2 - rims
    print(f'{grid.get("gridName", path.stem)}  ({path.name})')
    print(f'  V={len(V)} E={len(edges)} F={len(F)}   '
          f'Euler {len(V) - len(edges) + len(F)} (want {wanted_euler}'
          + ('' if closed else f', open with {rims} rim'
                               + ('s' if rims != 1 else '')) + ')   faces: '
          + ', '.join(f'{c}x{s}' for (s, c) in sorted(sizes.items())))
    print(f'  edges     {lengths[0]:.3f} / {median:.3f} / {lengths[-1]:.3f}  '
          f'(shortest is {lengths[0] / median:.0%} of median)')
    print(f'  sharpest  {min(sharpest_corner(f) for f in faces):.1f} degrees')
    print(f'  inradius  {min(inradii):.3f} to {max(inradii):.3f}  '
          f'(x{max(inradii) / min(inradii):.1f})')
    print(f'  bow       {max(face_bow(f) for f in faces):.1e}')
    (flattest, flat_count) = flattest_edge(V, F)
    print(f'  flattest  {flattest:.2f} degrees between adjacent faces'
          + (f'  -- {flat_count} EDGE(S) UNDER {FLAT_EDGE_DEGREES:.0f} DEGREE, '
             'so those pairs look like one face' if flat_count else ''))
    zones = len(direction_classes(V, F, DIRECTION_TOLERANCE))
    if all(len(face) % 2 == 0 for face in F):
        # Even-sided throughout, so central symmetry is testable face by face --
        # which is what face_skew measures for any even face, not just a quad. The
        # side ratio only means something for quads, where equal sides are what
        # makes a rhombus; a zonohedron's hexagon has no reason to be equilateral.
        line = (f'  zones     {zones} edge directions; worst face skew '
                f'{max(face_skew(f) for f in faces):.1e}')
        if all(len(face) == 4 for face in F):
            line += f', side ratio {max(side_ratio(f) for f in faces):.2f}'
        else:
            line += ' (centrally symmetric faces)'
        print(line)
    else:
        # An odd-sided face cannot be centrally symmetric, and every face of a
        # zonohedron must be, so this settles it with no measuring. The direction
        # count is still a fact about any solid, and a small one is interesting in
        # itself (a cube's edges run three ways).
        print(f'  zones     {zones} edge directions '
              f'(an odd-sided face, so no zonohedron)')
    # Faces per vertex on a closed grid, edges per vertex on an open one. The two are
    # the same number wherever every edge has two faces, and the EDGE count is the one
    # the vertex rule is about -- a loop needs 0 or 2 edges at every vertex. Reporting
    # faces on the nanotube would have said "20x1", which reads as twenty dead ends
    # when those atoms have two perfectly good edges apiece.
    (spans, character) = principal_spans(V)
    line = ('  shape     widths ' + ' / '.join(f'{s:.3f}' for s in spans)
            + f' along its principal axes: {character}')
    claimed = next((word for word in ('oblate', 'prolate')
                    if word in grid.get('gridName', '').lower()), None)
    if claimed and claimed != character:
        # The check that was missing when zonaD3o and zonaD3p shipped swapped.
        line += f'  -- BUT THE NAME SAYS {claimed.upper()}'
    print(line)

    tally = {}
    for degree in (vertex_degrees(F) if closed else edge_degrees(F)).values():
        tally[degree] = tally.get(degree, 0) + 1
    print(f'  degrees   '
          + ', '.join(f'{count}x{degree}' for (degree, count) in sorted(tally.items()))
          # No claim about what a rim vertex comes to: 2 on a tube, 5 round a capsid's
          # portal, and whatever the next open solid brings.
          + ('' if closed else '  (edges per vertex)'))
    crooked = [i for (i, f) in enumerate(faces) if not wound_outward(f, centre)]
    print(f'  winding   ' + ('all outward' if not crooked
                             else f'{len(crooked)} face(s) inward: {crooked[:5]}'))


def main():
    if len(sys.argv) > 1:
        paths = []
        for argument in sys.argv[1:]:
            path = Path(argument)
            paths.append(path if path.suffix == '.json'
                         else DATA_DIR / f'{argument}.json')
    else:
        paths = sorted(p for p in DATA_DIR.glob('*.json')
                       if not p.name.endswith('-puzzles.json')
                       and p.name != 'grids.json')
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print(f'No such grid file: {", ".join(missing)}', file=sys.stderr)
        sys.exit(1)
    for path in paths:
        report(path)


if __name__ == '__main__':
    main()
