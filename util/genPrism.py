#!/usr/bin/env python3
"""Generate a prism or antiprism as a grid JSON file, with all faces regular.

Usage: python3 genPrism.py [--anti] n [gridId] [gridName]
Output is written to stdout; progress and the self-check go to stderr.
For the JSON format, see docs/json-format.md.

An n-prism is two regular n-gons joined by a band of n squares:

    faces = n + 2,  vertices = 2n,  edges = 3n,  three faces at every vertex

An n-antiprism twists the two n-gons half a step relative to each other and
joins them with a band of 2n equilateral triangles:

    faces = 2n + 2,  vertices = 2n,  edges = 4n,  four faces at every vertex

Both are uniform, and both are infinite families -- which is why they are left
out of the Johnson solids and why this script takes n rather than a name. They
belong to no classical family, so the grids come out "Miscellaneous"; see
docs/json-format.md.

The coordinates are exact rather than fitted. Every edge is 1 long, which is
what makes the faces regular: the two n-gons have circumradius
1/(2 sin(pi/n)), and the bands are as tall as they must be for their lateral
edges to be 1 too -- straight up for a prism, and for an antiprism a height of
sqrt(1 - 1/(4 cos^2(pi/2n))), since twisting by half a step puts a lateral
edge's endpoints 1/(2 cos(pi/2n)) apart horizontally.

Two sizes are deliberately not for this script: the square prism is the cube and
the triangular antiprism is the octahedron, both of which data/ already has from
genUniformPolyh.py, with the coordinates their own symmetry suggests.
"""
import math
import sys

# Our local modules. All standard-library only, so this script still needs
# nothing installed.
import grid_checks
import grid_topology
import json_format

# How much the checks below tolerate. The arithmetic here is exact to within
# floating point, so this is only guarding against a real mistake.
TOLERANCE = 1e-12


def log(*args):
    """Progress and diagnostics, on stderr: stdout carries the JSON."""
    print(*args, file=sys.stderr)


def ring(n, radius, height, offset_steps=0.0):
    """n points evenly round a circle at the given height.

    @param offset_steps: how far to rotate the ring, in whole steps of the
        n-gon's angle -- 0.5 is the half-step twist an antiprism needs.
    """
    return [(radius * math.cos(2 * math.pi * (i + offset_steps) / n),
             radius * math.sin(2 * math.pi * (i + offset_steps) / n),
             height)
            for i in range(n)]


def prism(n):
    """An n-prism with unit edges, as (vertices, faces).

    Faces are wound counterclockwise seen from outside, the convention grid
    files follow (see docs/json-format.md). Vertices 0..n-1 are the bottom ring
    and n..2n-1 the top.
    """
    radius = 1 / (2 * math.sin(math.pi / n))
    # Half above and half below the origin, so the solid is centred.
    vertices = ring(n, radius, -0.5) + ring(n, radius, 0.5)

    # The bottom cap seen from below runs the other way round than it does from
    # above, hence the reversal; the top cap is already counterclockwise.
    faces = [list(reversed(range(n))), list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        # Up the near side, along the top, back down: counterclockwise from
        # outside.
        faces.append([i, j, n + j, n + i])
    return (vertices, faces)


def antiprism(n):
    """An n-antiprism with unit edges, as (vertices, faces). See prism()."""
    radius = 1 / (2 * math.sin(math.pi / n))
    # A lateral edge spans half a step round the ring, so its endpoints are this
    # far apart horizontally; the height makes up the rest of its unit length.
    span = 1 / (2 * math.cos(math.pi / (2 * n)))
    height = math.sqrt(1 - span * span)
    vertices = (ring(n, radius, -height / 2)
                + ring(n, radius, height / 2, offset_steps=0.5))

    faces = [list(reversed(range(n))), list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        # Two triangles per step: one pointing up to the top ring, one hanging
        # down from it.
        faces.append([i, j, n + i])
        faces.append([j, n + j, n + i])
    return (vertices, faces)


def check(n, anti, vertices, faces):
    """Verify the solid, and return a one-line description.

    Regular faces are the point of the exact coordinates, so that's what this
    checks hardest -- see grid_checks.check_regular_faces for why equal sides
    alone isn't enough.
    """
    expected = {'vertices': 2 * n,
                'faces': (2 * n + 2) if anti else (n + 2),
                'edges': (4 * n) if anti else (3 * n)}
    problems = (grid_checks.check_counts(vertices, faces, expected)
                + grid_checks.check_euler(vertices, faces)
                + grid_checks.check_equal_edge_lengths(vertices, faces, TOLERANCE)
                + grid_checks.check_regular_faces(vertices, faces, TOLERANCE)
                + grid_checks.check_flat_faces(vertices, faces, TOLERANCE)
                + grid_checks.check_closed_surface(faces)
                + grid_checks.check_outward_winding(vertices, faces))
    if problems:
        for problem in problems:
            log(f'Error: {problem}.')
        sys.exit(1)

    edge = grid_checks.distance(vertices[faces[0][0]], vertices[faces[0][1]])
    return (f'{n}-{"antiprism" if anti else "prism"}: {len(vertices)} vertices, '
            f'{len(grid_topology.edges_of(faces))} edges, {len(faces)} faces '
            f'({grid_checks.census_text(faces)}); '
            f'all edges {edge:.6f}, all faces regular and flat')


def normalized(vertices):
    """Scaled to a circumradius of 1, as the rest of data/ is: the app's camera
    distances and its edge and vertex radii all assume a solid about that size.
    """
    longest = max(math.sqrt(sum(c * c for c in v)) for v in vertices)
    return [[c / longest for c in v] for v in vertices]


def main():
    args = [a for a in sys.argv[1:] if a != '--anti']
    anti = '--anti' in sys.argv[1:]
    if not args:
        log('Usage: python3 genPrism.py [--anti] n [gridId] [gridName]')
        sys.exit(1)
    n = int(args[0])
    least = 3
    if n < least:
        log(f'Error: n must be at least {least}.')
        sys.exit(1)
    if (anti and n == 3) or (not anti and n == 4):
        # Not an error -- just not this script's job, and the existing files have
        # nicer coordinates. See the note in the module docstring.
        log(f'Note: the {"triangular antiprism is the octahedron" if anti else "square prism is the cube"}; '
            f'data/ already has it from genUniformPolyh.py.')

    (vertices, faces) = antiprism(n) if anti else prism(n)
    log(check(n, anti, vertices, faces))

    kind = 'antiprism' if anti else 'prism'
    grid_id = args[1] if len(args) > 1 else f'{"A" if anti else "P"}{n}'
    grid_name = args[2] if len(args) > 2 else f'{n}-gonal {kind}'

    # "Miscellaneous" is the family for a solid in none of the classical ones;
    # the kind is the cross-cutting attribute that says what it actually is. An
    # even-sided prism is also a zonohedron, and the hexagonal one a
    # parallelohedron -- but which categories a grid claims is a judgement about
    # what's worth teaching, so those go in by hand rather than from here.
    categories = ['Miscellaneous', kind]

    grid = {'gridId': grid_id, 'gridName': grid_name, 'categories': categories,
            # polyHédronisme's notation for these two families.
            'recipe': f'{"A" if anti else "P"}{n}',
            'source': f'Generated by util/genPrism.py '
                      f'{"--anti " if anti else ""}{n}.'}
    grid['vertices'] = [[round(c, 6) for c in v] for v in normalized(vertices)]
    grid['faces'] = faces
    json_format.write_json(grid, sys.stdout)


if __name__ == '__main__':
    main()
