#!/usr/bin/env python3.11
"""Generate one puzzle for every grid and report how good it is, without writing
anything. The regression test for changes to the puzzle GENERATOR.

Usage:
    util/sweep_grids.py                      # every grid, 60s each
    util/sweep_grids.py --budget 120         # more time per grid
    util/sweep_grids.py --seed 7 dbD dtD     # just these, a different draw

What it measures, and why each column matters:

  secs    how long one puzzle took, start to finish. Almost all of it is clue
          minimization, not painting.
  loop    edges in the solution loop, against `max`, the number of vertices --
          the loop is a simple cycle through vertices, so it can never be
          longer than that. A loop using a good fraction of the ceiling threads
          the whole solid.
  patch   the largest connected group of faces the loop never touches: a field
          of 0 clues with nothing happening in it. THIS is the number that
          matters most for whether a puzzle looks interesting, and the one that
          caught dbD's first puzzle having a whole untouched hemisphere. Small
          is good, but 0 is not the goal -- a few untouched faces read as
          organic rather than mechanical.
  clues   how many faces carry a clue.

Each column is shown against `was`: the mean over the puzzles already stored in
data/, so a change to the generator can be compared with what it replaces. Note
those stored puzzles were made by whatever generator was current when they were
written, which is not always the same one.

The seed is fixed and reported, because the whole point is comparing runs: with a
varying seed each run draws different solutions and small differences per grid are
noise. Same seed and same grids means the same draws, so a difference is real.

Reporting only, and writes nothing: use util/fill_puzzles.py to actually produce
puzzles. Needs python3.11 for compas and networkx.
"""
import argparse
import json
import os
import random
import signal
import statistics
import sys
import time
from pathlib import Path

# Select a non-interactive matplotlib backend BEFORE importing genSliPuzzles
# (which imports matplotlib.pyplot), exactly as the tests and run_gen.py do.
# Without it the generator believes it can draw its progress, and every grid dies
# in update_display on a figure that setup_display was never called to create --
# which is what happened the first time this script was run.
os.environ.setdefault('MPLBACKEND', 'Agg')

import networkx as nx  # noqa: E402  (after MPLBACKEND)
from compas.datastructures import Mesh  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genSliPuzzles  # noqa: E402  (needs the path set up first)
from genSliPuzzles import (  # noqa: E402
    RegionColoring, enumerate_solution, generate_minimal_clueset,
)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


class OutOfTime(Exception):
    pass


def _out_of_time(_signum, _frame):
    raise OutOfTime()


def loop_edges(loop):
    """The loop's edges as frozensets, for membership tests."""
    return {frozenset((loop[i], loop[(i + 1) % len(loop)]))
            for i in range(len(loop))}


def face_is_quiet(mesh, fkey, edges):
    """True if none of this face's edges is on the loop, i.e. its clue is 0."""
    verts = mesh.face_vertices(fkey)
    return not any(frozenset((verts[i], verts[(i + 1) % len(verts)])) in edges
                   for i in range(len(verts)))


def largest_quiet_patch(mesh, edges):
    """Size of the biggest connected group of faces the loop never touches."""
    quiet = {f for f in mesh.faces() if face_is_quiet(mesh, f, edges)}
    biggest = 0
    while quiet:
        group = {quiet.pop()}
        stack = list(group)
        while stack:
            for nbr in mesh.face_neighbors(stack.pop()):
                if nbr in quiet:
                    quiet.discard(nbr)
                    group.add(nbr)
                    stack.append(nbr)
        biggest = max(biggest, len(group))
    return biggest


def load_mesh(stem):
    grid = json.loads((DATA_DIR / f'{stem}.json').read_text())
    return Mesh.from_vertices_and_faces(grid['vertices'], grid['faces'])


def dual_graph(mesh):
    graph = nx.Graph()
    for fkey in mesh.faces():
        graph.add_node(fkey)
        for nbr in mesh.face_neighbors(fkey):
            graph.add_edge(fkey, nbr)
    return graph


