"""Data-integrity sweep: verify every puzzle in data/ has a unique solution.

These tests are marked 'slow' and excluded from default pytest runs
(see pytest.ini), since solver time can grow quickly with grid size.
Run them with:

    pytest -m slow util/tests

Why this sweep exists: puzzles produced by genSliPuzzles.py are verified
unique at generation time, but nothing else stops unverified puzzle data
from landing in data/. That happened with the original hand-made cube
puzzle (committed Oct 2025, before the solver existed): its mirror-
symmetric clues admitted at least two solutions, discovered only by a
player in July 2026. This sweep would have caught it.
"""
import json
from pathlib import Path

import pytest
from compas.datastructures import Mesh

from slisolver import solution_is_unique

DATA_DIR = Path(__file__).resolve().parent.parent.parent / 'data'

# Give up on any single puzzle after this long. Exhausting the budget FAILS
# the test (uniqueness unproven), which is the safe direction; raise the
# budget if a legitimately large grid ever trips it.
TIME_BUDGET_SECONDS = 300


def all_puzzle_cases():
    """One test case per puzzle: (grid_path, puzzles_path, puzzle_index),
    with a readable ID like 'cube-puzzle0'."""
    cases = []
    for puzzles_path in sorted(DATA_DIR.glob('*-puzzles.json')):
        stem = puzzles_path.name[:-len('-puzzles.json')]
        grid_path = DATA_DIR / f'{stem}.json'
        if not grid_path.exists():
            # Let the orphan test below report this; skip it here.
            continue
        num_puzzles = len(json.loads(puzzles_path.read_text())['puzzles'])
        for i in range(num_puzzles):
            cases.append(pytest.param(grid_path, puzzles_path, i,
                                      id=f'{stem}-puzzle{i}'))
    return cases


@pytest.mark.slow
def test_no_orphan_puzzle_files():
    """Every *-puzzles.json must have a matching grid file."""
    orphans = [p.name for p in DATA_DIR.glob('*-puzzles.json')
               if not (DATA_DIR / p.name.replace('-puzzles.json', '.json')).exists()]
    assert orphans == []


@pytest.mark.slow
@pytest.mark.parametrize(('grid_path', 'puzzles_path', 'index'), all_puzzle_cases())
def test_puzzle_solution_is_unique(grid_path, puzzles_path, index):
    grid = json.loads(grid_path.read_text())
    mesh = Mesh.from_vertices_and_faces(grid['vertices'], grid['faces'])
    data = json.loads(puzzles_path.read_text())

    assert data['gridId'] == grid['gridId'], \
        f"{puzzles_path.name} gridId {data['gridId']!r} != {grid_path.name} gridId {grid['gridId']!r}"

    puzzle = data['puzzles'][index]
    clues = [(face, n) for (face, n) in enumerate(puzzle['clues']) if n != -1]
    unique = solution_is_unique(clues, len(clues), puzzle['solution'], mesh, None,
                                time_budget=TIME_BUDGET_SECONDS)
    assert unique, (f'{puzzles_path.name} puzzle {index} is not uniquely solvable '
                    f'(or exceeded the {TIME_BUDGET_SECONDS}s time budget)')
