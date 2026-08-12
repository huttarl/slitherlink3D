#!/usr/bin/env python3
"""Generate a fullerene: a cage of 12 pentagons and hexagons, three at each corner.

Usage:
    util/genFullerene.py C70                    # one recipe, to stdout
    util/genFullerene.py --all                  # every recipe, into data/
    util/genFullerene.py --atoms=32 --seed=0    # any Cn, whichever isomer settles

A fullerene Cn is n atoms each bonded to three others, on a cage of 12 pentagons
and n/2 - 10 hexagons. C60 is the truncated icosahedron, and every fullerene with
icosahedral symmetry is a Goldberg polyhedron, which genGoldberg.py already makes
from its (m,n). This script is for the others, which have no (m,n) to be derived
from -- C70 and C26 to begin with.

BUILT THE OTHER WAY UP, as the polar dual of a triangulation of the sphere. The
hard part of a fullerene is which face meets which, and on the triangulated side
that comes free from a convex hull. Any triangulation on n/2 + 2 points whose
every vertex degree is 5 or 6 dualizes to a fullerene: the 5s become pentagons,
the 6s hexagons, three faces meet at each new corner because the old faces were
triangles, and Euler forces exactly twelve 5s without our arranging it. polar_dual
(genGoldberg.py) also makes every face dead flat, since the face replacing a point
p lies in the plane x.p = 1 -- no fitting and no canonicalization.

So the whole job is placing n/2 + 2 points well, and there are two ways here.

--seed, repulsion from random: let the points repel until they settle, as
genRandomPolyh.py does. Points that even lands nearly every degree on 5 or 6, so
almost any seed yields SOME fullerene. Where the isomer count is 1 that is the
whole story: C26 has exactly one, so a C26 passing the checks below IS the C26,
and it needs no more care than a seed.

Rings, a symmetric start: for bigger cages that is not enough. C70 has thousands
of isomers, and settled repulsion finds a lumpy one every time -- the roundest
arrangement of 37 repelling points is not the cage chemistry means by C70. What
distinguishes that one is that no two of its pentagons touch, which for C70 is a
property only one isomer has. So its points are placed with its own 5-fold
symmetry to start with -- rings of five at even latitudes, each turned half a step
from the last -- and then relaxed, which evens the spacing without changing who
neighbours whom. The isolated-pentagon check then CONFIRMS the isomer instead of
our assuming it came out right.

Needs numpy, scipy and matplotlib -- the last only because the repulsion is
borrowed from genRandomPolyh.py, which draws with it. See docs/project-overview.md.
"""
import contextlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

# Our local modules, so that almost nothing here is new machinery. The polar dual
# comes from the Goldberg generator, whose 12-pentagons-and-hexagons solids are the
# icosahedral fullerenes -- the same construction, one step shorter. The repulsion
# comes from the random one, where the grids in data/ already exercise it. And the
# canonical form is its own shared module, because getting a solid's shape right
# once its structure is settled is wanted in more places than this.
import canonical_form
import grid_checks
import grid_topology
import json_format
from genGoldberg import polar_dual
from genRandomPolyh import simulate_repulsion

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

USAGE = __doc__[__doc__.index('Usage:'):__doc__.index('A fullerene')].rstrip()

# The named fullerenes, each with the point placement that reaches it.
#
# 'rings' places the dual's points symmetrically: 'fold' points per ring, ring i
# turned 'offsets[i]' of the way round from the zero meridian (in units of a full
# step, so 0.5 is half a step), at latitudes spread evenly from pole to pole. With
# 'poles', a single point caps each end and the rings share the room between them;
# without, the rings straddle the axis and the two end FACES sit on it instead.
# The number of points has to come to n/2 + 2, which check() insists on.
#
# 'isolated_pentagons' says the cage is one where no two pentagons share an edge,
# which is worth recording only where it identifies the isomer. Below C60 no cage
# manages it at all.
RECIPES = {
    # 12 pentagons and 3 hexagons. The 3 hexagons sit round the equator, and the
    # two ends of the 3-fold axis are corners rather than faces -- hence no poles
    # among the dual's 15 points, which come as 5 rings of 3.
    'C26': {'atoms': 26, 'name': 'C26 fullerene',
            'rings': {'fold': 3, 'offsets': [0, 0.5, 0, 0.5, 0], 'poles': False},
            'isolated_pentagons': False},
    # 12 pentagons and 25 hexagons: C60 stretched along a 5-fold axis. A pentagon
    # caps each end, so the dual has a point on the axis at each pole, and the
    # other 35 come as 7 rings of 5 -- two of those rings the remaining 10
    # pentagons, the other five the 25 hexagons.
    'C70': {'atoms': 70, 'name': 'C70 fullerene',
            'rings': {'fold': 5, 'offsets': [0, 0.5, 0, 0.5, 0, 0.5, 0],
                      'poles': True},
            'isolated_pentagons': True},
}

