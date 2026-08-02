"""Tests for genSliPuzzles.py — currently the clue-minimization workflow.

Strategy:
    min_prefix_satisfying() is a pure function, so we unit-test it with
    fake predicates (no solver, no mesh). cut_clues() reads module-level
    globals (mesh, solution, num_faces, dualG), so the integration tests
    point those globals at a small cube via monkeypatch, then run the
    real solver.
"""
import os

# Select a non-interactive matplotlib backend BEFORE importing genSliPuzzles
# (which imports matplotlib.pyplot), so the tests can't try to open a GUI
# window, e.g. when run headless.
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest
from compas.datastructures import Mesh

import genSliPuzzles
from genSliPuzzles import LOOKAHEAD_DEPTH, cut_clues, min_prefix_satisfying
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


class TestCutClues:

    @pytest.fixture
    def cube(self):
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

    @pytest.fixture
    def cube_with_bottom_loop(self, cube, monkeypatch):
        """Point genSliPuzzles' module globals at the cube, with the
        bottom-face loop as the established solution. monkeypatch restores
        the globals after each test."""
        monkeypatch.setattr(genSliPuzzles, 'mesh', cube)
        monkeypatch.setattr(genSliPuzzles, 'dualG', None)  # unused by the solver
        monkeypatch.setattr(genSliPuzzles, 'num_faces', cube.number_of_faces())
        monkeypatch.setattr(genSliPuzzles, 'solution', BOTTOM_LOOP)
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
        assert cut_clues(ordering) == 2

    def test_result_is_deducible_and_minimal(self, cube_with_bottom_loop):
        """Whatever count cut_clues returns, that prefix must be solvable by
        deduction and the one below it must not be. Stated as a property so it
        survives future changes to the rule set."""
        walls = num_walls_by_face(cube_with_bottom_loop, BOTTOM_LOOP)
        ordering = [(f, walls[f]) for f in [0, 1, 2, 3, 4, 5]]
        needed = cut_clues(ordering)

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
        assert cut_clues(ordering) == 5
