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
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grid_checks import (  # noqa: E402
    centroid, distance, face_bow, inscribed_radius, sharpest_corner,
    wound_outward,
)
from grid_topology import edges_of, vertex_degrees  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


def report(path):
    grid = json.loads(path.read_text())
    V = grid['vertices']
    F = grid['faces']
    edges = edges_of(F)
    lengths = sorted(distance(V[a], V[b]) for (a, b) in edges)
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
    tally = {}
    for degree in vertex_degrees(F).values():
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
