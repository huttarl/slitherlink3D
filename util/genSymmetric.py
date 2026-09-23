#!/usr/bin/env python3
"""Generate a random solid with tetrahedral rotational symmetry, as grid JSON.

Usage:
    util/genSymmetric.py [orbits] [--relax=T] [--min-edge=F] [--regularize]
                         [--seed=N] [--vertex-axes] [--face-axes] [--edge-axes]
                         [--id=ID] [--name=NAME]

Output goes to stdout; progress, the census and the self-check go to stderr.

How it works: a few random points are chosen, and the 12 rotations of the
tetrahedral group T carry each one to 12 places. Each such set of 12 is an ORBIT.
The convex hull of all the points is a triangulation with the same symmetry, and
its polar dual (genGoldberg.polar_dual) is the solid: one face per point, every
face exactly flat, three faces at every vertex.

What the options mean for the solid:
  orbits          how many random orbits (default 6), 12 faces each. Every face
                  in an orbit is congruent to the others, so each orbit
                  contributes 12 faces of one size.
  --vertex-axes   also put a point on each of the tetrahedron's 4 vertex axes,
  --face-axes     or its 4 face axes, or its 6 edge axes. These points are fixed
  --edge-axes     by some rotations, so their faces are forced to have a
                  multiple of 3 sides (vertex and face axes: 3, 6, 9...) or of 2
                  (edge axes: 4, 6, 8...).
  --relax         how evenly to spread the points, 0 to 1 (default 0.5). As in
                  genRandomPolyh.py, 0 leaves them where they fell and gives the
                  most varied face sizes, and 1 spreads them evenly.
  --min-edge      the shortest edge to allow, as a fraction of the median
                  (default 0.4, as in genRandomPolyh.py; 0 to leave the points
                  where the draw put them). See separate_short_edges.
  --regularize    then move the points to make every face as nearly regular
                  -- equal sides, equal angles -- as its neighbors allow, keeping
                  the census. Off by default, so commands written before it
                  existed still make the same solid. See regularize.
  --seed          the random draw (default: chosen at random, and reported).

Euler's formula constrains the census: summing (6 - sides) over the faces always
gives 12. With 12 congruent faces per orbit, the orbits' own (6 - sides) must sum
to 1, less whatever the axis points take. See docs/generating-grids.md.

The solid is checked before it is written: tetrahedral symmetry of the
triangulation, Euler, flat faces, a closed and outward-wound surface, and three
faces per vertex. A draw whose hull has coplanar points is rejected and redrawn,
since the hull would then split a flat facet into triangles arbitrarily, which
breaks the symmetry and gives the dual coincident vertices.

Requires numpy and scipy.
"""
import sys

import numpy as np
from scipy.spatial import ConvexHull

import grid_checks
import json_format
from genGoldberg import polar_dual
from genUniformPolyh import merge_coplanar_faces

# How many fresh draws to try before giving up on a degenerate configuration.
MAX_ATTEMPTS = 50

# Two points closer than this are treated as the same point.
SAME_POINT = 1e-6

# Repulsion schedule: the step shrinks until moves fall below the tolerance.
RELAX_STEP = 0.05
RELAX_COOLING = 0.995
RELAX_TOLERANCE = 1e-7
RELAX_MAX_ITERATIONS = 5000

# The shortest dual edge to allow, as a fraction of the median: the same
# default as genRandomPolyh.py's --min-edge.
MIN_EDGE_FRACTION = 0.4

# Short-edge separation: the largest step a representative may take, the step
# below which it gives up, the most rounds, and the finite-difference offset.
SEPARATE_STEP = 0.02
SEPARATE_MIN_STEP = 1e-7
SEPARATE_ROUNDS = 500
GRADIENT_H = 1e-7
# Aim this far past the target: the descent approaches the line from below and
# slows as it nears it, so aiming at the line itself leaves edges a hair short.
SEPARATE_OVERSHOOT = 1.05

