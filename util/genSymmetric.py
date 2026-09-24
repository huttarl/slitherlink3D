#!/usr/bin/env python3
"""Generate a random solid with tetrahedral or octahedral rotational symmetry,
as grid JSON.

Usage:
    util/genSymmetric.py [orbits] [--group=G] [--relax=T] [--min-edge=F]
                         [--regularize] [--seed=N] [--vertex-axes]
                         [--face-axes] [--edge-axes] [--id=ID] [--name=NAME]

Output goes to stdout; progress, the census and the self-check go to stderr.

How it works: a few random points are chosen, and the rotations of a symmetry
group carry each one to as many places: 12 for the tetrahedral group T, 24 for
the octahedral group O. Each such set is an ORBIT. The convex hull of all the
points has the same symmetry, and its polar dual is the solid: one face per
point, every face exactly flat, and as many faces at each vertex as its hull
facet has corners.

Under T every facet is a triangle, so three faces meet at every vertex. Under O
the four images of a point around each 4-fold axis are always coplanar, so
unless --vertex-axes puts points on those axes, the hull has a square facet
around each of them, and the solid has six vertices where four faces meet.

What the options mean for the solid:
  orbits          how many random orbits (default 6), 12 or 24 faces each.
                  Every face in an orbit is congruent to the others, so each
                  orbit contributes 12 or 24 faces of one size.
  --group         tetrahedral (the default) or octahedral.
  --vertex-axes   also put a point on each of the solid's vertex axes, or its
  --face-axes     face axes, or its edge axes: of the tetrahedron (4, 4 and 6
  --edge-axes     points) or of the octahedron (6, 8 and 12). These points are
                  fixed by some rotations, so the number of sides of their
                  faces is forced to be a multiple of the axis's fold. Under T
                  that is 3 for vertex and face axes (3, 6, 9...) and 2 for
                  edge axes (4, 6, 8...); under O it is 4, 3 and 2.
                  With a value, as --face-axes=0.95, those faces' planes are
                  moved to that distance from the center once everything else
                  is done: below 1 slices them deeper, making them wider and
                  trimming their neighbors, and no other face moves. See
                  move_axis_faces.
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

Euler's formula constrains the census: summing (6 - sides) over the faces
gives 12, plus 2 for each vertex where four faces meet. With 12 congruent faces
per orbit under T, and 24 under O with its six such vertices, the orbits' own
(6 - sides) must sum to 1 either way, less whatever the axis points take. See
docs/generating-grids.md.

The solid is checked before it is written: the symmetry of the hull's facets,
Euler, flat faces, a closed and outward-wound surface, and the vertex degrees.
Coplanar hull points that the symmetry forces are merged into one facet (see
hull_facets). A draw with points that are only NEARLY coplanar is rejected and
redrawn, since its dual would have nearly coincident vertices.

Requires numpy and scipy.
"""
import sys

import numpy as np
from scipy.spatial import ConvexHull

import grid_checks
import json_format
from genGoldberg import cycle_around
from genUniformPolyh import merge_coplanar_faces

# How many fresh draws to try before giving up on a degenerate configuration.
MAX_ATTEMPTS = 50

# Two points closer than this are treated as the same point.
SAME_POINT = 1e-6

# Hull triangles in one plane to within this are one facet. Symmetry-forced
# coplanarity is exact up to rounding, near 1e-16; this is far above that and
# far below the near-coplanarity that usable_hull rejects.
COPLANAR = 1e-9

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


def octahedral_rotations():
    """The 24 rotations of the octahedral group O, as exact 3x3 matrices: the
    signed permutation matrices of determinant +1.

    T is half of O, so O is T's 12 followed by each of them after a quarter
    turn about z. T's come first and in their own order, so that a tetrahedral
    draw's arithmetic is untouched by O's existence.
    """
    quarter = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    tetrahedral = tetrahedral_rotations()
    return tetrahedral + [quarter @ r for r in tetrahedral]


