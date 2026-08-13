#!/usr/bin/env python3
"""Generate a prolate viral capsid: an elongated triangulated cage with a portal.

Usage:
    util/genCapsid.py                       # the default capsid, to stdout
    util/genCapsid.py --belts=1 --whole     # shorter, and unpierced
    util/genCapsid.py --out=data/capsid.json

The shape a bacteriophage's head is: twelve five-fold vertices with the rest
six-fold, stretched along one of the five-fold axes, and one pentamer missing where
the DNA goes in. See the capsid shapes at en.wikipedia.org/wiki/Capsid.

It is the TRIANGULATED side of the fullerene construction -- the solid genFullerene
computes on the way to a cage and then discards, since the cage is its polar dual.
Which is the reason this exists as its own script rather than as a longer geodesic:
a capsid's triangulation is not a geodesic polyhedron. Those come from subdividing a
Platonic solid and have an (m,n) to be named by; this one is elongated, so it has no
such name, and it does not look like one either -- gd20 and gd21 are round.

TWO THINGS FALL OUT NICELY, both worth knowing:

Triangles cannot bow. The fullerene cages had to choose between regular faces and
flat ones -- a curved cage cannot have both, so C110 ships bowed by 2% -- but a
triangle is planar whatever is done to it. So regularizing here costs nothing at
all: the faces come out within about a per cent of equilateral AND flat to
floating-point noise.

The portal is one vertex. Deleting a five-fold vertex and the five triangles around
it leaves a clean pentagonal rim, which is exactly what a portal is in the biology --
one pentamer replaced by the machinery that packs the DNA. Nothing has to be cut, and
the rim is planar for free, being five points that were around one vertex.

The result is therefore NOT CLOSED, and says `"closed": false` (see
docs/json-format.md). Euler's formula gives 1: a sphere with one hole is a disk.
Unlike the nanotube's two rims, one hole is nowhere narrow, so the puzzle generator
has none of the trouble a thin tube gives it.

Needs numpy and scipy, through the modules it borrows from.
"""
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

# Our local modules, so that nothing here is new machinery: the ring placement comes
# from the fullerene generator, the polar dual and its outward orientation from the
# Goldberg one, and both shaping passes from the shared shape module.
import grid_checks
import grid_topology
import json_format
import polyhedron_shape
from genFullerene import ring_points
from genGoldberg import orient_outward, polar_dual

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

USAGE = __doc__[__doc__.index('Usage:'):__doc__.index('The shape')].rstrip()

# How many belts of hexagons the underlying cage has, which is what makes the capsid
# prolate rather than round. Five gives 110 triangles and a solid twice as long as it
# is wide -- plainly a phage head, where one belt is only 1.3 and reads as a slightly
# squashed geodesic.
DEFAULT_BELTS = 5

# The capsid has 5-fold symmetry, being built on the same rings as a capped (5,5)
# tube. That is also why the portal comes out pentagonal.
AROUND = 5


def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def triangulation(belts):
    """The prolate triangulation, as (vertices, faces), before any portal.

    Same three stages as a fullerene, and for the same reasons: the rings fix the
    STRUCTURE, canonicalizing gives the shaping a well-behaved start, and
    regularizing gives the real proportions. No repulsion -- it spreads points evenly
    over a sphere, which would roll the prolate shape back into a ball (see the note
    in genFullerene).
    """
    offsets = [0.5 * (i % 2) for i in range(6 + belts)]
    points = ring_points(fold=AROUND, offsets=offsets, poles=True)
    (_, cage_faces) = polar_dual(points)
    (points, rounds, shift) = polyhedron_shape.canonicalize(
        points, ConvexHull(points).simplices, cage_faces)
    # Reported rather than warned about unless it is a long way off: this pass only
    # has to hand regularize something convex and roughly even, and regularize sets
    # the final shape from there. Same reasoning as in genFullerene.
    if shift < polyhedron_shape.SETTLED:
        log(f'Canonical after {rounds} rounds (last move {shift:.1e})')
    elif shift < 1e-3:
        log(f'Canonical enough after {rounds} rounds (last move {shift:.1e}, '
            'still easing -- regularize sets the shape from here)')
    else:
        log(f'Warning: canonical form still moving {shift:.1e} after {rounds} '
            'rounds, which is enough to see; the capsid may be malformed')
    # Wound outward one triangle at a time: ConvexHull gives no promise about which
    # way round its simplices come.
    faces = [orient_outward(points, list(simplex))
             for simplex in ConvexHull(points).simplices]
    return (polyhedron_shape.regularize(points, faces), faces)