# Regularizing: its largest step, most rounds, and the smallest relative gain
# in a round that is worth another. MIN_FACE_ANGLE is the flattest two
# neighboring faces may meet, and CONSTRAINT_WEIGHT how hard the two held
# limits (that and the minimum edge) outweigh the regularity itself.
REGULARIZE_STEP = 0.01
REGULARIZE_ROUNDS = 600
REGULARIZE_TOLERANCE = 1e-5
MIN_FACE_ANGLE = 8.0
CONSTRAINT_WEIGHT = 50.0
# The straightest a corner should be, in degrees, and how much that counts
# beside the average regularity. A corner near 180 hides a side, which is what
# makes a face hard to count; a regular nonagon's corners are 140. Averaging
# alone let the straightest corners get WORSE while the rest improved, since a
# face's angles have a fixed sum and a squeezed corner pushes its excess into
# the others.
STRAIGHT_CORNER = 145.0
STRAIGHT_WEIGHT = 20.0


def tetrahedral_rotations():
    """The 12 rotations of the tetrahedral group T, as exact 3x3 matrices.

    Each is a cyclic permutation of the axes followed by an even number of sign
    flips: 3 permutations times 4 sign patterns.
    """
    identity = np.eye(3)
    cycle = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)
    permutations = [identity, cycle, cycle @ cycle]
    signs = [np.diag(d) for d in ([1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1])]
    return [s @ p for s in signs for p in permutations]


# The points on the tetrahedron's symmetry axes, by which feature the axis runs
# through. Each set is one orbit of T.
VERTEX_AXES = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]) / 3 ** 0.5
FACE_AXES = -VERTEX_AXES
EDGE_AXES = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0],
                      [0, 0, 1], [0, 0, -1]], dtype=float)


def log(*args):
    print(*args, file=sys.stderr)


def orbit(point, rotations):
    """Every image of `point` under the rotations, in the rotations' order."""
    return np.array([r @ point for r in rotations])


def all_points(representatives, fixed, rotations):
    """The full point set: each representative's orbit, then the fixed points."""
    parts = [orbit(p, rotations) for p in representatives]
    if len(fixed):
        parts.append(fixed)
    return np.vstack(parts)


def random_unit_vectors(count, rng):
    vectors = rng.normal(size=(count, 3))
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def relax(representatives, fixed, rotations):
    """Spread the points by mutual repulsion, keeping the symmetry exact.

    Only the representatives move, each pushed by every other point including
    its own images; the images are then recomputed from them. Moving the full
    set instead would stay symmetric only in exact arithmetic, and rounding would
    slowly erode it. The axis points are fixed: moving one off its axis would
    break the symmetry by definition.

    @returns the converged representatives, as a new array
    """
    reps = representatives.copy()
    step = RELAX_STEP
    for _ in range(RELAX_MAX_ITERATIONS):
        points = all_points(reps, fixed, rotations)
        forces = np.zeros_like(reps)
        for (i, p) in enumerate(reps):
            offsets = p - points
            distances = np.linalg.norm(offsets, axis=1)
            # The representative itself is row i * len(rotations), at distance 0.
            others = distances > SAME_POINT
            forces[i] = (offsets[others]
                         / distances[others][:, None] ** 3).sum(axis=0)
            # Only the part along the sphere moves the point.
            forces[i] -= np.dot(forces[i], p) * p
        largest = np.max(np.linalg.norm(forces, axis=1))
        if largest == 0:
            break
        moved = reps + step * forces / largest
        moved /= np.linalg.norm(moved, axis=1, keepdims=True)
        movement = np.max(np.linalg.norm(moved - reps, axis=1))
        reps = moved
        step *= RELAX_COOLING
        if movement < RELAX_TOLERANCE:
            break
    return reps