# Repulsion settings. The forces and damping are genRandomPolyh's own tuning, kept
# so this inherits behaviour that is already known to settle. The threshold is
# tighter and the iteration cap higher: that script blends a fraction of the way
# to settled and stops, while here the settled positions themselves are wanted,
# and a run that stopped early would leave the cage visibly lopsided.
RELAX = {'radius': 1.0, 'max_iterations': 4000, 'force_strength': 0.025,
         'max_force': 0.25, 'damping': 0.75, 'max_velocity': 0.05,
         'convergence_threshold': 1e-6, 'animate': False}



def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def relax(points):
    """Let the points repel each other over the sphere until they settle.

    stdout is held aside for the duration. simulate_repulsion reports its progress
    by printing, which is right where it lives -- genRandomPolyh writes its solid
    to a file -- but here stdout is the grid, and a stray iteration count in the
    middle of the JSON would be a corrupt data file.
    """
    with contextlib.redirect_stdout(sys.stderr):
        return simulate_repulsion(points, **RELAX)


def ring_points(fold, offsets, poles):
    """Points on the unit sphere in rings, with the given rotational symmetry.

    Latitudes are spread evenly in polar angle, which is a guess at the shape and
    only has to be close: it decides which points end up adjacent, and the
    relaxation afterwards sorts out the spacing. What it must get right is the
    TURN of each ring against the last, since that is what settles whether a ring
    meets the one above it in triangles pointing up or down.
    """
    points = [[0.0, 0.0, 1.0]] if poles else []
    for (i, offset) in enumerate(offsets):
        # With poles, the rings divide the space between them; without, they
        # straddle the axis, leaving no point on it.
        theta = (np.pi * (i + 1) / (len(offsets) + 1) if poles
                 else np.pi * (i + 0.5) / len(offsets))
        (z, r) = (np.cos(theta), np.sin(theta))
        for k in range(fold):
            angle = 2 * np.pi * (k + offset) / fold
            points.append([r * np.cos(angle), r * np.sin(angle), z])
    if poles:
        points.append([0.0, 0.0, -1.0])
    return np.array(points, dtype=float)


def random_points(count, seed):
    """`count` points scattered over the unit sphere, reproducibly.

    Seeded from the argument rather than the clock, so a solid worth keeping can
    be made again: the seed goes into the grid's "source" line.
    """
    generator = np.random.default_rng(seed)
    points = generator.normal(size=(count, 3))
    return points / np.linalg.norm(points, axis=1)[:, None]


def fullerene(atoms, rings=None, seed=None):
    """Cn as (vertices, faces), scaled to a circumradius of 1.

    The scale matches the rest of data/: the app's camera distance and its edge
    and vertex radii are all chosen for a solid about that size.
    """
    faces_wanted = atoms // 2 + 2
    start = (ring_points(**rings) if rings
             else random_points(faces_wanted, seed))
    if len(start) != faces_wanted:
        log(f'Error: the placement gives {len(start)} points, but C{atoms} needs '
            f'{faces_wanted} faces.')
        sys.exit(1)

    # Two stages, doing two different jobs. The repulsion decides the CAGE'S
    # STRUCTURE -- which faces meet which -- by spreading the points until every
    # degree is 5 or 6. Canonicalizing then fixes its SHAPE without touching that
    # structure, since reciprocation moves points but never changes who neighbours
    # whom.
    settled = relax(start)
    (_, cage_faces) = polar_dual(settled)
    (canonical, rounds, shift) = canonical_form.canonicalize(
        settled, ConvexHull(settled).simplices, cage_faces)
    if shift < canonical_form.SETTLED:
        log(f'Canonical after {rounds} rounds (last move {shift:.1e})')
    else:
        log(f'Warning: still moving {shift:.1e} after {rounds} rounds; '
            'the shape has not settled')

    # The last dual is taken exactly, rather than keeping the cage the iteration
    # was carrying, because polar_dual puts every face in the plane x.p = 1 of the
    # point it replaces -- flat to floating-point noise, where the iteration only
    # approaches flatness. check() holds it to that.
    (vertices, faces) = polar_dual(canonical)
    return (vertices / np.abs(np.linalg.norm(vertices, axis=1)).max(), faces)


def pentagons_isolated(faces):
    """Does no pentagon share an edge with another?

    The isolated-pentagon rule, which real fullerenes obey and which no cage below
    C60 can: two pentagons meeting along an edge put ten atoms into a bowl too
    tight for the bonding. Here it is a fingerprint -- for C70 exactly one isomer
    has it, so this tells the cage chemistry means from the thousands it doesn't.
    """
    adjacency = grid_topology.face_adjacency(faces)
    five = {f for (f, face) in enumerate(faces) if len(face) == 5}
    return not any(neighbor in five for f in five for neighbor in adjacency[f])


