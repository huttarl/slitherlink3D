#!/usr/bin/env python3
"""Generate an open carbon nanotube: a cylinder of hexagons, with no ends.

Usage:
    util/genNanotube.py                 # the default tube, to stdout
    util/genNanotube.py --belts=10      # a longer or shorter one
    util/genNanotube.py --out=data/ntube.json

UNLIKE every other generator here, this writes a solid that is NOT CLOSED. It is a
tube with two open rims, so grid_checks.check_closed_surface would reject it and is
deliberately not called; what replaces it is check_cylinder below. Euler's formula
gives 0 rather than 2, which is the honest signature of a cylinder, and the rims are
left jagged -- the points of the outermost hexagons stick out, because nothing is cut
off to tidy them.

Built by stripping a capped tube rather than by rolling a lattice, which is the
cheaper road to the same place: genFullerene already makes a verified capped (5,5)
tube, and every one of its twelve pentagons is in a cap. So dropping every face that
shares an atom with a pentagon removes both caps and the ring of hexagons blending
into them, and what remains is whole belts of the barrel. No hexagon is ever cut.

The cost of that road is waste -- two belts go with the caps, so the capped tube has
to be built longer than the tube wanted -- and one limitation worth knowing: it can
only make the armchair (n,n) flavour, since that is what the ring construction
produces. A zigzag or a chiral (1,3) tube would want the lattice rolled directly.

WHAT AN OPEN TUBE COSTS THE PUZZLE, which is the point of building it to try:
  - A rim edge belongs to one face, so it can never lie on the boundary between
    painted and unpainted faces -- and that boundary is how genSliPuzzles chooses its
    solution loop. Rim edges therefore never appear in a solution: they are edges the
    player can never fill. There are 4 per hexagon-belt-worth of rim, and on the
    default tube that is 40 of 140 edges.
  - slisolver's colouring deduction (apply_color_rules) reads an edge's two faces and
    skips any edge that has only one. It stays correct, but loses its strongest
    inference at the rims, so puzzles here may want more clues or take longer to
    whittle.
Both were known before building it; see docs/json-format.md on closed surfaces.

Needs numpy and scipy, through genFullerene. See docs/project-overview.md.
"""
import sys
from collections import Counter
from pathlib import Path

import numpy as np

# Our local modules: the capped tube comes from the fullerene generator, and the
# reporting and formatting are the shared ones every generator here uses.
import grid_checks
import grid_topology
import json_format
from genFullerene import fullerene

# How many belts of hexagons the capped tube is built with. Two are lost with the
# caps, so this is the wanted tube's length plus two: 10 leaves 8 belts, 40 hexagons,
# and a tube about 1.6 times as long as it is wide -- plainly a tube, and still a
# grid of ordinary size for this catalogue.
DEFAULT_BELTS = 10

# The tube has 5-fold symmetry, being the armchair (5,5): five hexagons round.
AROUND = 5


def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def capped_tube(belts):
    """A capped (5,5) tube with `belts` belts, from the fullerene generator."""
    # Alternating half-step offsets, and no repulsion: see the notes in
    # genFullerene, where relaxing a long tube rolls it back into a ball.
    offsets = [0.5 * (i % 2) for i in range(6 + belts)]
    return fullerene(60 + 10 * belts, relax_wanted=False,
                     rings={'fold': AROUND, 'offsets': offsets, 'poles': True})


def strip_caps(vertices, faces):
    """Keep the barrel: every face that shares no atom with a pentagon.

    Purely topological -- no plane, no threshold -- because the pentagons say where
    the caps are. Renumbering keeps the atoms in their original order, so the tube's
    own structure decides the numbering rather than the iteration order of a set.
    """
    in_a_cap = {v for face in faces if len(face) == 5 for v in face}
    kept = [face for face in faces if not (set(face) & in_a_cap)]
    used = sorted({v for face in kept for v in face})
    renumbered = {v: i for (i, v) in enumerate(used)}
    return ([vertices[v] for v in used],
            [[renumbered[v] for v in face] for face in kept])


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


