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
              coordinates; small values are invisible, and note that
              util/obj2json.py rounds coordinates to 3 decimals, which alone
              costs a few thousandths.
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

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


def edges_of(faces):
    return {tuple(sorted((face[i], face[(i + 1) % len(face)])))
            for face in faces for i in range(len(face))}


def subtract(p, q):
    return [p[i] - q[i] for i in range(3)]


def cross(u, v):
    return [u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0]]


def norm(u):
    return math.sqrt(sum(x * x for x in u))


def centroid(points):
    return [sum(p[i] for p in points) / len(points) for i in range(3)]


def sharpest_corner(corners):
    """The sharpest interior angle of a face, in degrees."""
    sharpest = 180.0
    for i in range(len(corners)):
        previous = corners[i - 1]
        here = corners[i]
        following = corners[(i + 1) % len(corners)]
        (u, v) = (subtract(previous, here), subtract(following, here))
        scale = norm(u) * norm(v)
        if scale == 0:
            continue
        cosine = max(-1.0, min(1.0, sum(u[k] * v[k] for k in range(3)) / scale))
        sharpest = min(sharpest, math.degrees(math.acos(cosine)))
    return sharpest


def inscribed_radius(corners):
    """Twice the area over the perimeter: the inscribed circle of a regular
    polygon, and a fair stand-in for how much room a clue digit has."""
    centre = centroid(corners)
    area = sum(norm(cross(subtract(corners[i], centre),
                          subtract(corners[(i + 1) % len(corners)], centre))) / 2
               for i in range(len(corners)))
    perimeter = sum(norm(subtract(corners[i], corners[(i + 1) % len(corners)]))
                    for i in range(len(corners)))
    return 2 * area / perimeter if perimeter else 0.0


def face_bow(corners):
    """How far the corners stray from the plane of the first three."""
    normal = cross(subtract(corners[1], corners[0]),
                   subtract(corners[2], corners[1]))
    scale = norm(normal)
    if scale == 0:
        return math.inf
    return max(abs(sum(normal[k] * (corner[k] - corners[0][k]) for k in range(3)))
               / scale for corner in corners)


def wound_outward(corners, solid_centre):
    normal = cross(subtract(corners[1], corners[0]),
                   subtract(corners[2], corners[1]))
    middle = subtract(centroid(corners), solid_centre)
    return sum(normal[k] * middle[k] for k in range(3)) > 0


def report(path):
    grid = json.loads(path.read_text())
    V = grid['vertices']
    F = grid['faces']
    edges = edges_of(F)
    lengths = sorted(norm(subtract(V[a], V[b])) for (a, b) in edges)
    median = statistics.median(lengths)
    faces = [[V[i] for i in face] for face in F]
    centre = centroid(V)
    sizes = {}
    for face in F:
        sizes[len(face)] = sizes.get(len(face), 0) + 1

    inradii = [inscribed_radius(f) for f in faces]
    print(f'{grid.get("gridName", path.stem)}  ({path.name})')
    print(f'  V={len(V)} E={len(edges)} F={len(F)}   '
          f'Euler {len(V) - len(edges) + len(F)} (want 2)   faces: '
          + ', '.join(f'{c}x{s}' for (s, c) in sorted(sizes.items())))
    print(f'  edges     {lengths[0]:.3f} / {median:.3f} / {lengths[-1]:.3f}  '
          f'(shortest is {lengths[0] / median:.0%} of median)')
    print(f'  sharpest  {min(sharpest_corner(f) for f in faces):.1f} degrees')
    print(f'  inradius  {min(inradii):.3f} to {max(inradii):.3f}  '
          f'(x{max(inradii) / min(inradii):.1f})')
    print(f'  bow       {max(face_bow(f) for f in faces):.1e}')
    degrees = {}
    for face in F:
        for v in face:
            degrees[v] = degrees.get(v, 0) + 1
    tally = {}
    for degree in degrees.values():
        tally[degree] = tally.get(degree, 0) + 1
    print(f'  degrees   '
          + ', '.join(f'{count}x{degree}' for (degree, count) in sorted(tally.items())))
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