def check(atoms, vertices, faces, want_isolated):
    """Verify the cage against what a Cn must be, and describe it.

    The point of checking rather than trusting: the placement above is a guess
    followed by a simulation, so what comes out is not known in advance. These
    counts are what make it a fullerene, and for C70 the isolated-pentagon test is
    what makes it the RIGHT fullerene -- see the docstring.

    @returns a one-line description, or exits if anything is off
    """
    face_count = atoms // 2 + 2
    expected = {'vertices': atoms, 'faces': face_count,
                'edges': 3 * atoms // 2}
    sizes = grid_checks.face_census(faces)

    problems = grid_checks.check_counts(vertices, faces, expected)
    if sizes.get(5) != 12:
        problems.append(f'12 pentagons expected, got {sizes.get(5, 0)}')
    if set(sizes) - {5, 6}:
        problems.append('only pentagons and hexagons expected, got '
                        f'{sorted(sizes)}')
    # Three bonds per atom, which is what makes it a cage of carbon rather than
    # just a solid with the right faces.
    problems += grid_checks.check_vertex_degrees(faces, {3})
    isolated = pentagons_isolated(faces)
    if want_isolated and not isolated:
        problems.append('two pentagons share an edge, so this is not the isomer '
                        'wanted (see RECIPES)')
    problems += (
        # Flatness is the point of going via the polar dual, so it is held to
        # floating-point noise rather than to a tolerance.
        grid_checks.check_flat_faces(vertices, faces, 1e-9)
        + grid_checks.check_closed_surface(faces)
        + grid_checks.check_outward_winding(vertices, faces))

    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)

    lengths = [grid_checks.distance(vertices[a], vertices[b])
               for (a, b) in grid_topology.edges_of(faces)]
    return (f'C{atoms}: {len(vertices)} atoms, {len(lengths)} bonds, '
            f'{len(faces)} faces ({grid_checks.census_text(faces)}); '
            f'bonds {min(lengths):.4f} to {max(lengths):.4f} '
            f'(ratio {max(lengths) / min(lengths):.3f}); '
            + ('no two pentagons adjacent' if isolated
               else 'some pentagons adjacent'))


def build(grid_id, recipe):
    """One grid, as the dict that goes into the JSON file."""
    rings = recipe.get('rings')
    seed = recipe.get('seed')
    (vertices, faces) = fullerene(recipe['atoms'], rings=rings, seed=seed)
    log(check(recipe['atoms'], vertices, faces,
              recipe.get('isolated_pentagons', False)))

    # "Miscellaneous" because none of the classical families covers these, and the
    # picker files every solid under exactly one family. Not 'Goldberg': that is
    # the narrower word for the icosahedral fullerenes, and where one category
    # implies another data/ lists only the narrowest (see docs/json-format.md), so
    # a Goldberg polyhedron says so and stops rather than also saying 'fullerene'.
    grid = {'gridId': grid_id, 'gridName': recipe['name'],
            'categories': ['Miscellaneous', 'fullerene']}
    # So the file says where it came from, and can be made again exactly. A named
    # recipe reproduces from its name; an ad-hoc cage needs its seed, since that
    # is the only thing deciding which isomer turned up.
    arguments = (grid_id if grid_id in RECIPES
                 else f'--atoms={recipe["atoms"]} --seed={seed}')
    grid['source'] = f'Generated by util/genFullerene.py {arguments}.'
    grid['vertices'] = [[round(float(c), 6) for c in v] for v in vertices]
    grid['faces'] = faces
    return grid


def main():
    options = [arg for arg in sys.argv[1:] if arg.startswith('--')]
    argv = [arg for arg in sys.argv[1:] if not arg.startswith('--')]

    atoms = None
    seed = 0
    write_all = False
    # --flag=value, as --base= is in genGoldberg.py: one argument per option means
    # the positional recipe name can't be swallowed by a flag expecting a value.
    for option in options:
        if option == '--all':
            write_all = True
        elif option.startswith('--atoms='):
            atoms = int(option.split('=', 1)[1])
        elif option.startswith('--seed='):
            seed = int(option.split('=', 1)[1])
        else:
            log(f'Error: unknown option {option}.\n{USAGE}')
            sys.exit(1)

    if atoms is not None and (atoms < 20 or atoms % 2):
        # 20 is the dodecahedron, the smallest cage there is; an odd count leaves
        # a half-integer number of hexagons, so no such cage exists.
        log(f'Error: C{atoms} is not a fullerene; the atom count must be even '
            'and at least 20.')
        sys.exit(1)

    if write_all:
        for (grid_id, recipe) in RECIPES.items():
            path = DATA_DIR / f'{grid_id}.json'
            with open(path, 'w') as out:
                json_format.write_json(build(grid_id, recipe), out)
            log(f'Wrote {path}')
        return

    if atoms is not None:
        # An unnamed cage: any isomer the seed happens to settle into, which is
        # only trustworthy where there is one to find. No isolated-pentagon
        # requirement, since without knowing the isomer count it would prove
        # nothing about which cage this is.
        recipe = {'atoms': atoms, 'name': f'C{atoms} fullerene', 'seed': seed}
        json_format.write_json(build(f'C{atoms}', recipe), sys.stdout)
        return

    if len(argv) != 1 or argv[0] not in RECIPES:
        log(f'{USAGE}\n\nNamed recipes: {", ".join(RECIPES)}')
        sys.exit(1)
    json_format.write_json(build(argv[0], RECIPES[argv[0]]), sys.stdout)


if __name__ == '__main__':
    main()