def partially_relaxed(representatives, fixed, rotations, fraction):
    """Move each representative `fraction` of the way to where relaxing puts it.

    The same meaning of --relax as genRandomPolyh.py: the repulsion is run to
    convergence and the points are then moved that fraction of the way there,
    so the knob means the same thing whatever the point count.
    """
    if fraction <= 0:
        return representatives
    converged = relax(representatives, fixed, rotations)
    blended = (1 - fraction) * representatives + fraction * converged
    return blended / np.linalg.norm(blended, axis=1, keepdims=True)


def index_of(point, points):
    """The index of the point in `points` nearest `point`, or None if none is
    within SAME_POINT of it."""
    distances = np.linalg.norm(points - point, axis=1)
    nearest = int(np.argmin(distances))
    return nearest if distances[nearest] < SAME_POINT else None


def symmetry_problems(points, triangles, rotations):
    """Check that every rotation carries the triangulation onto itself.

    The dual is computed from the triangulation alone, so a symmetric
    triangulation means a symmetric solid.
    """
    wanted = {frozenset(int(v) for v in t) for t in triangles}
    for (n, r) in enumerate(rotations):
        mapping = [index_of(r @ p, points) for p in points]
        if None in mapping:
            return [f'rotation {n} carries a point to where there is none']
        image = {frozenset(mapping[v] for v in t) for t in wanted}
        if image != wanted:
            return [f'rotation {n} does not carry the triangulation onto itself']
    return []