# The points on the tetrahedron's symmetry axes, by which feature the axis runs
# through. Each set is one orbit of T.
VERTEX_AXES = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]) / 3 ** 0.5
FACE_AXES = -VERTEX_AXES
EDGE_AXES = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0],
                      [0, 0, 1], [0, 0, -1]], dtype=float)

# The same for the octahedron, each set one orbit of O: its vertex axes are
# the 4-fold ones, its face axes the 3-fold, and its edge axes the 2-fold.
OCTAHEDRON_VERTEX_AXES = EDGE_AXES
OCTAHEDRON_FACE_AXES = np.vstack([VERTEX_AXES, FACE_AXES])
OCTAHEDRON_EDGE_AXES = np.array([[a, b, 0] for a in (1, -1) for b in (1, -1)]
                                + [[a, 0, b] for a in (1, -1) for b in (1, -1)]
                                + [[0, a, b] for a in (1, -1) for b in (1, -1)],
                                dtype=float) / 2 ** 0.5

# What each --group means: its rotations, the points on each kind of axis, the
# vertex degrees its solids can have (see the module docstring on the squares),
# and the letter and word that name its solids.
GROUPS = {
    'tetrahedral': {
        'rotations': tetrahedral_rotations,
        'axes': {'vertex': VERTEX_AXES, 'face': FACE_AXES, 'edge': EDGE_AXES},
        'degrees': [3], 'letter': 'T', 'name': 'Tetrahedral'},
    'octahedral': {
        'rotations': octahedral_rotations,
        'axes': {'vertex': OCTAHEDRON_VERTEX_AXES, 'face': OCTAHEDRON_FACE_AXES,
                 'edge': OCTAHEDRON_EDGE_AXES},
        'degrees': [3, 4], 'letter': 'O', 'name': 'Octahedral'},
}


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


def symmetry_problems(points, facets, rotations):
    """Check that every rotation carries the hull's facets onto themselves.

    The dual is computed from the facets alone, so symmetric facets mean a
    symmetric solid.
    """
    wanted = facet_set(facets)
    for (n, r) in enumerate(rotations):
        # Where each point's image lands, all at once: this runs on every step
        # of the descent.
        gaps = np.linalg.norm((points @ r.T)[:, None] - points[None, :], axis=2)
        mapping = gaps.argmin(axis=1)
        if np.any(gaps[np.arange(len(points)), mapping] >= SAME_POINT):
            return [f'rotation {n} carries a point to where there is none']
        image = {frozenset(int(mapping[v]) for v in f) for f in wanted}
        if image != wanted:
            return [f'rotation {n} does not carry the facets onto themselves']
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


def hull_facets(points, hull):
    """The hull's facets, as tuples of point indices: its triangles, with any
    that lie in one plane merged into one polygon.

    scipy's hull comes back triangulated, splitting a flat polygon into
    triangles arbitrarily. Each facet's pole is one vertex of the dual, so an
    unmerged square would give the dual two coincident vertices where there
    should be one vertex with four faces.

    A triangle keeps its corners in the hull's order, and the facets come in
    the order of their first triangles, so a hull with nothing to merge gives
    exactly the vertices genGoldberg.polar_dual does. A merged facet's corners
    go in order around it.
    """
    # How far each triangle's neighbors' corners are from its plane: the two
    # corners they share are on it, so the largest is the third.
    homogeneous = np.hstack([points, np.ones((len(points), 1))])
    across = homogeneous[hull.simplices[hull.neighbors]]       # (F, 3, 3, 4)
    heights = np.abs(np.einsum('fd,fkvd->fkv', hull.equations, across)).max(axis=2)

    group = list(range(len(hull.simplices)))

    def root(t):
        while group[t] != t:
            t = group[t]
        return t

    for (t, k) in np.argwhere(heights < COPLANAR):
        group[root(int(hull.neighbors[t, k]))] = root(int(t))

    members = {}
    for t in range(len(hull.simplices)):
        members.setdefault(root(t), []).append(t)
    facets = []
    for triangles in sorted(members.values(), key=min):
        if len(triangles) == 1:
            facets.append(tuple(int(v) for v in hull.simplices[triangles[0]]))
            continue
        corners = sorted({int(v) for t in triangles for v in hull.simplices[t]})
        # Around the centroid, which a convex polygon always contains.
        offsets = points[corners] - points[corners].mean(axis=0)
        facets.append(tuple(cycle_around(hull.equations[triangles[0]][:3],
                                         offsets, corners)))
    return facets


