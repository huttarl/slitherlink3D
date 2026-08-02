"""Tests for genSliPuzzles.py — currently the clue-minimization workflow.

Strategy:
    min_prefix_satisfying() is a pure function, so we unit-test it with
    fake predicates (no solver, no mesh). cut_clues() takes the mesh as an
    argument, so the integration tests just hand it a small cube and let
    the real solver run -- no module globals involved.
"""
import os

# Select a non-interactive matplotlib backend BEFORE importing genSliPuzzles
# (which imports matplotlib.pyplot), so the tests can't try to open a GUI
# window, e.g. when run headless.
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest
from compas.datastructures import Mesh

import genSliPuzzles
from genSliPuzzles import (
    LOOKAHEAD_DEPTH,
    RegionColoring,
    blue,
    cut_clues,
    min_prefix_satisfying,
    red,
)
from slisolver import solvable_by_deduction


# --- helpers ---

def threshold_predicate(true_from, max_calls=50):
    """Build a monotonic fake predicate: predicate(n) is True iff n >= true_from.

    Returns (predicate, calls). `calls` is a list recording each n the
    predicate was called with, for asserting call counts.

    The predicate raises after max_calls calls, so a broken search fails
    fast instead of hanging pytest in an infinite loop.

    Pass true_from=float('inf') for a predicate that is never satisfied.
    """
    calls = []

    def predicate(n):
        calls.append(n)
        if len(calls) > max_calls:
            raise AssertionError(
                f"predicate called {len(calls)} times — infinite loop in the search?")
        return n >= true_from

    return (predicate, calls)


# --- unit tests for the pure binary search ---

class TestMinPrefixSatisfying:

    def test_threshold_in_middle(self):
        (pred, _) = threshold_predicate(6)
        assert min_prefix_satisfying(pred, 10, 3) == 6

    def test_answer_is_one(self):
        (pred, _) = threshold_predicate(1)
        assert min_prefix_satisfying(pred, 10, 5) == 1

    def test_answer_is_n_total(self):
        (pred, _) = threshold_predicate(10)
        assert min_prefix_satisfying(pred, 10, 5) == 10

    def test_never_satisfied_returns_none(self):
        (pred, _) = threshold_predicate(float('inf'))
        assert min_prefix_satisfying(pred, 10, 3) is None

    def test_regression_bankers_rounding_answer_1(self):
        # Regression for the round() bug: with min=1, max=2, the old
        # round((1+2)/2) gave 2 forever (banker's rounding), so the search
        # never probed n=1. The threshold_predicate max_calls guard turns
        # that infinite loop into a fast failure.
        (pred, _) = threshold_predicate(1)
        assert min_prefix_satisfying(pred, 2, 2) == 1

    def test_regression_bankers_rounding_answer_2(self):
        # Companion case: the answer really is 2, so returning 2 is correct.
        (pred, _) = threshold_predicate(2)
        assert min_prefix_satisfying(pred, 2, 2) == 2

    def test_initial_guess_below_range_is_clamped(self):
        (pred, calls) = threshold_predicate(3)
        assert min_prefix_satisfying(pred, 10, 0) == 3
        assert all(1 <= n <= 10 for n in calls)

    def test_initial_guess_above_range_is_clamped(self):
        (pred, calls) = threshold_predicate(3)
        assert min_prefix_satisfying(pred, 5, 99) == 3
        assert all(1 <= n <= 5 for n in calls)

    def test_n_total_one_satisfied(self):
        (pred, _) = threshold_predicate(1)
        assert min_prefix_satisfying(pred, 1, 1) == 1

    def test_n_total_one_not_satisfied(self):
        (pred, _) = threshold_predicate(float('inf'))
        assert min_prefix_satisfying(pred, 1, 1) is None

    def test_n_total_zero_returns_none(self):
        (pred, calls) = threshold_predicate(1)
        assert min_prefix_satisfying(pred, 0, 1) is None
        assert calls == []  # nothing to probe

    def test_exhaustive_sweep_small_range(self):
        # For every threshold and every initial guess in a small range,
        # the search must find exactly the threshold. Catches off-by-one
        # errors at every boundary.
        n_total = 7
        for true_from in range(1, n_total + 1):
            for guess in range(1, n_total + 1):
                (pred, _) = threshold_predicate(true_from)
                result = min_prefix_satisfying(pred, n_total, guess)
                assert result == true_from, \
                    f"true_from={true_from}, guess={guess}: got {result}"

    def test_call_count_is_logarithmic(self):
        # Binary search over 1000 should take ~log2(1000) ≈ 10 probes,
        # not ~1000. Allow slack for the initial guess and boundary probes.
        (pred, calls) = threshold_predicate(700, max_calls=1000)
        assert min_prefix_satisfying(pred, 1000, 300) == 700
        assert len(calls) <= 15, f"took {len(calls)} probes: {calls}"