def pierce(vertices, faces):
    """Remove a five-fold vertex and the triangles at it, leaving a portal.

    The topmost vertex, which on this solid is one of the twelve five-fold ones: the
    rings put a point on the axis at each pole. Taking it and its five triangles
    leaves a pentagonal hole centred on the axis.

    @returns (vertices, faces, removed) with the vertices renumbered
    """
    pole = max(range(len(vertices)), key=lambda v: vertices[v][1])
    kept = [face for face in faces if pole not in face]
    used = sorted({v for face in kept for v in face})
    renumbered = {v: i for (i, v) in enumerate(used)}
    return ([vertices[v] for v in used],
            [[renumbered[v] for v in face] for face in kept],
            len(faces) - len(kept))


def upright(vertices):
    """Stand the capsid up: its axis on y, which is up on screen.

    The rings are built about z and the app's camera sits out along z (see
    CAMERA_DISTANCE in js/constants.js), so a solid left as built is seen end on --
    and end on, a prolate capsid is a circle. A rotation about x rather than a swap of
    axes, since swapping two would mirror it and reverse every face's winding.
    """
    return np.column_stack((vertices[:, 0], vertices[:, 2], -vertices[:, 1]))


def check(vertices, faces, belts, pierced):
    """Verify the capsid against what it must be, and describe it.

    The counts come from the cage it is the triangulation of: a capped (5,5) tube of
    b belts has 60 + 10b atoms and 32 + 5b faces, and dualizing swaps those. A portal
    then takes one vertex, five faces and five edges. Derived rather than tabulated,
    so a wrong ring pattern cannot pass.

    @returns a one-line description, or exits if anything is off
    """
    cage_atoms = 60 + 10 * belts
    cage_faces = 32 + 5 * belts
    expected = {'vertices': cage_faces, 'faces': cage_atoms,
                'edges': 3 * cage_atoms // 2}
    wanted_euler = 2
    if pierced:
        expected = {'vertices': cage_faces - 1, 'faces': cage_atoms - 5,
                    'edges': 3 * cage_atoms // 2 - 5}
        wanted_euler = 1

    problems = []
    census = Counter(len(face) for face in faces)
    if set(census) != {3}:
        problems.append(f'only triangles expected, got {dict(sorted(census.items()))}')
    edges = grid_topology.edges_of([list(face) for face in faces])
    for (what, count) in (('vertices', len(vertices)), ('faces', len(faces)),
                          ('edges', len(edges))):
        if count != expected[what]:
            problems.append(f'{expected[what]} {what} expected, got {count}')

    euler = len(vertices) - len(edges) + len(faces)
    if euler != wanted_euler:
        problems.append(f'Euler characteristic {euler}, expected {wanted_euler}'
                        + (' for a surface with one hole' if pierced else ''))

    rim = grid_topology.boundary_edges([list(face) for face in faces])
    if len(rim) != (AROUND if pierced else 0):
        problems.append(f'{len(rim)} rim edge(s), expected '
                        f'{AROUND if pierced else 0}')

    # edge_degrees, not vertex_degrees: on a pierced capsid a rim vertex has one face
    # fewer than it has edges, and it is the edges a loop cares about.
    degrees = grid_topology.edge_degrees([list(face) for face in faces])
    stray = sorted({degree for degree in degrees.values()} - {5, 6})
    if stray:
        problems.append(f'vertices of degree {stray}; a capsid wants 5 or 6')
    # Twelve five-fold vertices is what makes it a closed cage of this family. The
    # portal removes one of them and drops its five neighbours from 6 to 5, so the
    # count goes 12 -> 16 -- checked, since getting it wrong would mean the hole was
    # somewhere other than a five-fold vertex.
    fivefold = sum(1 for degree in degrees.values() if degree == 5)
    wanted_fivefold = 16 if pierced else 12
    if fivefold != wanted_fivefold:
        problems.append(f'{wanted_fivefold} five-fold vertices expected, '
                        f'got {fivefold}')

    problems += grid_checks.check_flat_faces(vertices, faces, 1e-9)
    problems += grid_checks.check_outward_winding(vertices, faces)
    if not pierced:
        problems += grid_checks.check_closed_surface(faces)

    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)

    lengths = [grid_checks.distance(vertices[a], vertices[b]) for (a, b) in edges]
    heights = [v[1] for v in vertices]
    width = 2 * max(math.hypot(v[0], v[2]) for v in vertices)
    return (f'{len(faces)} triangles, {len(vertices)} vertices, {len(edges)} edges; '
            f'edges {min(lengths):.4f} to {max(lengths):.4f} '
            f'(ratio {max(lengths) / min(lengths):.3f}); '
            f'length/width {(max(heights) - min(heights)) / width:.3f}; '
            f'faces flat to {max(grid_checks.face_bow(grid_checks.corners_of(vertices, list(f))) for f in faces):.1e}'
            + (f'; portal of {AROUND} edges' if pierced else '; closed'))


def capsid(belts, pierced):
    """A capsid as (vertices, faces), scaled to a circumradius of 1."""
    (vertices, faces) = triangulation(belts)
    vertices = upright(np.asarray(vertices)).tolist()
    if pierced:
        (vertices, faces, removed) = pierce(vertices, faces)
        log(f'Portal: removed the top vertex and {removed} triangles at it')
    # Scaled AFTER piercing, so the result really is at circumradius 1 like every
    # other grid: the vertex the portal takes is the topmost one, so scaling first
    # would leave the pierced capsid a little under size.
    points = np.asarray(vertices)
    return ((points / np.linalg.norm(points, axis=1).max()).tolist(), faces)


def build(belts, pierced):
    """One grid, as the dict that goes into the JSON file."""
    (vertices, faces) = capsid(belts, pierced)
    rounded = [[round(float(c), 6) for c in v] for v in vertices]
    log(check(rounded, faces, belts, pierced))

    grid = {
        'gridId': 'capsid',
        'gridName': ('Prolate capsid with DNA portal' if pierced
                     else 'Prolate capsid'),
        # No 'geodesic': that word is for the round triangulations with an (m,n),
        # which this deliberately is not -- see the docstring.
        'categories': ['Miscellaneous'],
    }
    if pierced:
        grid['closed'] = False
    # Both spelled out even when defaulted, since each decides the geometry and argv
    # would say nothing about a default. See json_format.source_line.
    grid['source'] = json_format.source_line(
        [f'--belts={belts}'] + ([] if pierced else ['--whole']))
    grid['vertices'] = rounded
    grid['faces'] = faces
    return grid


def main():
    belts = DEFAULT_BELTS
    pierced = True
    out = None
    for option in sys.argv[1:]:
        if option == '--whole':
            pierced = False
        elif option.startswith('--belts='):
            belts = int(option.split('=', 1)[1])
        elif option.startswith('--out='):
            out = Path(option.split('=', 1)[1])
        else:
            log(f'Error: unknown option {option}.\n{USAGE}')
            sys.exit(1)
    if belts < 1:
        log(f'Error: --belts={belts} leaves nothing to elongate; ask for 1 or more.')
        sys.exit(1)

    grid = build(belts, pierced)
    if out:
        with open(out, 'w') as handle:
            json_format.write_json(grid, handle)
        log(f'Wrote {out}')
    else:
        json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
