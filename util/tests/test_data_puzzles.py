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
from collections import Counter
from pathlib import Path

import pytest
from compas.datastructures import Mesh

import grid_topology
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


def all_puzzle_cases(skip=None):
    """One test case per puzzle: (grid_path, puzzles_path, key, puzzle_index),
    with a readable ID like 'cube-puzzle0' or 'eD-display0'.

    Display puzzles are swept too: they are shown with their clues on the title
    screen, so they hold to the same standard as a playable puzzle.

    @param skip: {test id: reason} to mark as skipped. Per-test, since a puzzle
        the uniqueness sweep can't afford is still worth the cheaper checks."""
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
                marks = ([pytest.mark.skip(reason=skip[case_id])]
                         if skip and case_id in skip else [])
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
                         all_puzzle_cases(skip=SKIP_UNIQUENESS))
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


def loop_edges(solution):
    """A loop's edges, as frozensets so direction and starting point don't
    matter."""
    return {frozenset((solution[i], solution[(i + 1) % len(solution)]))
            for i in range(len(solution))}


@pytest.mark.parametrize(('grid_path', 'puzzles_path', 'key', 'index'),
                         all_puzzle_cases())
def test_puzzle_agrees_with_its_grid(grid_path, puzzles_path, key, index):
    """Every stored puzzle describes a real single loop on its own grid, with
    clues that count it correctly.

    Fast (no solver), so it runs by default, and it catches a whole class of
    mistake the uniqueness sweep would only report as "not solvable": a puzzle
    generated against a different version of the grid, whose vertex numbers no
    longer mean what they did. That's a live risk now that grids can be
    regenerated -- util/genGoldberg.py rebuilds one from its parameters.
    """
    grid = json.loads(grid_path.read_text())
    faces = grid['faces']
    solid_edges = {frozenset((f[i], f[(i + 1) % len(f)]))
                   for f in faces for i in range(len(f))}

    puzzle = json.loads(puzzles_path.read_text())[key][index]
    loop = puzzle['solution']
    edges = loop_edges(loop)

    assert len(set(loop)) == len(loop), 'the loop repeats a vertex'
    assert len(edges) == len(loop), 'the loop repeats an edge'
    assert not (edges - solid_edges), \
        'the loop uses pairs of vertices that are not edges of this solid'
    # Two loop edges at every vertex it passes through: that is what makes it a
    # closed path rather than a tree or several pieces.
    touches = {}
    for edge in edges:
        for v in edge:
            touches[v] = touches.get(v, 0) + 1
    assert set(touches.values()) == {2}, 'not a single closed loop'

    for (fkey, clue) in enumerate(puzzle['clues']):
        if clue == -1:
            continue
        face = faces[fkey]
        used = sum(1 for i in range(len(face))
                   if frozenset((face[i], face[(i + 1) % len(face)])) in edges)
        assert used == clue, f'face {fkey} says {clue} but the loop uses {used}'


def grid_files():
    """Every grid file in data/: not the puzzles, not the catalogue."""
    return [p for p in sorted(DATA_DIR.glob('*.json'))
            if p.name != 'grids.json' and not p.name.endswith('-puzzles.json')]


def test_source_urls_name_the_right_solid():
    """A polyHedronisme "source" must point at the solid it sits beside.

    Worth a test because the failure is invisible: the URL is well-formed, it
    returns 200, and it shows somebody else's polyhedron. data/J1.json really did
    ship with ?recipe=J92 for a moment, copied from an example and not substituted,
    and nothing else would have noticed.

    The recipe in the URL should match the grid's own "recipe" field, or its gridId
    where it has none -- which is what "recipe" is for these solids anyway.
    """
    prefix = 'https://levskaya.github.io/polyhedronisme/?recipe='
    wrong = []
    for path in grid_files():
        grid = json.loads(path.read_text())
        source = grid.get('source', '')
        if not source.startswith(prefix):
            continue            # generated grids say which script made them
        named = source[len(prefix):]
        expected = grid.get('recipe') or grid['gridId']
        if named != expected:
            wrong.append(f'{path.name} points at {named}, expected {expected}')
    assert wrong == [], '; '.join(wrong)


def test_fullerenes_really_are_fullerene_cages():
    """Anything labelled "fullerene" must have the structure the word names: three
    faces at every corner, exactly 12 pentagons, and nothing else but hexagons.

    Cheap here, and worth having in the data as well as in the generator, because a
    grid file outlives the run that made it: these come from a simulation followed
    by a convex hull (see util/genFullerene.py), so what they are was measured
    rather than laid out, and a re-run with a different seed or a retuned relaxation
    could quietly produce a different cage under the same name.
    """
    wrong = []
    for path in grid_files():
        grid = json.loads(path.read_text())
        if 'fullerene' not in grid.get('categories', []):
            continue
        faces = grid['faces']
        census = Counter(len(face) for face in faces)
        degrees = Counter(v for face in faces for v in face)
        atoms = len(grid['vertices'])
        if census.get(5) != 12 or set(census) - {5, 6}:
            wrong.append(f'{path.name}: faces {dict(sorted(census.items()))}')
        if set(degrees.values()) != {3} or len(degrees) != atoms:
            wrong.append(f'{path.name}: not every atom has three bonds')
        if len(faces) != atoms // 2 + 2:
            wrong.append(f'{path.name}: {atoms} atoms wants {atoms // 2 + 2} faces, '
                         f'has {len(faces)}')
    assert wrong == [], '; '.join(wrong)


def test_C70_is_the_isolated_pentagon_isomer():
    """C70 has thousands of isomers and this is the one chemistry means: the only
    one with no two pentagons sharing an edge.

    The property is what identifies the solid, and nothing else in the repo would
    notice its loss -- a different isomer has the same atom, bond and face counts,
    and passes every check above. See util/genFullerene.py, where a symmetric
    starting arrangement is what reaches this isomer in the first place.
    """
    grid = json.loads((DATA_DIR / 'C70.json').read_text())
    faces = grid['faces']
    adjacency = grid_topology.face_adjacency(faces)
    pentagons = {f for (f, face) in enumerate(faces) if len(face) == 5}
    touching = [(f, n) for f in pentagons for n in adjacency[f] if n in pentagons]
    assert touching == [], f'pentagons sharing an edge: {touching}'


def test_display_puzzles_key_is_never_empty():
    """An empty "displayPuzzles" would promise the title screen a loop that isn't
    there; the key is omitted instead (see docs/json-format.md).

    Fast, unlike the sweep above, so it runs by default: it only reads the files.
    """
    empty = [p.name for p in sorted(DATA_DIR.glob('*-puzzles.json'))
             if 'displayPuzzles' in json.loads(p.read_text())
             and not json.loads(p.read_text())['displayPuzzles']]
    assert empty == [], 'omit the key rather than shipping an empty list'