# --- integration tests: cut_clues with the real solver on a cube ---

# Vertex IDs of the cube's bottom face cycle, used as the known solution loop.
BOTTOM_LOOP = [0, 3, 2, 1]


def loop_edges(loop):
    """The edge set of a vertex loop, as frozensets for order independence."""
    n = len(loop)
    return {frozenset((loop[i], loop[(i + 1) % n])) for i in range(n)}


def num_walls_by_face(mesh, loop):
    """Map each face key to its num_walls: how many of its edges lie on the loop."""
    edges = loop_edges(loop)
    return {fkey: sum(1 for e in mesh.face_halfedges(fkey) if frozenset(e) in edges)
            for fkey in mesh.faces()}


@pytest.fixture
def cube():
    """Same cube as in test_slisolver.py: 8 vertices, 6 quad faces, 12 edges.

    Face keys: 0=bottom, 1=top, 2=front, 3=right, 4=back, 5=left.
    """
    vertices = [
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
    ]
    faces = [
        [0, 3, 2, 1],   # bottom (outward normal -z)
        [4, 5, 6, 7],   # top    (+z)
        [0, 1, 5, 4],   # front  (-y)
        [1, 2, 6, 5],   # right  (+x)
        [2, 3, 7, 6],   # back   (+y)
        [3, 0, 4, 7],   # left   (-x)
    ]
    return Mesh.from_vertices_and_faces(vertices, faces)


def dual_graph(mesh):
    """The face-adjacency graph RegionColoring needs alongside the mesh."""
    import networkx as nx
    dualG = nx.Graph()
    for f in mesh.faces():
        dualG.add_node(f)
        for nbr in mesh.face_neighbors(f):
            dualG.add_edge(f, nbr)
    return dualG


class TestRegionColoring:
    """The face counts are derived from the mesh, not tallied as faces are
    painted. These are the regressions for the two ways the old module-global
    tallies went wrong."""

    @pytest.fixture
    def coloring(self, cube):
        return RegionColoring(cube, dual_graph(cube))

    def test_repainting_a_face_does_not_double_count(self, coloring, cube):
        """Painting a red face blue used to add to blue without taking anything
        off red, so the counts drifted above the number of faces."""
        for fkey in cube.faces():
            coloring.paint_face(fkey, red)
        assert (coloring.count(red), coloring.count(blue)) == (6, 0)

        coloring.paint_face(0, blue)
        assert (coloring.count(red), coloring.count(blue)) == (5, 1)
        assert coloring.count(red) + coloring.count(blue) == cube.number_of_faces()

    def test_randomizing_again_does_not_accumulate(self, coloring, cube):
        """randomize_face_colors used to add to the counts without resetting
        them, so a second attempt started with the first attempt's totals still
        in place -- and after a few attempts the counts exceeded num_faces,
        which is what silently switched adjust_populations off."""
        for _ in range(3):
            coloring.randomize_face_colors()
            assert (coloring.count(red) + coloring.count(blue)
                    == cube.number_of_faces())

    def test_adjust_populations_tops_up_the_missing_color(self, coloring, cube):
        """The one thing that reads the counts: with no blue faces at all, it
        must paint some blue. This is what stopped happening once the counts
        inflated past num_faces / 3."""
        for fkey in cube.faces():
            coloring.paint_face(fkey, red)
        coloring.adjust_populations()
        assert coloring.count(blue) == round(cube.number_of_faces() / 3)

    def test_paint_random_faces_paints_that_many_distinct_faces(self, coloring, cube):
        for fkey in cube.faces():
            coloring.paint_face(fkey, blue)
        coloring.paint_random_faces(red, 4)
        assert coloring.count(red) == 4
        assert coloring.count(blue) == cube.number_of_faces() - 4

    def test_paint_random_faces_skips_faces_already_that_color(self, coloring, cube):
        """The candidates are the faces NOT already this color, so asking for two
        more reds when four faces are red leaves six red, not two."""
        for fkey in [0, 1, 2, 3]:
            coloring.paint_face(fkey, red)
        for fkey in [4, 5]:
            coloring.paint_face(fkey, blue)
        coloring.paint_random_faces(red, 2)
        assert coloring.count(red) == 6

    def test_paint_random_faces_clamps_to_what_is_available(self, coloring, cube):
        """Asking for more than exist used to spin forever looking for a
        candidate that could never turn up."""
        coloring.paint_random_faces(red, 99)
        assert coloring.count(red) == cube.number_of_faces()

    def test_paint_random_faces_ignores_nonpositive_counts(self, coloring, cube):
        for fkey in cube.faces():
            coloring.paint_face(fkey, blue)
        coloring.paint_random_faces(red, 0)
        coloring.paint_random_faces(red, -3)
        assert coloring.count(red) == 0

    def test_painting_flags_the_other_color_for_a_check(self, coloring):
        """Painting a face red can disconnect the blue region, so it's blue that
        needs re-checking, and vice versa."""
        coloring.paint_face(0, red)
        assert (coloring.blue_needs_check, coloring.red_needs_check) == (True, False)

        coloring2 = RegionColoring(coloring.mesh, coloring.dualG)
        coloring2.paint_face(0, blue)
        assert (coloring2.red_needs_check, coloring2.blue_needs_check) == (True, False)


