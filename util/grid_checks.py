#!/usr/bin/env python3
"""Geometric checks a generated solid must pass before it is written.

Every grid generator ends the same way: measure what it just built, and refuse to
write it if the numbers are wrong. They had each grown their own version of that,
so the same checks existed four times over -- Euler's formula twice, face flatness
four times in three different formulations, outward winding three times, the face
census in four places. This is the one copy.

Each `check_*` returns a **list of problem strings**, empty when all is well, so a
generator composes the checks it needs and keeps its own reporting:

    problems = (grid_checks.check_euler(vertices, faces)
                + grid_checks.check_flat_faces(vertices, faces, 1e-9)
                + grid_checks.check_outward_winding(vertices, faces))
    if problems: ...

Reporting is deliberately left to the caller. `genUniformPolyh.py` returns its
messages so `--check` can print them without writing; the others log and exit. One
shared reporter would have to serve both, and there is nothing to gain from it.

**Standard library only**, like `grid_topology.py`, which it builds on. That is not
incidental: `genPrism.py` advertises needing nothing installed, and these checks
are O(faces) on a couple of hundred faces, so numpy would buy nothing and cost that
property. The functions index `vertices` and do arithmetic on coordinates, so they
work whether a caller passes lists of lists or numpy arrays.
"""
import math

from grid_topology import edges_of, vertex_degrees


# --------------------------------------------------------------------------
# Vector arithmetic
# --------------------------------------------------------------------------

def subtract(p, q):
    return [p[i] - q[i] for i in range(3)]


def dot(u, v):
    return sum(u[i] * v[i] for i in range(3))


def cross(u, v):
    return [u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0]]


def norm(u):
    return math.sqrt(dot(u, u))


def distance(p, q):
    return norm(subtract(p, q))


def centroid(points):
    return [sum(p[i] for p in points) / len(points) for i in range(3)]


def corners_of(vertices, face):
    """A face's corner coordinates, in order round it."""
    return [vertices[index] for index in face]


# --------------------------------------------------------------------------
# Face geometry
# --------------------------------------------------------------------------

def face_normal(corners):
    """A face's normal, by Newell's method: the sum of the cross products of
    successive edge vectors taken about the face's centroid.

    Not normalized. Summing round the whole face rather than taking one cross
    product of the first three corners is what makes this trustworthy on a face
    whose first three corners happen to be nearly collinear -- possible on a
    decagon, and it would make a first-three normal wildly imprecise while
    reporting nothing amiss.
    """
    middle = centroid(corners)
    total = [0.0, 0.0, 0.0]
    for i in range(len(corners)):
        this = subtract(corners[i], middle)
        following = subtract(corners[(i + 1) % len(corners)], middle)
        piece = cross(this, following)
        total = [total[axis] + piece[axis] for axis in range(3)]
    return total


def face_bow(corners):
    """How far a face's corners stray from being flat, as a distance.

    Measured from the plane through the face's centroid perpendicular to its
    Newell normal, which for a nearly flat face is within rounding of the
    least-squares best-fit plane an SVD would give -- and needs no numpy.
    Exactly 0 for a face built from exact coordinates.
    """
    normal = face_normal(corners)
    length = norm(normal)
    if length == 0:
        return math.inf          # degenerate face; no plane to measure against
    unit = [component / length for component in normal]
    middle = centroid(corners)
    return max(abs(dot(unit, subtract(corner, middle))) for corner in corners)


def edge_lengths(corners):
    """The lengths of a face's sides, in order round it."""
    return [distance(corners[i], corners[(i + 1) % len(corners)])
            for i in range(len(corners))]


def corner_angles(corners):
    """A face's interior angles in degrees, in order round it."""
    angles = []
    for i in range(len(corners)):
        previous = subtract(corners[i - 1], corners[i])
        following = subtract(corners[(i + 1) % len(corners)], corners[i])
        scale = norm(previous) * norm(following)
        if scale == 0:
            angles.append(0.0)
            continue
        cosine = max(-1.0, min(1.0, dot(previous, following) / scale))
        angles.append(math.degrees(math.acos(cosine)))
    return angles


