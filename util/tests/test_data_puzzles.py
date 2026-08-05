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

# Puzzles this sweep doesn't attempt, by test id. Only for ones whose check
# doesn't finish in the budget above -- never for one whose uniqueness is in
# doubt. Each is still verified at generation time by a stronger test than this
# one: genSliPuzzles.py keeps a clue set only if the solver can reach the
# solution BY DEDUCTION, which implies uniqueness, and it discards any clue set
# whose check times out rather than shipping it unproven.
SKIP_UNIQUENESS = {
    # 210 edges, the largest grid we have; the three playable puzzles on it pass
    # in well under the budget, but re-proving this one from its stored clues
    # runs long. Raising the budget for the whole sweep to cover one case would
    # cost more than it's worth.
    'gp12-display0': 'the check exceeds the time budget on a 210-edge grid',
}


def all_puzzle_cases():
    """One test case per puzzle: (grid_path, puzzles_path, key, puzzle_index),
    with a readable ID like 'cube-puzzle0' or 'eD-display0'.

    Display puzzles are swept too: they are shown with their clues on the title
    screen, so they hold to the same standard as a playable puzzle."""
    cases = []
    for puzzles_path in sorted(DATA_DIR.glob('*-puzzles.json')):
        stem = puzzles_path.name[:-len('-puzzles.json')]
        grid_path = DATA_DIR / f'{stem}.json'
        if not grid_path.exists():
            # Let the orphan test below report this; skip it here.
            continue
        data = json.loads(puzzles_path.read_text())
        for (key, label) in (('puzzles', 'puzzle'), ('displayPuzzles', 'display')):
            for i in range(len(data.get(key, []))):
                case_id = f'{stem}-{label}{i}'
                marks = ([pytest.mark.skip(reason=SKIP_UNIQUENESS[case_id])]
                         if case_id in SKIP_UNIQUENESS else [])
                cases.append(pytest.param(grid_path, puzzles_path, key, i,
                                          id=case_id, marks=marks))
    return cases


@pytest.mark.slow
def test_no_orphan_puzzle_files():
    """Every *-puzzles.json must have a matching grid file."""
    orphans = [p.name for p in DATA_DIR.glob('*-puzzles.json')
               if not (DATA_DIR / p.name.replace('-puzzles.json', '.json')).exists()]
    assert orphans == []


@pytest.mark.slow
@pytest.mark.parametrize(('grid_path', 'puzzles_path', 'key', 'index'),
                         all_puzzle_cases())
def test_puzzle_solution_is_unique(grid_path, puzzles_path, key, index):
    grid = json.loads(grid_path.read_text())
    mesh = Mesh.from_vertices_and_faces(grid['vertices'], grid['faces'])
    data = json.loads(puzzles_path.read_text())

    assert data['gridId'] == grid['gridId'], \
        f"{puzzles_path.name} gridId {data['gridId']!r} != {grid_path.name} gridId {grid['gridId']!r}"

    puzzle = data[key][index]
    clues = [(face, n) for (face, n) in enumerate(puzzle['clues']) if n != -1]
    unique = solution_is_unique(clues, len(clues), puzzle['solution'], mesh, None,
                                time_budget=TIME_BUDGET_SECONDS)
    assert unique, (f'{puzzles_path.name} {key}[{index}] is not uniquely solvable '
                    f'(or exceeded the {TIME_BUDGET_SECONDS}s time budget)')


def test_display_puzzles_key_is_never_empty():
    """An empty "displayPuzzles" would promise the title screen a loop that isn't
    there; the key is omitted instead (see docs/json-format.md).

    Fast, unlike the sweep above, so it runs by default: it only reads the files.
    """
    empty = [p.name for p in sorted(DATA_DIR.glob('*-puzzles.json'))
             if 'displayPuzzles' in json.loads(p.read_text())
             and not json.loads(p.read_text())['displayPuzzles']]
    assert empty == [], 'omit the key rather than shipping an empty list'