def usable_hull(points, rotations):
    """The facets of the points' hull (see hull_facets), or None if it would
    make a bad solid."""
    # Distinct points: a representative too near an axis gives images that
    # nearly coincide.
    gaps = np.linalg.norm(points[:, None] - points[None, :], axis=2)
    np.fill_diagonal(gaps, np.inf)
    if gaps.min() < 1e-3:
        return None

    hull = ConvexHull(points)
    if len(hull.vertices) != len(points):
        return None       # a point inside the hull would get no face
    facets = hull_facets(points, hull)
    # merge_coplanar_faces rounds the planes, so it also merges triangles that
    # are only NEARLY coplanar, whose poles, the dual's vertices, would nearly
    # coincide. A facet it merges that hull_facets doesn't is one of those.
    if len(merge_coplanar_faces(points, hull)) != len(facets):
        return None
    # A merge that the symmetry forces is carried onto itself by every
    # rotation; one that the tolerance made by accident would not be.
    if (len(facets) != len(hull.simplices)
            and symmetry_problems(points, facets, rotations)):
        return None
    return facets


def facets_of(points):
    """The facets of the points' hull, for points already known to be usable."""
    return hull_facets(points, ConvexHull(points))


def draw(orbits, fixed, rotations, relax_fraction, rng):
    """One attempt: (representatives, points, facets), or None if the hull is
    unusable."""
    reps = random_unit_vectors(orbits, rng)
    reps = partially_relaxed(reps, fixed, rotations, relax_fraction)
    points = all_points(reps, fixed, rotations)
    facets = usable_hull(points, rotations)
    return None if facets is None else (reps, points, facets)


def facet_dual(points, facets):
    """The polar dual of the hull with these facets, about the unit sphere.

    genGoldberg.polar_dual builds it from the hull's raw triangles, which would
    give a merged facet one pole per triangle. This is the same construction
    over the merged facets: each facet's pole is solved from three of its
    corners, the rest lying in the same plane.

    @returns (vertices, faces) -- one vertex per facet, one face per point,
        each face flat and wound counterclockwise seen from outside
    """
    poles = np.array([np.linalg.solve(points[list(facet[:3])], np.ones(3))
                      for facet in facets])
    around = [[] for _ in range(len(points))]
    for (f, facet) in enumerate(facets):
        for vertex in facet:
            around[vertex].append(f)
    faces = [cycle_around(points[v], poles[corners], corners)
             for (v, corners) in enumerate(around)]
    return (poles, faces)


def facet_edges(facet):
    """A facet's sides, as sorted pairs of point indices: its corners are in
    order around it, so each corner and the next."""
    return [tuple(sorted((facet[k], facet[(k + 1) % len(facet)])))
            for k in range(len(facet))]


def dual_edges_of(facets):
    """The dual's edges, as pairs of facet indices: one pair per primal edge,
    the two facets that share it."""
    sharing = {}
    for (f, facet) in enumerate(facets):
        for edge in facet_edges(facet):
            sharing.setdefault(edge, []).append(f)
    return np.array(list(sharing.values()))


def pole_triples(facets):
    """Three corners of each facet, from which poles_of solves its pole."""
    return np.array([facet[:3] for facet in facets])


