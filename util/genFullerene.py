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
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

# Our local modules, so that almost nothing here is new machinery. The polar dual
# comes from the Goldberg generator, whose 12-pentagons-and-hexagons solids are the
# icosahedral fullerenes -- the same construction, one step shorter. The repulsion
# comes from the random one, where the grids in data/ already exercise it. And the
# shaping passes are their own shared module, because getting a solid's shape right
# once its structure is settled is wanted in more places than this.
import grid_checks
import grid_topology
import json_format
import polyhedron_shape
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
            'relax': True, 'isolated_pentagons': False},
    # 12 pentagons and 25 hexagons: C60 stretched along a 5-fold axis. A pentagon
    # caps each end, so the dual has a point on the axis at each pole, and the
    # other 35 come as 7 rings of 5 -- two of those rings the remaining 10
    # pentagons, the other five the 25 hexagons.
    'C70': {'atoms': 70, 'name': 'C70 fullerene',
            'rings': {'fold': 5, 'offsets': [0, 0.5, 0, 0.5, 0, 0.5, 0],
                      'poles': True},
            'relax': True, 'isolated_pentagons': True},
    # The same cage carried on: a capped (5,5) nanotube, which is what C70 already
    # is with one belt of hexagons. Five belts make it plainly a tube, at about
    # 1.8 times as long as it is wide.
    #
    # Nothing new is needed for it, which is the point worth keeping: a capped
    # nanotube IS a fullerene. Each cap is half a C60 and holds six pentagons, so
    # the twelve Euler insists on are all used up there and the tube between them
    # is nothing but hexagons -- no other polygon has to appear, however long it
    # gets. Two more rings of five per belt: 6 + belts rings in all.
    'C110': {'atoms': 110, 'name': 'C110 capped nanotube',
             'rings': {'fold': 5, 'poles': True,
                       'offsets': [0, 0.5, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0.5, 0]},
             'categories': ['nanotube'], 'isolated_pentagons': True},
}

# Repulsion settings. The forces and damping are genRandomPolyh's own tuning, kept
# so this inherits behaviour that is already known to settle. The threshold is
# tighter and the iteration cap higher: that script blends a fraction of the way
# to settled and stops, while here the settled positions themselves are wanted,
# and a run that stopped early would leave the cage visibly lopsided.
RELAX = {'radius': 1.0, 'max_iterations': 4000, 'force_strength': 0.025,
         'max_force': 0.25, 'damping': 0.75, 'max_velocity': 0.05,
         'convergence_threshold': 1e-6, 'animate': False}

# How much drift is still acceptable in the canonical INTERMEDIATE, which does not
# have to converge: regularize takes it from there and decides the final shape. A
# thousandth of the radius is about a twentieth of a bond, well past anything a
# player could notice, so more than that says the cage itself is suspect rather than
# merely unfinished.
CANONICAL_ENOUGH = 1e-3



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


