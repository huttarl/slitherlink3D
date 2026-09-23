#!/usr/bin/env python3
"""Generate a random solid with tetrahedral rotational symmetry, as grid JSON.

Usage:
    util/genSymmetric.py [orbits] [--relax=T] [--seed=N]
                         [--vertex-axes] [--face-axes] [--edge-axes]
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
  --edge-axes     by some rotations, so their faces are forced to have 3 or 6
                  sides (vertex and face axes) or an even number (edge axes).
  --relax         how evenly to spread the points, 0 to 1 (default 0.5). As in
                  genRandomPolyh.py, 0 leaves them where they fell and gives the
                  most varied face sizes, and 1 spreads them evenly.
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


def draw(orbits, fixed, rotations, relax_fraction, rng):
    """One attempt: the points, or None if their hull is degenerate."""
    reps = random_unit_vectors(orbits, rng)
    reps = partially_relaxed(reps, fixed, rotations, relax_fraction)
    points = all_points(reps, fixed, rotations)

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
    return (points, hull)


def census_line(faces):
    return ', '.join(f'{count}x{sides}' for (sides, count)
                     in sorted(grid_checks.face_census(faces).items()))


def parse_arguments(argv):
    options = {'orbits': 6, 'relax': 0.5, 'seed': None, 'axes': [],
               'id': None, 'name': None}
    for argument in argv:
        if argument.startswith('--relax='):
            options['relax'] = float(argument.split('=', 1)[1])
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
    if options['orbits'] < 1:
        raise SystemExit('orbits must be at least 1.')
    return options


def source_arguments(options):
    """The arguments that reproduce this file, with the seed always spelled out
    -- a file made from a random seed must still name the seed it used."""
    arguments = [str(options['orbits']), f'--relax={options["relax"]:g}',
                 f'--seed={options["seed"]}']
    arguments += [f'--{axis}-axes' for axis in options['axes']]
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
    (points, hull) = result

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
    parts = [f'symT{options["orbits"]}']
    if options['axes']:
        parts.append(''.join(axis[0] for axis in options['axes']))
    parts += [f'r{round(options["relax"] * 100)}', f's{options["seed"]}']
    grid_id = options['id'] or '_'.join(parts)
    grid = {
        'gridId': grid_id,
        'gridName': options['name'] or f'Tetrahedral random solid {grid_id}',
        'categories': ['Miscellaneous'] + (['chiral'] if chiral else []),
        'source': json_format.source_line(source_arguments(options)),
        'vertices': [[round(float(c), 9) for c in v] for v in vertices],
        'faces': [[int(i) for i in face] for face in faces],
    }
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