def poles_of(points, triples):
    """The dual's vertices: each facet's pole, the point p with p.a = p.b =
    p.c = 1 for three of its corners (pole_triples) -- what facet_dual
    computes."""
    corners = points[triples]
    return np.linalg.solve(corners, np.ones((len(corners), 3, 1)))[..., 0]


def dual_edge_lengths(points, triples, dual_edges):
    """How long each dual edge is: the distance between the poles of its two
    facets, which is where facet_dual puts the dual's vertices."""
    poles = poles_of(points, triples)
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

    Gradient descent on the total squared shortfall, with the hull's facets
    held FIXED. A nearly coplanar pair of triangles can also be resolved by
    flipping to the other diagonal, but a flip changes vertex degrees and so
    face sizes: left free to flip, this turned two orbits of squares and
    octagons into hexagons, spending the variety the draw produced. So a step is
    kept only if the hull it actually produces is usable, has the same
    facets, and has less shortfall.

    @returns (representatives, shortest before, shortest after), the shortest
        dual edge given as a fraction of the median
    """
    facets = usable_hull(all_points(reps, fixed, rotations), rotations)
    dual_edges = dual_edges_of(facets)
    triples = pole_triples(facets)
    lengths = dual_edge_lengths(all_points(reps, fixed, rotations),
                                triples, dual_edges)
    before = float(lengths.min() / np.median(lengths))

    def shortfall(candidate):
        # Against the CURRENT median, which is what grid_quality.py reports:
        # separating the short edges lengthens the typical one too (by 22% on
        # one draw), so a target fixed at the start would be missed as measured.
        lengths = dual_edge_lengths(all_points(candidate, fixed, rotations),
                                    triples, dual_edges)
        target = min_fraction * SEPARATE_OVERSHOOT * np.median(lengths)
        return float(np.sum(np.clip(target - lengths, 0, None) ** 2))

    reps = descend(reps, fixed, rotations, shortfall, SEPARATE_STEP,
                   SEPARATE_ROUNDS, tolerance=0)
    lengths = dual_edge_lengths(all_points(reps, fixed, rotations),
                                triples, dual_edges)
    return (reps, before, float(lengths.min()) / float(np.median(lengths)))


def descend(reps, fixed, rotations, objective, max_step, rounds, tolerance):
    """Gradient descent on objective(representatives), keeping the facets.

    The objective is expected to be computed on the starting facets, so its
    gradient is exact for small enough steps. Each candidate step is then
    judged on the hull it actually produces, and kept only if that hull is
    usable, has the same facets (see separate_short_edges on why), and lowers
    the objective.

    @param tolerance: stop once a round improves the objective by less than
        this fraction of it; 0 to go on until no downhill step is left
    @returns the representatives, as a new array
    """
    wanted = facet_set(usable_hull(all_points(reps, fixed, rotations), rotations))
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
            candidate_facets = usable_hull(all_points(candidate, fixed, rotations),
                                           rotations)
            if (candidate_facets is not None
                    and facet_set(candidate_facets) == wanted):
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


def face_cycles(points, facets):
    """Each dual face as the ordered cycle of its corners, which are indices
    into `facets` (the dual's vertices are the facets' poles).

    Taken from facet_dual, so the order matches the solid it builds.
    """
    return facet_dual(points, facets)[1]


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

    As near as the census ALLOWS, because the regular faces meeting at a
    corner must leave its angles summing to less than 360 degrees for the solid
    to be convex, and three regular hexagons already sum to exactly 360. So a
    face of
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
    facets = usable_hull(points, rotations)
    groups = grouped_by_size(face_cycles(points, facets))
    dual_edges = dual_edges_of(facets)
    triples = pole_triples(facets)
    # Faces that share an edge: the points at the ends of a facet's side.
    neighbors = np.array(sorted({edge for facet in facets
                                 for edge in facet_edges(facet)}))
    flattest = np.radians(MIN_FACE_ANGLE)

    def shape(candidate):
        return face_shape(poles_of(all_points(candidate, fixed, rotations),
                                   triples), groups)

    def objective(candidate):
        pts = all_points(candidate, fixed, rotations)
        poles = poles_of(pts, triples)
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


def move_axis_faces(reps, axis_points, distances, rotations):
    """Move the axis points' face planes to the given distances from the center.

    A face lies in the plane x.v = 1 of its point v, at distance 1/|v| from the
    center, so scaling an axis point by 1/distance moves its face's plane and
    no other. The point stays on its axis, so the symmetry stays exact, and the
    dual is still exactly flat. Done last, after regularizing, since moving the
    points earlier would let everything else move to suit.

    @param axis_points: [(axis name, its points)], in the order the fixed
        points are stacked
    @param distances: {axis name: distance}, for the axes to move
    @returns (the moved fixed points, their hull's facets), or None if the move
        changes which faces meet -- a neighbor's edge shrunk to nothing
    """
    before = usable_hull(all_points(reps, np.vstack([p for (_, p) in axis_points]),
                                    rotations), rotations)
    moved = np.vstack([points / distances.get(name, 1.0)
                       for (name, points) in axis_points])
    after = usable_hull(all_points(reps, moved, rotations), rotations)
    if after is None or facet_set(after) != facet_set(before):
        return None
    return (moved, after)


def facet_set(facets):
    """A hull's facets as a set, for comparing two regardless of order."""
    return {frozenset(int(v) for v in f) for f in facets}


def census_line(faces):
    return ', '.join(f'{count}x{sides}' for (sides, count)
                     in sorted(grid_checks.face_census(faces).items()))


def parse_arguments(argv):
    options = {'orbits': 6, 'group': 'tetrahedral', 'relax': 0.5,
               'min_edge': MIN_EDGE_FRACTION, 'regularize': False, 'seed': None,
               'axes': [], 'axis_distances': {}, 'id': None, 'name': None}
    for argument in argv:
        if argument == '--regularize':
            options['regularize'] = True
        elif argument.startswith('--group='):
            options['group'] = argument.split('=', 1)[1]
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
        elif argument.partition('=')[0] in ('--vertex-axes', '--face-axes',
                                            '--edge-axes'):
            (flag, _, value) = argument.partition('=')
            axis = flag[2:].split('-')[0]
            options['axes'].append(axis)
            if value:
                options['axis_distances'][axis] = float(value)
                if options['axis_distances'][axis] <= 0:
                    raise SystemExit(f'{flag} needs a distance above 0.')
        elif argument.isdigit():
            options['orbits'] = int(argument)
        else:
            raise SystemExit(f'Unrecognized argument {argument!r}.\n\n{__doc__}')
    if options['group'] not in GROUPS:
        raise SystemExit(f'--group must be one of {", ".join(GROUPS)}.')
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
    docs/json-format.md). The group only when it isn't tetrahedral, so that files
    written before --group existed still regenerate byte for byte, source line
    included."""
    arguments = [str(options['orbits'])]
    if options['group'] != 'tetrahedral':
        arguments.append(f'--group={options["group"]}')
    arguments += [f'--relax={options["relax"]:g}',
                  f'--min-edge={options["min_edge"]:g}', f'--seed={options["seed"]}']
    for axis in options['axes']:
        distance = options['axis_distances'].get(axis)
        arguments.append(f'--{axis}-axes' + ('' if distance is None
                                             else f'={distance:g}'))
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
    group = GROUPS[options['group']]
    rotations = group['rotations']()
    chosen = [group['axes'][a] for a in options['axes']]
    fixed = np.vstack(chosen) if chosen else np.empty((0, 3))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = draw(options['orbits'], fixed, rotations, options['relax'], rng)
        if result is not None:
            break
        log(f'  draw {attempt} was degenerate; drawing again')
    else:
        raise SystemExit(f'No usable draw in {MAX_ATTEMPTS} attempts.')
    (reps, points, facets) = result

    if options['min_edge'] > 0:
        (reps, before, after) = separate_short_edges(reps, fixed, rotations,
                                                     options['min_edge'])
        points = all_points(reps, fixed, rotations)
        facets = facets_of(points)
        log(f'  shortest edge {before:.0%} of median before separating, '
            f'{after:.0%} after (target {options["min_edge"]:.0%})'
            + ('' if after >= options['min_edge']
               else ' -- SHORT OF THE TARGET; try another seed'))

    if options['regularize']:
        (reps, before, after) = regularize(reps, fixed, rotations,
                                           options['min_edge'])
        points = all_points(reps, fixed, rotations)
        facets = facets_of(points)
        log(f'  regularized: straightest corner {before[2]:.0f} -> '
            f'{after[2]:.0f} degrees, sides within a face up to '
            f'x{before[3]:.1f} -> x{after[3]:.1f}')

    if options['axis_distances']:
        result = move_axis_faces(reps, [(a, group['axes'][a]) for a in options['axes']],
                                 options['axis_distances'], rotations)
        if result is None:
            raise SystemExit('Moving the axis faces that far changes which faces '
                             'meet; try a distance nearer 1. Not written.')
        (fixed, facets) = result
        points = all_points(reps, fixed, rotations)
        log('  moved the axis faces to distance '
            + ', '.join(f'{d:g} ({axis})'
                        for (axis, d) in options['axis_distances'].items()))

    (vertices, faces) = facet_dual(points, facets)
    problems = (symmetry_problems(points, facets, rotations)
                + grid_checks.check_euler(vertices, faces)
                + grid_checks.check_flat_faces(vertices, faces, 1e-9)
                + grid_checks.check_closed_surface(faces)
                + grid_checks.check_outward_winding(vertices, faces)
                + grid_checks.check_vertex_degrees(faces, group['degrees']))
    chiral = not has_mirror_symmetry(points)

    degrees = grid_checks.face_census(facets)
    log(f'seed {options["seed"]}: {len(points)} points, {len(faces)} faces '
        f'({census_line(faces)}), vertex degrees '
        + ', '.join(f'{count}x{degree}' for (degree, count) in sorted(degrees.items()))
        + f', {"chiral" if chiral else "achiral"}')
    if problems:
        for problem in problems:
            log(f'  FAILED: {problem}')
        raise SystemExit('Not written.')

    # Every argument that changes the solid is in the default id, so two
    # different solids can never share one. Underscores between the parts, or
    # the axis letters run into the relax value ("ve" + "r25" read as "ver25").
    # The minimum edge only when it isn't the default: an absent part then means
    # the default, so ids stay unique without growing for the common case.
    parts = [f'sym{group["letter"]}{options["orbits"]}']
    if options['axes']:
        # A moved axis carries its distance, as "f95" for --face-axes=0.95.
        parts.append(''.join(
            axis[0] + (f'{round(options["axis_distances"][axis] * 100)}'
                       if axis in options['axis_distances'] else '')
            for axis in options['axes']))
    parts.append(f'r{round(options["relax"] * 100)}')
    if options['min_edge'] != MIN_EDGE_FRACTION:
        parts.append(f'm{round(options["min_edge"] * 100)}')
    if options['regularize']:
        parts.append('reg')
    parts.append(f's{options["seed"]}')
    grid_id = options['id'] or '_'.join(parts)
    grid = {
        'gridId': grid_id,
        'gridName': options['name'] or f'{group["name"]} random solid {grid_id}',
        'categories': ['Miscellaneous', 'random'] + (['chiral'] if chiral else []),
        'source': json_format.source_line(source_arguments(options)),
        'vertices': [[round(float(c), 9) for c in v] for v in vertices],
        'faces': [[int(i) for i in face] for face in faces],
    }
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
