#!/usr/bin/env python3.11
"""Generate a valid puzzle WITHOUT proving it uniquely or deductively solvable.

Usage:
    util/genLoosePuzzle.py dtC                      # write data/dtC-puzzles.json
    util/genLoosePuzzle.py dtC --fraction 0.9       # more clues
    util/genLoosePuzzle.py dtC --seed 5 --force     # another try, overwriting

Why this exists: genSliPuzzles.py insists on a clue set with a provably unique
solution, and on the three all-triangle solids with very uneven vertex degrees
(dtC, dtD, dbD) that proof does not finish in any reasonable time. That leaves us
unable to tell whether such a puzzle is *hard to verify* or *hard to solve* --
quite different problems. This script sidesteps the question: it produces an
honest puzzle -- a real single-loop solution with clues read off it -- so a human
can try solving it and report back.

What it guarantees:
  - the solution is a single closed loop obeying the vertex rule;
  - every clue is the true number of loop edges around that face.

What it does NOT guarantee, and this is the whole point:
  - that the clues admit only that one solution;
  - that it is solvable by deduction rather than trial and error.

So treat the result as an experiment, not as catalogue content. It is written to
the normal data/<stem>-puzzles.json path so the game will load it, but it refuses
to overwrite an existing file unless given --force.

Faces whose every edge is on the loop are never clued, matching
genSliPuzzles.random_face_ordering: such a clue forces the whole loop at once.
"""
import argparse
import json
import random
import sys
from pathlib import Path

from compas.datastructures import Mesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slisolver import (  # noqa: E402  (needs the path set up first)
    apply_clues, is_valid_loop, propagate_constraints, solution_is_unique,
    solvable_by_deduction,
)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
ATTEMPTS = 2000


def load_grid(stem):
    grid = json.loads((DATA_DIR / f'{stem}.json').read_text())
    mesh = Mesh.from_vertices_and_faces(grid['vertices'], grid['faces'])
    return (grid, mesh)


def grow_region(mesh, rng, target):
    """A random connected set of faces, grown to roughly `target` faces."""
    faces = list(mesh.faces())
    region = {rng.choice(faces)}
    frontier = set(mesh.face_neighbors(next(iter(region))))
    while len(region) < target and frontier:
        pick = rng.choice(sorted(frontier))
        frontier.discard(pick)
        region.add(pick)
        for neighbor in mesh.face_neighbors(pick):
            if neighbor not in region:
                frontier.add(neighbor)
    return region


def connected(mesh, faces):
    """Is this set of faces connected through shared edges?"""
    if not faces:
        return False
    seen = {next(iter(faces))}
    stack = list(seen)
    while stack:
        for neighbor in mesh.face_neighbors(stack.pop()):
            if neighbor in faces and neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == len(faces)


def boundary_of(mesh, region):
    """The edges with one face inside `region` and one outside."""
    boundary = []
    for ekey in mesh.edges():
        (face1, face2) = mesh.edge_faces(ekey)
        if face1 is None or face2 is None:
            continue
        if (face1 in region) != (face2 in region):
            boundary.append(ekey)
    return boundary


def walk_loop(mesh, boundary):
    """The boundary as a sequence of vertex ids, or None if it isn't one loop."""
    adjacency = {}
    for (v1, v2) in boundary:
        adjacency.setdefault(v1, []).append(v2)
        adjacency.setdefault(v2, []).append(v1)
    if any(len(nbrs) != 2 for nbrs in adjacency.values()):
        return None  # A vertex used by 1, 3 or 4 loop edges.

    start = min(adjacency)
    loop = [start]
    (previous, current) = (start, adjacency[start][0])
    while current != start:
        loop.append(current)
        (a, b) = adjacency[current]
        (previous, current) = (current, a if a != previous else b)
    return loop if len(loop) == len(adjacency) else None