def inscribed_radius(corners):
    """Twice the area over the perimeter: the inscribed circle of a regular
    polygon, and a fair stand-in for how much room a clue digit has."""
    middle = centroid(corners)
    area = sum(norm(cross(subtract(corners[i], middle),
                          subtract(corners[(i + 1) % len(corners)], middle))) / 2
               for i in range(len(corners)))
    perimeter = sum(edge_lengths(corners))
    return 2 * area / perimeter if perimeter else 0.0


def sharpest_corner(corners):
    """The sharpest interior angle of a face, in degrees."""
    return min(corner_angles(corners), default=180.0)


def wound_outward(corners, solid_centre):
    """Whether a face is wound counterclockwise seen from outside the solid."""
    return dot(face_normal(corners), subtract(centroid(corners), solid_centre)) > 0


def face_census(faces):
    """How many faces of each size, as {sides: count}."""
    census = {}
    for face in faces:
        census[len(face)] = census.get(len(face), 0) + 1
    return census


def census_text(faces):
    """The census as "12 5-gons, 20 6-gons"."""
    return ', '.join(f'{count} {size}-gons'
                     for (size, count) in sorted(face_census(faces).items()))


# --------------------------------------------------------------------------
# Checks. Each returns a list of problems; empty means it passed.
# --------------------------------------------------------------------------

def check_counts(vertices, faces, expected):
    """Compare against expected counts: any of 'vertices', 'edges', 'faces'.

    Worth checking even when the construction "obviously" gives the right number:
    a wrong lattice or a wrong seed still yields *a* polyhedron, just not the one
    asked for, and the counts are the cheapest thing that notices.
    """
    got = {'vertices': len(vertices), 'faces': len(faces),
           'edges': len(edges_of(faces))}
    return [f'{count} {what} expected, got {got[what]}'
            for (what, count) in expected.items() if got[what] != count]


def check_euler(vertices, faces):
    """V - E + F = 2, which every solid sphere-like surface satisfies."""
    (V, E, F) = (len(vertices), len(edges_of(faces)), len(faces))
    if V - E + F == 2:
        return []
    return [f"Euler's formula fails: V-E+F = {V}-{E}+{F} = {V - E + F}"]


def check_census(faces, expected):
    """Compare the face census against an expected {sides: count}."""
    census = face_census(faces)
    if census == expected:
        return []
    return [f'face census {census} != expected {expected}']


def check_vertex_degrees(faces, expected):
    """Every vertex should meet one of the `expected` numbers of faces."""
    degrees = set(vertex_degrees(faces).values())
    if degrees <= set(expected):
        return []
    return [f'vertex degrees should be {sorted(expected)}, got {sorted(degrees)}']


def check_equal_edge_lengths(vertices, faces, tolerance):
    """Every edge the same length -- true of the uniform solids and the
    prisms/antiprisms with regular faces, and not of most other solids."""
    lengths = [distance(vertices[a], vertices[b]) for (a, b) in edges_of(faces)]
    if not lengths:
        return ['no edges']
    spread = max(lengths) - min(lengths)
    if spread <= tolerance:
        return []
    return [f'edge lengths vary by {spread:.3g} '
            f'(min {min(lengths):.6f}, max {max(lengths):.6f})']


def check_equal_vertex_radii(vertices, tolerance, centre=None):
    """Every vertex the same distance from the centre, i.e. the solid has a
    circumsphere. True of the uniform solids; false of the Catalan ones."""
    middle = centre if centre is not None else centroid(vertices)
    radii = [distance(v, middle) for v in vertices]
    spread = max(radii) - min(radii)
    if spread <= tolerance:
        return []
    return [f'vertex radii vary by {spread:.3g} '
            f'(min {min(radii):.6f}, max {max(radii):.6f})']


def check_flat_faces(vertices, faces, tolerance):
    """No face may bend. A face that isn't flat has no well-defined plane to draw
    a clue digit on, and the renderer assumes one."""
    worst = 0.0
    worst_face = None
    for (index, face) in enumerate(faces):
        bow = face_bow(corners_of(vertices, face))
        if bow > worst:
            (worst, worst_face) = (bow, index)
    if worst <= tolerance:
        return []
    return [f'faces are not flat (worst bow {worst:.3g}, on face {worst_face})']