class TestDuplicateRejection:
    """Puzzles must differ as the PLAYER sees them, which means up to rotation
    and reflection -- they can turn the solid over. Comparing clue lists face by
    face isn't enough, and data/ shipped such pairs before this: all three
    tetrahedron puzzles were one puzzle, and two of the cube's three matched."""

    @pytest.fixture(autouse=True)
    def cube_as_the_current_grid(self, cube, monkeypatch):
        """The dedupe helpers read the module's mesh and output, so point both at
        a cube with no puzzles recorded yet."""
        monkeypatch.setattr(genSliPuzzles, 'mesh', cube)
        monkeypatch.setattr(genSliPuzzles, 'symmetries_cache', None)
        monkeypatch.setattr(genSliPuzzles, 'puzzles_output', {'puzzles': []})

    def test_finds_the_cubes_48_symmetries(self):
        """24 rotations, doubled by reflections."""
        assert len(genSliPuzzles.face_symmetries()) == 48

    def test_a_rotated_puzzle_counts_as_the_same_one(self):
        """Clue 2 on the bottom, clue 1 on the top, versus the same pair on the
        front and back: a quarter turn carries one onto the other."""
        bottom_and_top = [2, 1, -1, -1, -1, -1]
        front_and_back = [-1, -1, 2, -1, 1, -1]
        assert genSliPuzzles.same_puzzle_up_to_symmetry(bottom_and_top,
                                                        front_and_back)

    def test_adjacent_and_opposite_placements_are_different_puzzles(self):
        """Clue 2 and clue 1 on OPPOSITE faces, versus on ADJACENT faces. No
        symmetry maps an opposite pair to an adjacent one, so these are two
        puzzles -- and they share a clue census, which is exactly the case the
        census test alone would get wrong."""
        opposite = [2, 1, -1, -1, -1, -1]     # bottom and top
        adjacent = [2, -1, 1, -1, -1, -1]     # bottom and front
        assert (genSliPuzzles.clue_census(opposite)
                == genSliPuzzles.clue_census(adjacent))
        assert not genSliPuzzles.same_puzzle_up_to_symmetry(opposite, adjacent)

    def test_already_generated_rejects_a_rotation_of_a_kept_puzzle(self):
        genSliPuzzles.puzzles_output['puzzles'].append(
            {'clues': [2, 1, -1, -1, -1, -1], 'solution': [0, 1, 2, 3]})
        assert genSliPuzzles.already_generated([-1, -1, 2, -1, 1, -1]) is True

    def test_already_generated_accepts_a_genuinely_new_puzzle(self):
        genSliPuzzles.puzzles_output['puzzles'].append(
            {'clues': [2, 1, -1, -1, -1, -1], 'solution': [0, 1, 2, 3]})
        assert genSliPuzzles.already_generated([2, -1, 1, -1, -1, -1]) is False

    def test_a_differing_census_skips_the_symmetry_scan(self, monkeypatch):
        """The census is the cheap pre-filter: when it differs, no symmetry could
        relate the two, so the group is never even computed."""
        genSliPuzzles.puzzles_output['puzzles'].append(
            {'clues': [2, 1, -1, -1, -1, -1], 'solution': [0, 1, 2, 3]})

        def fail_if_called():
            raise AssertionError("should not need the symmetry group here")
        monkeypatch.setattr(genSliPuzzles, 'face_symmetries', fail_if_called)

        assert genSliPuzzles.already_generated([3, 3, 3, -1, -1, -1]) is False