def fullerene(atoms, rings=None, seed=None, relax_wanted=True):
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

    # Only the first stage decides STRUCTURE -- which faces meet which -- and the
    # two shaping passes then move vertices about without ever changing it.
    #
    # A RANDOM start needs the repulsion: scattered points hull into a mess, and
    # spreading them is what drives every degree to 5 or 6. For a long tube it is
    # actively wrong -- repulsion spreads points evenly over a SPHERE, and the
    # evenest arrangement of 57 points is not a tube, so it rolled the five-belt
    # cage back up into a ball, from 1.84 times as long as wide to 0.89. The rings
    # already ARE the structure; the shaping passes give the shape.
    #
    # Hence a per-recipe choice rather than one rule, and C70 and C26 keep the
    # repulsion they were built with even though neither needs it. Not history for
    # its own sake: the repulsion moves the points, the hull then numbers its
    # triangles in a different order, and the cage comes out with the same shape
    # under different vertex and face NUMBERS. Those numbers are what the stored
    # puzzles index their clues and solutions by, so a recipe has to keep
    # reproducing the file it produced. Dropping it here would leave C70's shape
    # untouched to four figures and its puzzles pointing at the wrong faces.
    settled = relax(start) if relax_wanted else start
    (_, cage_faces) = polar_dual(settled)

    # Canonicalizing first, as a well-behaved intermediate: it leaves the cage
    # convex and roughly even, which is a much better place to regularize from
    # than the raw dual, whose edges vary by nearly a factor of two.
    (canonical, rounds, shift) = polyhedron_shape.canonicalize(
        settled, ConvexHull(settled).simplices, cage_faces)
    # Reported, not warned about, unless it is a long way off. This pass only has to
    # hand regularize something convex and roughly even, and regularize sets the
    # final shape from there, so a residue of a few parts in a million never reaches
    # the grid -- C110 stops at 7e-06 and its numbers are the same to four figures
    # either way. A residue big enough to SEE would mean something else is wrong.
    if shift >= CANONICAL_ENOUGH:
        log(f'Warning: canonical form still moving {shift:.1e} after {rounds} '
            'rounds, which is enough to see; the cage may be malformed')
    elif shift < polyhedron_shape.SETTLED:
        log(f'Canonical after {rounds} rounds (last move {shift:.1e})')
    else:
        log(f'Canonical enough after {rounds} rounds (last move {shift:.1e}, '
            'still easing -- regularize sets the shape from here)')
    (vertices, faces) = polar_dual(canonical)

    # Then regularize, which is what gives a fullerene its real proportions.
    # Canonical form alone draws C70 exactly as round as C60, because tangency to
    # one sphere is a roundness condition; asking instead for regular faces of a
    # common edge length elongates it, as the molecule is elongated, and does so
    # without a weight to tune. See polyhedron_shape.py.
    #
    # This is also why check() cannot ask for flatness to floating-point noise any
    # more: regular and flat are incompatible on a curved cage, and the molecule's
    # own hexagons are not flat either.
    vertices = polyhedron_shape.regularize(vertices, faces)

    # Stand the cage up. The rings are built about z, and the app's camera sits out
    # along z too (see CAMERA_DISTANCE in js/constants.js), so a cage left as built
    # is seen END ON: C110 arrives looking like a ball, with the whole length of the
    # tube hidden behind its own cap. Turning the axis to y -- which is up on screen
    # -- shows it standing, as the pictures of nanotubes do.
    #
    # A rotation about x, not a swap of axes: swapping two would mirror the solid and
    # so reverse the winding of every face, and check() insists on outward winding
    # for good reason. Vertex ORDER is untouched either way, which is what keeps any
    # stored puzzle valid -- clues and solutions index these lists.
    upright = np.column_stack((vertices[:, 0], vertices[:, 2], -vertices[:, 1]))
    return (upright, faces)


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
        # Faces are bowed here, unavoidably: regularizing asks them to be regular
        # polygons of one size, which on a curved cage cannot also be flat, and the
        # molecule's hexagons aren't flat either. So the tolerance is set to catch a
        # face that has gone WRONG rather than one that is merely curved -- 5% of the
        # circumradius, against the 2% these cages actually reach and the 0.05% that
        # data/tI.json has always carried.
        grid_checks.check_flat_faces(vertices, faces, 0.05)
        + grid_checks.check_closed_surface(faces)
        + grid_checks.check_outward_winding(vertices, faces))

    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)

    lengths = [grid_checks.distance(vertices[a], vertices[b])
               for (a, b) in grid_topology.edges_of(faces)]
    worst_bow = max(grid_checks.face_bow(grid_checks.corners_of(vertices, face))
                    for face in faces)
    # Length against width about the z axis, which the ring recipes put the cage's
    # main symmetry axis on. Reported because it is the point of regularizing: a
    # canonical C70 reads 0.95 here, the same as a round C60, and the molecule is
    # nearer 1.1. Not a check -- there is nothing to compare against for a cage
    # whose shape nobody has published -- but the number to look at.
    (along, across) = extent(vertices)
    return (f'C{atoms}: {len(vertices)} atoms, {len(lengths)} bonds, '
            f'{len(faces)} faces ({grid_checks.census_text(faces)}); '
            f'bonds {min(lengths):.4f} to {max(lengths):.4f} '
            f'(ratio {max(lengths) / min(lengths):.3f}); '
            f'length/width {along / across:.3f}; faces bowed {worst_bow:.1e}; '
            + ('no two pentagons adjacent' if isolated
               else 'some pentagons adjacent'))


def extent(vertices):
    """How long the cage is along its axis, and how wide across it.

    The axis is y: the cage is stood upright before this sees it (see fullerene),
    since y is up on screen.
    """
    heights = [v[1] for v in vertices]
    widest = max(math.hypot(v[0], v[2]) for v in vertices)
    return (max(heights) - min(heights), 2 * widest)


def build(grid_id, recipe):
    """One grid, as the dict that goes into the JSON file."""
    rings = recipe.get('rings')
    seed = recipe.get('seed')
    # A random start has no choice about it; a ring start says for itself. See the
    # note in fullerene() for why this is per recipe and not one rule.
    relax_wanted = recipe.get('relax', seed is not None)
    (vertices, faces) = fullerene(recipe['atoms'], rings=rings, seed=seed,
                                 relax_wanted=relax_wanted)
    log(check(recipe['atoms'], vertices, faces,
              recipe.get('isolated_pentagons', False)))

    # "Miscellaneous" because none of the classical families covers these, and the
    # picker files every solid under exactly one family. Not 'Goldberg': that is
    # the narrower word for the icosahedral fullerenes, and where one category
    # implies another data/ lists only the narrowest (see docs/json-format.md), so
    # a Goldberg polyhedron says so and stops rather than also saying 'fullerene'.
    #
    # A recipe may add to that: C110 is a capped nanotube as well as a cage, and
    # carries 'nanotube' so it can be found beside the open tubes of
    # util/genNanotube.py. The two overlap rather than nest -- a capped tube is both,
    # an open one only a nanotube -- so neither implies the other and both are listed.
    grid = {'gridId': grid_id, 'gridName': recipe['name'],
            'categories': ['Miscellaneous', 'fullerene']
                          + recipe.get('categories', [])}
    # So the file says where it came from, and can be made again exactly. A named
    # recipe reproduces from its name; an ad-hoc cage needs its seed, since that
    # is the only thing deciding which isomer turned up.
    # Spelled out rather than taken from argv, because --all writes several files and
    # each should say the command that makes IT, not all of them. See
    # json_format.source_line.
    grid['source'] = json_format.source_line(
        [grid_id] if grid_id in RECIPES
        else [f'--atoms={recipe["atoms"]}', f'--seed={seed}'])
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