def check_closed_surface(faces):
    """Every directed edge appears exactly once, and its reverse exists.

    That is what makes the faces a closed, consistently wound surface. It catches
    a duplicated or dropped face, which Euler's formula alone can miss when two
    errors cancel.
    """
    directed = []
    for face in faces:
        for i in range(len(face)):
            directed.append((face[i], face[(i + 1) % len(face)]))
    problems = []
    if len(directed) != len(set(directed)):
        problems.append(f'{len(directed) - len(set(directed))} directed edge(s) '
                        f'used more than once (faces overlap or repeat)')
    unpaired = sum(1 for (a, b) in set(directed) if (b, a) not in set(directed))
    if unpaired:
        problems.append(f'{unpaired} directed edge(s) have no reverse '
                        f'(inconsistent winding, or a hole)')
    return problems


def check_outward_winding(vertices, faces, centre=None):
    """Every face wound counterclockwise seen from outside.

    The renderer and the picking code both assume it. Measured against the solid's
    centroid rather than the origin, so it holds for a solid that isn't centred.
    """
    middle = centre if centre is not None else centroid(vertices)
    inward = [index for (index, face) in enumerate(faces)
              if not wound_outward(corners_of(vertices, face), middle)]
    if not inward:
        return []
    return [f'{len(inward)} face(s) wound inward: {inward[:5]}']


def check_regular_faces(vertices, faces, tolerance):
    """Every face a regular polygon: equal sides AND equal corner radii.

    Both are needed. Equal sides alone allows a rhombus; for a flat face, equal
    sides plus corners equidistant from the centre is regularity.
    """
    problems = []
    for (index, face) in enumerate(faces):
        corners = corners_of(vertices, face)
        lengths = edge_lengths(corners)
        if max(lengths) - min(lengths) > tolerance:
            problems.append(f'face {index} has unequal sides '
                            f'({min(lengths):.6f} to {max(lengths):.6f})')
        middle = centroid(corners)
        radii = [distance(corner, middle) for corner in corners]
        if max(radii) - min(radii) > tolerance:
            problems.append(f'face {index} is not regular: corners '
                            f'{min(radii):.6f} to {max(radii):.6f} from its centre')
    return problems


def face_shape(vertices, face):
    """A face's shape, as (sorted edge lengths, sorted angles).

    Sorted, so two congruent faces compare equal however they are wound or where
    they start. That makes it a fingerprint for congruence.
    """
    corners = corners_of(vertices, face)
    return (sorted(edge_lengths(corners)), sorted(corner_angles(corners)))


def check_congruent_faces(vertices, faces, length_tolerance, angle_tolerance):
    """Every face the same shape as every other -- what makes the dual of a
    uniform solid a Catalan solid.

    Lengths and angles get separate tolerances because their units are unrelated:
    one figure says nothing about the other, and comparing an angle in degrees
    against a length tolerance once condemned a perfectly good pentakis
    dodecahedron over a quarter of a degree.
    """
    if not faces:
        return ['no faces']
    shapes = [face_shape(vertices, face) for face in faces]
    (first_edges, first_angles) = shapes[0]
    problems = []
    (worst_length, worst_angle) = (0.0, 0.0)
    for (index, (edges, angles)) in enumerate(shapes[1:], start=1):
        if len(edges) != len(first_edges):
            problems.append(f'face {index} has {len(edges)} sides, face 0 has '
                            f'{len(first_edges)}')
            continue
        worst_length = max(worst_length,
                           max(abs(a - b) for (a, b) in zip(edges, first_edges)))
        worst_angle = max(worst_angle,
                          max(abs(a - b) for (a, b) in zip(angles, first_angles)))
    if worst_length > length_tolerance:
        problems.append(f'faces differ in shape: edges by up to {worst_length:.2e}')
    if worst_angle > angle_tolerance:
        problems.append(f'faces differ in shape: angles by up to '
                        f'{worst_angle:.2f} degrees')
    return problems