class TestBackendCanDisplay:
    """What gates the progress redraws. Getting this wrong either wastes most of
    a headless run's time (the reason for the gate) or silently kills the
    animation when someone runs the generator directly to watch it."""

    @pytest.mark.parametrize("backend, expected", [
        ("Agg", False),
        ("agg", False),        # matplotlib reports capitalized; don't rely on it
        ("pdf", False),
        ("svg", False),
        ("template", False),
        ("TkAgg", True),
        ("QtAgg", True),
        ("MacOSX", True),
    ])
    def test_recognizes_which_backends_can_show_a_figure(self, backend, expected,
                                                         monkeypatch):
        monkeypatch.setattr(genSliPuzzles.plt, 'get_backend', lambda: backend)
        assert genSliPuzzles.backend_can_display() is expected

    def test_update_display_does_nothing_when_the_display_is_dead(self, cube,
                                                                  monkeypatch):
        """It must not even touch `poly`, which is None until setup_display runs
        -- so a run that never sets up a figure can still call this freely."""
        monkeypatch.setattr(genSliPuzzles, 'DISPLAY_IS_LIVE', False)
        monkeypatch.setattr(genSliPuzzles, 'poly', None)
        genSliPuzzles.update_display(cube)   # would raise if it drew anything


class TestCutClues:

    @pytest.fixture
    def cube_with_bottom_loop(self, cube):
        """The cube, with the bottom-face loop as the established solution.

        Nothing to set up beyond the mesh itself: cut_clues takes it as an
        argument. This fixture used to monkeypatch four module globals
        (mesh, dualG, num_faces, solution) to stand in for a generator run."""
        return cube

    def test_num_walls_fixture_sanity(self, cube):
        # Verify our helper before trusting it: for the bottom loop,
        # bottom face has all 4 edges filled, top has 0, sides have 1 each.
        walls = num_walls_by_face(cube, BOTTOM_LOOP)
        assert walls == {0: 4, 1: 0, 2: 1, 3: 1, 4: 1, 5: 1}

    def test_high_info_ordering_needs_two_clues(self, cube_with_bottom_loop):
        """Bottom clue (4) first, top clue (0) second: two clues.

        The bottom's clue 4 forces all four bottom edges, and the vertex rule
        then rules out the verticals — but that leaves the four top edges
        undecided. Ruling them out needs "there must be only ONE loop", which
        none of our propagation rules encode yet: the solver only checks it in
        is_valid_loop, once an assignment is complete. Players DO reason with
        it ("filling that would close the loop early, leaving clues
        unsatisfied, so it must be ruled out"), so this is a gap in our rule
        set rather than a fact that is off-limits — see the TODO about adding
        it as a rule. For now the top's clue 0 settles those edges directly,
        so the answer is 2.

        Under the older, uniqueness-only test this ordering needed just 1
        clue: the two-loop alternative was eliminated by is_valid_loop at the
        end of a search, not by deduction. That is the difference this change
        is about.
        """
        walls = num_walls_by_face(cube_with_bottom_loop, BOTTOM_LOOP)
        ordering = [(f, walls[f]) for f in [0, 1, 2, 3, 4, 5]]
        assert cut_clues(cube_with_bottom_loop, ordering) == 2

    def test_result_is_deducible_and_minimal(self, cube_with_bottom_loop):
        """Whatever count cut_clues returns, that prefix must be solvable by
        deduction and the one below it must not be. Stated as a property so it
        survives future changes to the rule set."""
        walls = num_walls_by_face(cube_with_bottom_loop, BOTTOM_LOOP)
        ordering = [(f, walls[f]) for f in [0, 1, 2, 3, 4, 5]]
        needed = cut_clues(cube_with_bottom_loop, ordering)

        assert solvable_by_deduction(cube_with_bottom_loop, ordering, needed,
                                     depth=LOOKAHEAD_DEPTH) is True
        assert solvable_by_deduction(cube_with_bottom_loop, ordering, needed - 1,
                                     depth=LOOKAHEAD_DEPTH) is False

    def test_low_info_ordering_needs_five_clues(self, cube_with_bottom_loop):
        # Side faces first (each clue 1), then bottom (4), then top (0).
        # No prefix of side clues alone gets anywhere: the top loop and the
        # bottom loop both give every side face exactly 1 filled edge, so
        # nothing distinguishes them. The bottom clue (5th) is what makes the
        # position deducible, so the minimum is 5.
        walls = num_walls_by_face(cube_with_bottom_loop, BOTTOM_LOOP)
        ordering = [(f, walls[f]) for f in [2, 3, 4, 5, 0, 1]]
        assert cut_clues(cube_with_bottom_loop, ordering) == 5