def has_mirror_symmetry(points):
    """Whether the point set is also symmetric under an improper operation.

    Checks the two that would extend T to an achiral group: inversion through
    the centre (giving T_h) and the mirror swapping x and y (giving T_d). Random
    orbits have neither except by coincidence, so the result is normally
    chiral, like the snub cube.
    """
    inversion = -np.eye(3)
    mirror = np.array([[0, 1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    return any(all(index_of(m @ p, points) is not None for p in points)
               for m in (inversion, mirror))


def usable_hull(points):
    """The points' convex hull, or None if it would make a bad solid."""
    # Distinct points: a representative too near an axis gives images that
    # nearly coincide.
    gaps = np.linalg.norm(points[:, None] - points[None, :], axis=2)
    np.fill_diagonal(gaps, np.inf)
    if gaps.min() < 1e-3:
        return None

    hull = ConvexHull(points)
    if len(hull.vertices) != len(points):
        return None       # a point inside the hull would get no face
    if len(merge_coplanar_faces(points, hull)) != len(hull.simplices):
        return None       # coplanar points: see the module docstring
    return hull


def draw(orbits, fixed, rotations, relax_fraction, rng):
    """One attempt: (representatives, points, hull), or None if the hull is
    unusable."""
    reps = random_unit_vectors(orbits, rng)
    reps = partially_relaxed(reps, fixed, rotations, relax_fraction)
    points = all_points(reps, fixed, rotations)
    hull = usable_hull(points)
    return None if hull is None else (reps, points, hull)


def dual_edges_of(triangles):
    """The dual's edges, as pairs of triangle indices: one pair per primal edge,
    the two triangles that share it."""
    sharing = {}
    for (t, triangle) in enumerate(triangles):
        for k in range(3):
            edge = tuple(sorted((int(triangle[k]), int(triangle[(k + 1) % 3]))))
            sharing.setdefault(edge, []).append(t)
    return np.array(list(sharing.values()))


def poles_of(points, triangles):
    """The dual's vertices: each triangle's pole, the point p with p.a = p.b =
    p.c = 1 for its three corners -- exactly what polar_dual computes."""
    corners = points[triangles]
    return np.linalg.solve(corners, np.ones((len(corners), 3, 1)))[..., 0]


def dual_edge_lengths(points, triangles, dual_edges):
    """How long each dual edge is: the distance between the poles of its two
    triangles, which is where polar_dual puts the dual's vertices."""
    poles = poles_of(points, triangles)
    return np.linalg.norm(poles[dual_edges[:, 0]] - poles[dual_edges[:, 1]], axis=1)


def separate_short_edges(reps, fixed, rotations, min_fraction):
    """Move the representatives until no dual edge is shorter than
    `min_fraction` of the median, keeping the symmetry and flatness exact.

    A short dual edge comes from two adjacent hull triangles that are nearly
    coplanar: their poles, the dual's two vertices, then nearly coincide. So
    this moves the PRIMAL points, deepening the fold between such triangles,
    rather than nudging the dual's vertices as genRandomPolyh.py does. The dual
    of any point set is exactly flat, so flatness costs nothing, and moving one
    representative per orbit keeps the symmetry exact.

    Gradient descent on the total squared shortfall, with the triangulation
    held FIXED. A nearly coplanar pair of triangles can also be resolved by
    flipping to the other diagonal, but a flip changes vertex degrees and so
    face sizes: left free to flip, this turned two orbits of squares and
    octagons into hexagons, spending the variety the draw produced. So a step is
    kept only if the hull it actually produces is usable, has the same
    triangles, and has less shortfall.

    @returns (representatives, shortest before, shortest after), the shortest
        dual edge given as a fraction of the median
    """
    hull = usable_hull(all_points(reps, fixed, rotations))
    dual_edges = dual_edges_of(hull.simplices)
    lengths = dual_edge_lengths(all_points(reps, fixed, rotations),
                                hull.simplices, dual_edges)
    before = float(lengths.min() / np.median(lengths))

    triangles = hull.simplices

    def shortfall(candidate):
        # Against the CURRENT median, which is what grid_quality.py reports:
        # separating the short edges lengthens the typical one too (by 22% on
        # one draw), so a target fixed at the start would be missed as measured.
        lengths = dual_edge_lengths(all_points(candidate, fixed, rotations),
                                    triangles, dual_edges)
        target = min_fraction * SEPARATE_OVERSHOOT * np.median(lengths)
        return float(np.sum(np.clip(target - lengths, 0, None) ** 2))

    reps = descend(reps, fixed, rotations, shortfall, SEPARATE_STEP,
                   SEPARATE_ROUNDS, tolerance=0)
    lengths = dual_edge_lengths(all_points(reps, fixed, rotations),
                                triangles, dual_edges)
    return (reps, before, float(lengths.min()) / float(np.median(lengths)))


def descend(reps, fixed, rotations, objective, max_step, rounds, tolerance):
    """Gradient descent on objective(representatives), keeping the triangulation.

    The objective is expected to be computed on the starting triangulation, so
    its gradient is exact for small enough steps. Each candidate step is then
    judged on the hull it actually produces, and kept only if that hull is
    usable, has the same triangles (see separate_short_edges on why), and
    lowers the objective.

    @param tolerance: stop once a round improves the objective by less than
        this fraction of it; 0 to go on until no downhill step is left
    @returns the representatives, as a new array
    """
    wanted = triangle_set(usable_hull(all_points(reps, fixed, rotations)).simplices)
    current = objective(reps)
    step = max_step
    for _ in range(rounds):
        if current == 0:
            break
        # Central differences over every coordinate of every representative.
        gradient = np.zeros_like(reps)
        for index in np.ndindex(reps.shape):
            nudge = np.zeros_like(reps)
            nudge[index] = GRADIENT_H
            gradient[index] = (objective(reps + nudge)
                               - objective(reps - nudge)) / (2 * GRADIENT_H)
        # Only the part along the sphere moves a point.
        gradient -= np.sum(gradient * reps, axis=1, keepdims=True) * reps
        largest = np.max(np.linalg.norm(gradient, axis=1))
        if largest == 0:
            break
        direction = -gradient / largest

        improved = False
        while step > SEPARATE_MIN_STEP:
            candidate = reps + step * direction
            candidate /= np.linalg.norm(candidate, axis=1, keepdims=True)
            candidate_hull = usable_hull(all_points(candidate, fixed, rotations))
            if (candidate_hull is not None
                    and triangle_set(candidate_hull.simplices) == wanted):
                value = objective(candidate)
                if value < current:
                    gain = current - value
                    (reps, current) = (candidate, value)
                    step = min(step * 1.5, max_step)
                    improved = True
                    break
            step /= 2
        if not improved:
            break       # no downhill step left: as good as this draw gets
        if gain <= tolerance * (current + gain):
            break
    return reps


def face_cycles(points, triangles):
    """Each dual face as the ordered cycle of its corners, which are indices
    into `triangles` (the dual's vertices are the triangles' poles).

    Taken from polar_dual, so the order matches the solid it builds. That
    computes its own hull of the same points, so check that its vertices really
    are these triangles' poles before trusting the indices.
    """
    (vertices, faces) = polar_dual(points)
    if not np.allclose(vertices, poles_of(points, triangles)):
        raise RuntimeError("polar_dual's hull disagrees with this triangulation")
    return faces


def grouped_by_size(faces):
    """The faces as {sides: array of corner cycles}, so faces of one size can
    be measured together."""
    groups = {}
    for face in faces:
        groups.setdefault(len(face), []).append(face)
    return {sides: np.array(cycles) for (sides, cycles) in groups.items()}


def face_shape(poles, groups):
    """Per-face measurements of how far each face is from regular.

    @returns (irregularity, straightness, straightest corner in degrees, worst
        ratio of a face's longest side to its shortest). Irregularity is the
        mean, over every corner of every face, of the squared relative
        difference of its side from the face's mean side, plus the squared
        difference in radians of its angle from a regular polygon's,
        180 - 360/sides degrees. Straightness is the mean squared excess, in
        radians, of each corner over STRAIGHT_CORNER.
    """
    total = 0.0
    straightness = 0.0
    count = 0
    straightest = 0.0
    lopsided = 1.0
    cap = np.radians(STRAIGHT_CORNER)
    for (sides, cycles) in groups.items():
        corner = poles[cycles]                          # (faces, sides, 3)
        following = np.roll(corner, -1, axis=1)
        preceding = np.roll(corner, 1, axis=1)
        lengths = np.linalg.norm(following - corner, axis=2)
        total += np.sum((lengths / lengths.mean(axis=1, keepdims=True) - 1) ** 2)
        (a, b) = (preceding - corner, following - corner)
        cosines = np.sum(a * b, axis=2) / (np.linalg.norm(a, axis=2)
                                           * np.linalg.norm(b, axis=2))
        angles = np.arccos(np.clip(cosines, -1, 1))
        total += np.sum((angles - np.pi * (sides - 2) / sides) ** 2)
        straightness += np.sum(np.clip(angles - cap, 0, None) ** 2)
        count += cycles.size
        straightest = max(straightest, float(np.degrees(angles.max())))
        lopsided = max(lopsided, float(np.max(lengths.max(axis=1)
                                              / lengths.min(axis=1))))
    return (total / count, straightness / count, straightest, lopsided)


def regularize(reps, fixed, rotations, min_fraction):
    """Move the representatives to make every face as nearly regular as the
    census allows, keeping the symmetry, the flatness and the census exact.

    As near as the census ALLOWS, because three regular faces meeting at a
    corner must leave its angles summing to less than 360 degrees for the solid
    to be convex, and regular hexagons already sum to exactly 360. So a face of
    six or more sides can be near-regular only where smaller faces sit beside
    it; elsewhere it has to stay squeezed. This finds the compromise.

    Two things are held while it does, because regularizing works against both:
    no dual edge shorter than `min_fraction` of the median, and no two
    neighboring faces flatter than MIN_FACE_ANGLE. The second is cheap to state,
    because each face of a polar dual lies in the plane x.v = 1 and so has the
    point v itself as its normal: the angle between two neighboring faces IS the
    angle between their two points.

    @returns (representatives, shape before, shape after), each shape being
        face_shape's (irregularity, straightest corner, worst side ratio)
    """
    points = all_points(reps, fixed, rotations)
    triangles = usable_hull(points).simplices
    groups = grouped_by_size(face_cycles(points, triangles))
    dual_edges = dual_edges_of(triangles)
    neighbors = np.array(sorted({tuple(sorted((int(t[k]), int(t[(k + 1) % 3]))))
                                 for t in triangles for k in range(3)}))
    flattest = np.radians(MIN_FACE_ANGLE)

    def shape(candidate):
        return face_shape(poles_of(all_points(candidate, fixed, rotations),
                                   triangles), groups)

    def objective(candidate):
        pts = all_points(candidate, fixed, rotations)
        poles = poles_of(pts, triangles)
        (irregularity, straightness, _, _) = face_shape(poles, groups)
        lengths = np.linalg.norm(poles[dual_edges[:, 0]] - poles[dual_edges[:, 1]],
                                 axis=1)
        target = min_fraction * np.median(lengths)
        short = np.mean(np.clip(target - lengths, 0, None) ** 2) / target ** 2
        between = np.arccos(np.clip(np.sum(pts[neighbors[:, 0]]
                                           * pts[neighbors[:, 1]], axis=1), -1, 1))
        flat = np.mean(np.clip(flattest - between, 0, None) ** 2) / flattest ** 2
        return (irregularity + STRAIGHT_WEIGHT * straightness
                + CONSTRAINT_WEIGHT * (short + flat))

    before = shape(reps)
    reps = descend(reps, fixed, rotations, objective, REGULARIZE_STEP,
                   REGULARIZE_ROUNDS, REGULARIZE_TOLERANCE)
    return (reps, before, shape(reps))


def triangle_set(triangles):
    """A triangulation as a set, for comparing two regardless of order."""
    return {frozenset(int(v) for v in t) for t in triangles}


def census_line(faces):
    return ', '.join(f'{count}x{sides}' for (sides, count)
                     in sorted(grid_checks.face_census(faces).items()))


def parse_arguments(argv):
    options = {'orbits': 6, 'relax': 0.5, 'min_edge': MIN_EDGE_FRACTION,
               'regularize': False, 'seed': None, 'axes': [], 'id': None,
               'name': None}
    for argument in argv:
        if argument == '--regularize':
            options['regularize'] = True
        elif argument.startswith('--relax='):
            options['relax'] = float(argument.split('=', 1)[1])
        elif argument.startswith('--min-edge='):
            options['min_edge'] = float(argument.split('=', 1)[1])
        elif argument.startswith('--seed='):
            options['seed'] = int(argument.split('=', 1)[1])
        elif argument.startswith('--id='):
            options['id'] = argument.split('=', 1)[1]
        elif argument.startswith('--name='):
            options['name'] = argument.split('=', 1)[1]
        elif argument in ('--vertex-axes', '--face-axes', '--edge-axes'):
            options['axes'].append(argument[2:].split('-')[0])
        elif argument.isdigit():
            options['orbits'] = int(argument)
        else:
            raise SystemExit(f'Unrecognized argument {argument!r}.\n\n{__doc__}')
    if not 0 <= options['relax'] <= 1:
        raise SystemExit('--relax must be between 0 and 1.')
    if not 0 <= options['min_edge'] < 1:
        raise SystemExit('--min-edge must be at least 0 and less than 1.')
    if options['orbits'] < 1:
        raise SystemExit('orbits must be at least 1.')
    return options


def source_arguments(options):
    """The arguments that reproduce this file. The seed, relax and minimum edge
    are always spelled out, even at their defaults: they decide the geometry,
    and the line must go on reproducing the file after a default moves (see
    docs/json-format.md)."""
    arguments = [str(options['orbits']), f'--relax={options["relax"]:g}',
                 f'--min-edge={options["min_edge"]:g}', f'--seed={options["seed"]}']
    arguments += [f'--{axis}-axes' for axis in options['axes']]
    if options['regularize']:
        arguments.append('--regularize')
    if options['id']:
        arguments.append(f'--id={options["id"]}')
    if options['name']:
        arguments.append(f'--name={options["name"]}')
    return arguments


def main():
    options = parse_arguments(sys.argv[1:])
    if options['seed'] is None:
        options['seed'] = int(np.random.default_rng().integers(0, 2 ** 31))
    rng = np.random.default_rng(options['seed'])
    rotations = tetrahedral_rotations()
    axis_sets = {'vertex': VERTEX_AXES, 'face': FACE_AXES, 'edge': EDGE_AXES}
    chosen = [axis_sets[a] for a in options['axes']]
    fixed = np.vstack(chosen) if chosen else np.empty((0, 3))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = draw(options['orbits'], fixed, rotations, options['relax'], rng)
        if result is not None:
            break
        log(f'  draw {attempt} was degenerate; drawing again')
    else:
        raise SystemExit(f'No usable draw in {MAX_ATTEMPTS} attempts.')
    (reps, points, hull) = result

    if options['min_edge'] > 0:
        (reps, before, after) = separate_short_edges(reps, fixed, rotations,
                                                     options['min_edge'])
        points = all_points(reps, fixed, rotations)
        hull = ConvexHull(points)
        log(f'  shortest edge {before:.0%} of median before separating, '
            f'{after:.0%} after (target {options["min_edge"]:.0%})'
            + ('' if after >= options['min_edge']
               else ' -- SHORT OF THE TARGET; try another seed'))

    if options['regularize']:
        (reps, before, after) = regularize(reps, fixed, rotations,
                                           options['min_edge'])
        points = all_points(reps, fixed, rotations)
        hull = ConvexHull(points)
        log(f'  regularized: straightest corner {before[2]:.0f} -> '
            f'{after[2]:.0f} degrees, sides within a face up to '
            f'x{before[3]:.1f} -> x{after[3]:.1f}')

    (vertices, faces) = polar_dual(points)
    problems = (symmetry_problems(points, hull.simplices, rotations)
                + grid_checks.check_euler(vertices, faces)
                + grid_checks.check_flat_faces(vertices, faces, 1e-9)
                + grid_checks.check_closed_surface(faces)
                + grid_checks.check_outward_winding(vertices, faces)
                + grid_checks.check_vertex_degrees(faces, [3]))
    chiral = not has_mirror_symmetry(points)

    log(f'seed {options["seed"]}: {len(points)} points, {len(faces)} faces '
        f'({census_line(faces)}), {"chiral" if chiral else "achiral"}')
    if problems:
        for problem in problems:
            log(f'  FAILED: {problem}')
        raise SystemExit('Not written.')

    # Every argument that changes the solid is in the default id, so two
    # different solids can never share one. Underscores between the parts, or
    # the axis letters run into the relax value ("ve" + "r25" read as "ver25").
    # The minimum edge only when it isn't the default: an absent part then means
    # the default, so ids stay unique without growing for the common case.
    parts = [f'symT{options["orbits"]}']
    if options['axes']:
        parts.append(''.join(axis[0] for axis in options['axes']))
    parts.append(f'r{round(options["relax"] * 100)}')
    if options['min_edge'] != MIN_EDGE_FRACTION:
        parts.append(f'm{round(options["min_edge"] * 100)}')
    if options['regularize']:
        parts.append('reg')
    parts.append(f's{options["seed"]}')
    grid_id = options['id'] or '_'.join(parts)
    grid = {
        'gridId': grid_id,
        'gridName': options['name'] or f'Tetrahedral random solid {grid_id}',
        'categories': ['Miscellaneous', 'random'] + (['chiral'] if chiral else []),
        'source': json_format.source_line(source_arguments(options)),
        'vertices': [[round(float(c), 9) for c in v] for v in vertices],
        'faces': [[int(i) for i in face] for face in faces],
    }
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