def stored_means(stem, mesh):
    """Mean loop length, quiet patch and clue count over the stored puzzles."""
    path = DATA_DIR / f'{stem}-puzzles.json'
    if not path.exists():
        return (None, None, None)
    data = json.loads(path.read_text())
    puzzles = data.get('puzzles', []) + data.get('displayPuzzles', [])
    if not puzzles:
        return (None, None, None)
    return (statistics.mean(len(p['solution']) for p in puzzles),
            statistics.mean(largest_quiet_patch(mesh, loop_edges(p['solution']))
                            for p in puzzles),
            statistics.mean(sum(1 for c in p['clues'] if c != -1)
                            for p in puzzles))


def catalogue_stems():
    """Grid file stems in catalogue order, smallest first."""
    catalogue = json.loads((DATA_DIR / 'grids.json').read_text())
    return [(g['file'], g.get('edges', 0)) for g in catalogue['grids']]


def one_grid(stem, budget, seed):
    """Generate a single puzzle for one grid. Returns a result dict."""
    if not (DATA_DIR / f'{stem}.json').exists():
        return {'outcome': 'no grid file'}
    mesh = load_mesh(stem)
    # generate_minimal_clueset and the coloring read these module globals.
    genSliPuzzles.mesh = mesh
    genSliPuzzles.dualG = dual_graph(mesh)
    coloring = RegionColoring(mesh, genSliPuzzles.dualG)
    genSliPuzzles.coloring = coloring

    random.seed(f'{seed}:{stem}')
    started = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, budget)
    try:
        for _ in range(genSliPuzzles.MAX_REGION_ATTEMPTS):
            coloring.generate(0)
            try:
                solution = enumerate_solution(mesh)
            except ValueError:
                continue        # a coloring with no single loop; try another
            clues = generate_minimal_clueset(mesh)
            if clues:
                return {'outcome': 'ok', 'mesh': mesh,
                        'seconds': time.monotonic() - started,
                        'loop': len(solution),
                        'patch': largest_quiet_patch(mesh, loop_edges(solution)),
                        'clues': sum(1 for c in clues if c != -1)}
        return {'outcome': 'no clue set'}
    except OutOfTime:
        return {'outcome': f'TIMEOUT >{budget:g}s'}
    except Exception as failure:                    # noqa: BLE001
        # Report and carry on: one broken grid shouldn't end the sweep.
        return {'outcome': f'{type(failure).__name__}: {failure}'}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def show(value, spec='.1f'):
    return format(value, spec) if value is not None else '-'


def main():
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument('stems', nargs='*', help='grid file stems; default all')
    parser.add_argument('--budget', type=float, default=60.0,
                        help='seconds per grid before giving up (default 60)')
    parser.add_argument('--seed', type=int, default=0,
                        help='fixed seed, so runs are comparable (default 0)')
    args = parser.parse_args()

    signal.signal(signal.SIGALRM, _out_of_time)
    # The generator narrates each clue-set search at its default verbosity, which
    # buries this report's own table. Errors and warnings still come through.
    genSliPuzzles.VERBOSITY = 0
    todo = [(stem, edges) for (stem, edges) in catalogue_stems()
            if not args.stems or stem in args.stems]
    if not todo:
        sys.exit(f'No grid matches {args.stems}.')

    print(f'seed {args.seed}, {args.budget:g}s per grid')
    print(f'{"grid":6} {"outcome":14} {"secs":>6} {"loop":>5} {"was":>5} '
          f'{"max":>4} {"patch":>6} {"was":>5} {"clues":>6} {"was":>5}')
    problems = []
    for (stem, _edges) in todo:
        result = one_grid(stem, args.budget, args.seed)
        if result['outcome'] != 'ok':
            print(f'{stem:6} {result["outcome"]:14}')
            problems.append((stem, result['outcome']))
            sys.stdout.flush()
            continue
        mesh = result['mesh']
        (loop_was, patch_was, clues_was) = stored_means(stem, mesh)
        print(f'{stem:6} {"ok":14} {result["seconds"]:>6.2f} '
              f'{result["loop"]:>5} {show(loop_was):>5} '
              f'{mesh.number_of_vertices():>4} '
              f'{result["patch"]:>6} {show(patch_was):>5} '
              f'{result["clues"]:>6} {show(clues_was):>5}')
        sys.stdout.flush()

    print()
    if problems:
        print(f'{len(problems)} grid(s) with problems:')
        for (stem, outcome) in problems:
            print(f'  {stem}: {outcome}')
    else:
        print(f'all {len(todo)} grid(s) produced a puzzle')


if __name__ == '__main__':
    main()