def find_solution(mesh, rng):
    """A random single-loop solution, as (region, boundary, loop)."""
    face_count = mesh.number_of_faces()
    for _ in range(ATTEMPTS):
        target = rng.randint(max(2, face_count // 3), 2 * face_count // 3)
        region = grow_region(mesh, rng, target)
        outside = set(mesh.faces()) - region
        if not outside or not connected(mesh, region) or not connected(mesh, outside):
            continue
        boundary = boundary_of(mesh, region)
        loop = walk_loop(mesh, boundary)
        if loop is None:
            continue
        for ekey in mesh.edges():
            mesh.edge_attribute(ekey, 'guess',
                                'filledIn' if ekey in boundary
                                or tuple(reversed(ekey)) in boundary
                                else 'ruledOut')
        if is_valid_loop(mesh):
            return (region, boundary, loop)
    return (None, None, None)


def wall_counts(mesh, region):
    """How many of each face's edges are on the loop."""
    counts = {}
    for fkey in mesh.faces():
        inside = fkey in region
        counts[fkey] = sum(1 for neighbor in mesh.face_neighbors(fkey)
                           if (neighbor in region) != inside)
    return counts


def choose_clues(mesh, counts, fraction, seed):
    """(eligible, chosen) faces for a given solution and clue density.

    Deterministic in `seed` alone, and shared by the survey and the writer, so a
    row the survey printed can be reproduced exactly by generating with the same
    --seed and --fraction.
    """
    eligible = [fkey for fkey in mesh.faces()
                if counts[fkey] < len(mesh.face_vertices(fkey))]
    picked = list(eligible)
    random.Random(seed + 1000).shuffle(picked)
    chosen = sorted(picked[:max(1, round(fraction * len(eligible)))])
    return (eligible, chosen)


def deduction_reach(mesh, clues, face_count):
    """How far the solver's deterministic rules get from these clues alone.
    Reported for interest: it says whether the puzzle is merely unverifiable or
    genuinely resistant to deduction."""
    for ekey in mesh.edges():
        mesh.edge_attribute(ekey, 'guess', 'unknown')
    apply_clues(clues, len(clues), mesh)
    ok = propagate_constraints(mesh, clues, len(clues))
    settled = sum(1 for ekey in mesh.edges()
                  if mesh.edge_attribute(ekey, 'guess') != 'unknown')
    return (ok, settled)


def survey(stem, seeds, fractions):
    """Try several solutions and clue densities, writing nothing.

    The useful puzzle is the one at the edge of our solver's reach: too many
    clues and plain propagation finishes it, which tells us nothing; too few and
    it may not be uniquely solvable at all. This finds that edge, and reports
    depth-1 lookahead separately, since that -- supposing one edge and following
    the consequences -- is roughly what a competent player does by hand.
    """
    (_grid, mesh) = load_grid(stem)
    edges = mesh.number_of_edges()
    print(f'{stem}: {edges} edges, {mesh.number_of_faces()} faces')
    print(f'{"seed":>4} {"loop":>4} {"clues":>6} {"frac":>5} '
          f'{"propagates":>10} {"lookahead":>10}')
    for seed in range(seeds):
        rng = random.Random(seed)
        (region, _boundary, loop) = find_solution(mesh, rng)
        if loop is None:
            continue
        counts = wall_counts(mesh, region)
        for fraction in fractions:
            (eligible, chosen) = choose_clues(mesh, counts, fraction, seed)
            clues = [(f, counts[f]) for f in chosen]
            (ok, settled) = deduction_reach(mesh, clues, mesh.number_of_faces())
            solved = solvable_by_deduction(mesh, clues, len(clues), depth=1)
            print(f'{seed:>4} {len(loop):>4} {len(chosen):>6} {fraction:>5.2f} '
                  f'{("dead" if not ok else f"{settled}/{edges}"):>10} '
                  f'{("solves" if solved else "stalls"):>10}')


def main():
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument('stem', help='grid file stem, e.g. dtC')
    parser.add_argument('--fraction', type=float, default=0.8,
                        help='share of eligible faces to clue (default 0.8)')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--force', action='store_true',
                        help='overwrite an existing puzzles file')
    parser.add_argument('--budget', type=float, default=30.0,
                        help='seconds to spend on the bounded uniqueness check '
                             '(default 30; it is reported, never required)')
    parser.add_argument('--survey', type=int, metavar='SEEDS',
                        help='try SEEDS solutions at several clue densities and '
                             'report how far deduction gets, writing nothing')
    args = parser.parse_args()

    if args.survey:
        survey(args.stem, args.survey, (1.0, 0.9, 0.8, 0.65, 0.5, 0.4))
        return

    (grid, mesh) = load_grid(args.stem)
    out_path = DATA_DIR / f'{args.stem}-puzzles.json'
    if out_path.exists() and not args.force:
        sys.exit(f'{out_path.name} already exists; pass --force to replace it.')

    rng = random.Random(args.seed)
    (region, boundary, loop) = find_solution(mesh, rng)
    if loop is None:
        sys.exit(f'No single-loop solution found in {ATTEMPTS} attempts.')

    counts = wall_counts(mesh, region)
    (eligible, chosen) = choose_clues(mesh, counts, args.fraction, args.seed)

    face_count = mesh.number_of_faces()
    clue_list = [-1] * face_count
    for fkey in chosen:
        clue_list[fkey] = counts[fkey]

    clues = [(fkey, counts[fkey]) for fkey in chosen]
    (ok, settled) = deduction_reach(mesh, clues, face_count)
    solved = solvable_by_deduction(mesh, clues, len(clues), depth=1)

    # A bounded attempt at the question this script otherwise skips. Three
    # outcomes, and the middle one matters most: "not unique" means a hand solver
    # may legitimately find a different loop than the one stored here.
    unique = solution_is_unique(clues, len(clues), loop, mesh, None,
                                time_budget=args.budget)
    verdict = ('unique' if unique
               else f'not proven unique within {args.budget:g}s')

    # No "displayPuzzles" key at all: an empty list would promise the title
    # screen a loop that isn't there (see docs/json-format.md, and the test in
    # util/tests/test_data_puzzles.py that enforces it).
    out_path.write_text(json.dumps(
        {'gridId': grid.get('gridId', args.stem),
         'puzzles': [{'clues': clue_list, 'solution': loop}]}, indent=1) + '\n')

    print(f'{args.stem}: loop of {len(loop)} edges over {len(region)} of '
          f'{face_count} faces')
    print(f'  clues: {len(chosen)} of {len(eligible)} eligible faces '
          f'({len(chosen) / face_count:.0%} of all {face_count}), '
          f'values {sorted(set(counts[f] for f in chosen))}')
    print(f'  deduction alone: {"consistent" if ok else "CONTRADICTION"}, '
          f'settles {settled}/{mesh.number_of_edges()} edges; '
          f'depth-1 lookahead {"finishes it" if solved else "stalls"}')
    print(f'  uniqueness: {verdict}')
    print(f'  wrote {out_path.name} -- the solution and clues are valid; '
          f'read the uniqueness line before trusting it as a puzzle')


if __name__ == '__main__':
    main()