def check_cylinder(vertices, faces):
    """The checks a tube must pass, in place of the closed-surface ones.

    A closed solid is checked by Euler = 2 and every edge having two faces. Neither
    holds here, so what is checked instead is that this is a cylinder and not some
    other torn thing: nothing but hexagons, Euler 0, exactly two rims, and every atom
    with two or three bonds -- two on a rim, three inside. An atom with ONE bond would
    matter: a loop needs two edges at every vertex it visits, so that bond could never
    be filled and would be a dead edge in the middle of the grid rather than at a rim.

    @returns a list of problems, empty if all is well
    """
    problems = []
    census = Counter(len(face) for face in faces)
    if set(census) != {6}:
        problems.append(f'only hexagons expected, got {dict(sorted(census.items()))}')

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


def nanotube(belts):
    """An open tube as (vertices, faces), scaled to a circumradius of 1."""
    (vertices, faces) = capped_tube(belts)
    (points, tube) = strip_caps(vertices.tolist(), faces)
    # Rescale: the barrel's own radius is well inside the capped solid's, so without
    # this the tube would arrive smaller than every other grid and the app's camera,
    # whose distance suits a solid of circumradius 1, would leave it small on screen.
    points = np.array(points, dtype=float)
    points -= points.mean(axis=0)
    return (points / np.linalg.norm(points, axis=1).max(), tube)


def describe(vertices, faces):
    """One line about the tube, for the log."""
    edges = grid_topology.edges_of([list(face) for face in faces])
    lengths = [grid_checks.distance(vertices[a], vertices[b]) for (a, b) in edges]
    rims = boundary_cycles(faces)
    on_a_rim = sum(len(rim) for rim in rims)
    heights = [v[1] for v in vertices]
    width = 2 * max(np.hypot(v[0], v[2]) for v in vertices)
    bow = max(grid_checks.face_bow(grid_checks.corners_of(vertices, list(face)))
              for face in faces)
    return (f'{len(faces)} hexagons, {len(vertices)} atoms, {len(edges)} bonds '
            f'({on_a_rim} of them on a rim, so never in a solution); '
            f'bonds {min(lengths):.4f} to {max(lengths):.4f} '
            f'(ratio {max(lengths) / min(lengths):.3f}); '
            f'length/width {(max(heights) - min(heights)) / width:.3f}; '
            f'faces bowed {bow:.1e}')


def main():
    belts = DEFAULT_BELTS
    out = None
    for option in sys.argv[1:]:
        if option.startswith('--belts='):
            belts = int(option.split('=', 1)[1])
        elif option.startswith('--out='):
            out = Path(option.split('=', 1)[1])
        else:
            log(f'Error: unknown option {option}.\n'
                f'{__doc__[__doc__.index("Usage:"):__doc__.index("UNLIKE")].rstrip()}')
            sys.exit(1)
    if belts < 4:
        # Three belts leave one after the caps go, which is a ring and not a tube.
        log(f'Error: --belts={belts} leaves {belts - 2} belt(s) after the caps go; '
            'ask for at least 4.')
        sys.exit(1)

    (vertices, faces) = nanotube(belts)
    rounded = [[round(float(c), 6) for c in v] for v in vertices]
    problems = check_cylinder(rounded, faces)
    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)
    log(describe(rounded, faces))

    hexagons = len(faces)
    grid = {
        'gridId': 'ntube',
        'gridName': f'Open nanotube ({hexagons} hexagons)',
        # No 'fullerene': a fullerene is a closed cage, and this is open. Nor any
        # other attribute -- what is interesting about it is that it has no ends,
        # which the name says.
        'categories': ['Miscellaneous'],
        'source': (f'Generated by util/genNanotube.py --belts={belts}.'),
        'vertices': rounded,
        'faces': faces,
    }
    if out:
        with open(out, 'w') as handle:
            json_format.write_json(grid, handle)
        log(f'Wrote {out}')
    else:
        json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
