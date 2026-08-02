"""Unit tests for slisolver.py.

Strategy:
    Build small known meshes (a cube, an octahedron) once per test via
    fixtures. Each test sets up edge guesses or face clues directly, then
    invokes the function under test.
"""
import json
import time
from pathlib import Path

import pytest
from compas.datastructures import Mesh

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from slisolver import (
    FaceColoring,
    apply_clue_rules,
    apply_clues,
    apply_color_rules,
    apply_pattern_rules,
    apply_vertex_rules,
    is_complete_solution,
    is_valid_loop,
    propagate_constraints,
    restore_state,
    save_state,
    select_edge_for_branching,
    solution_is_unique,
)


# --- fixtures ---

@pytest.fixture
def cube():
    """Unit cube: 8 vertices, 6 quad faces, 12 edges.

    Vertex layout:
        bottom (z=0): 0,1,2,3 going CCW from origin
        top    (z=1): 4,5,6,7 directly above
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
def dodecahedron():
    """Regular dodecahedron loaded from data/D.json: 20 vertices,
    12 pentagonal faces, 30 edges. Each vertex has degree 3."""
    grid = json.loads((REPO_ROOT / 'data' / 'D.json').read_text())
    return Mesh.from_vertices_and_faces(grid['vertices'], grid['faces'])


@pytest.fixture
def dodec_puzzle():
    """Hand-crafted puzzle from data/D-puzzles.json, as (clues, solution).

    clues is in (face, num_walls) tuple form ready for apply_clues.
    """
    data = json.loads((REPO_ROOT / 'data' / 'D-puzzles.json').read_text())
    p = data['puzzles'][0]
    clues = [(face, n) for face, n in enumerate(p['clues']) if n != -1]
    return clues, p['solution']


@pytest.fixture
def octahedron():
    """Octahedron: 6 vertices, 8 triangle faces, 12 edges.

    Vertex 0 = north pole, 1 = south pole, 2-5 = equator (CCW from +x).
    Each polar vertex has degree 4; each equatorial vertex has degree 4
    (2 polar edges + 2 equator edges).
    """
    vertices = [
        [0,  0,  1],  # 0: north pole
        [0,  0, -1],  # 1: south pole
        [1,  0,  0],  # 2
        [0,  1,  0],  # 3
        [-1, 0,  0],  # 4
        [0, -1,  0],  # 5
    ]
    faces = [
        [0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 2],   # northern triangles
        [1, 3, 2], [1, 4, 3], [1, 5, 4], [1, 2, 5],   # southern triangles
    ]
    return Mesh.from_vertices_and_faces(vertices, faces)


# --- helper ---

def fill(mesh, edge_endpoints):
    """Set 'guess' to 'filledIn' for the given edges, 'unknown' for the rest.

    `edge_endpoints` is an iterable of (u, v) pairs. Order within a pair
    doesn't matter — we compare against canonical edge keys via frozenset.
    """
    # frozenset() gives us order independence for the comparison.
    # So frozenset((0, 1)) is the same as frozenset((1, 0)).
    target = {frozenset(p) for p in edge_endpoints}
    for ekey in mesh.edges():
        guess = 'filledIn' if frozenset(ekey) in target else 'unknown'
        mesh.edge_attribute(ekey, 'guess', guess)


def set_edge(mesh, v1, v2, guess):
    """Set one edge's 'guess' to any of the three states.

    Vertex order doesn't matter: COMPAS keeps edge attributes per *undirected*
    edge (locked in by test_edge_attribute_is_orientation_independent).
    """
    mesh.edge_attribute((v1, v2), 'guess', guess)


def guess_of(mesh, v1, v2):
    """Read one edge's 'guess'. Vertex order doesn't matter (see set_edge)."""
    return mesh.edge_attribute((v1, v2), 'guess')


# --- fixture sanity tests ---
# These verify the fixtures and `fill` helper themselves before we trust
# them in the is_valid_loop tests. If is_valid_loop tests fail but these
# pass, the bug is in slisolver. If these fail, the bug is in the fixture
# or in fill.

class TestFixtureSanity:
    def test_cube_has_12_edges(self, cube):
        assert sum(1 for _ in cube.edges()) == 12

    def test_cube_has_8_vertices(self, cube):
        assert sum(1 for _ in cube.vertices()) == 8

    def test_octahedron_has_12_edges(self, octahedron):
        assert sum(1 for _ in octahedron.edges()) == 12

    def test_octahedron_has_6_vertices(self, octahedron):
        assert sum(1 for _ in octahedron.vertices()) == 6

    def test_cube_edge_keys_are_2_tuples_of_ints(self, cube):
        for ekey in cube.edges():
            assert isinstance(ekey, tuple), f"ekey {ekey!r} is {type(ekey).__name__}"
            assert len(ekey) == 2
            for v in ekey:
                assert isinstance(v, int), f"vertex key {v!r} is {type(v).__name__}"

    def test_cube_has_edge_between_0_and_1(self, cube):
        edge_set = {frozenset(e) for e in cube.edges()}
        assert frozenset({0, 1}) in edge_set

    def test_cube_has_all_bottom_face_edges(self, cube):
        edge_set = {frozenset(e) for e in cube.edges()}
        for pair in [(0, 1), (1, 2), (2, 3), (3, 0)]:
            assert frozenset(pair) in edge_set, f"missing edge {pair}"

    def test_fill_marks_exactly_the_given_edges(self, cube):
        # Critical: this verifies our setter/getter round-trip.
        target_pairs = [(0, 1), (1, 2), (2, 3), (3, 0)]
        fill(cube, target_pairs)
        filled = [e for e in cube.edges()
                  if cube.edge_attribute(e, 'guess') == 'filledIn']
        target_set = {frozenset(p) for p in target_pairs}
        filled_set = {frozenset(e) for e in filled}
        assert len(filled) == 4, f"got {len(filled)} filled, expected 4: {filled}"
        assert filled_set == target_set, f"filled {filled_set} != target {target_set}"

    def test_fill_clears_unfilled_edges(self, cube):
        fill(cube, [(0, 1), (1, 2), (2, 3), (3, 0)])
        unknown = [e for e in cube.edges()
                   if cube.edge_attribute(e, 'guess') == 'unknown']
        assert len(unknown) == 8

    def test_full_inline_walk_for_4_cycle(self, cube):
        """Mirror the entire is_valid_loop body inline.

        If this passes but TestIsValidLoop.test_4_cycle_around_cube_face
        fails on the same input, slisolver.py is not the version we think.
        """
        fill(cube, [(0, 1), (1, 2), (2, 3), (3, 0)])

        adj = {}
        for ekey in cube.edges():
            if cube.edge_attribute(ekey, 'guess') == 'filledIn':
                (v1, v2) = ekey
                adj.setdefault(v1, []).append(v2)
                adj.setdefault(v2, []).append(v1)

        assert adj, "no filled edges seen"
        assert all(len(n) == 2 for n in adj.values()), f"degree check: {adj}"

        start = next(iter(adj))
        cur = start
        prev = None
        steps = 0
        path = [start]
        while cur != start or prev is None:
            (a, b) = adj[cur]
            nxt = a if a != prev else b
            prev = cur
            cur = nxt
            path.append(cur)
            steps += 1

        assert steps == len(adj), (
            f"walk took {steps} steps, len(adj)={len(adj)}; "
            f"path={path}, adj={adj}"
        )

        # And finally: confirm the actual function agrees on the same input.
        assert is_valid_loop(cube) is True, (
            f"inline walk says True, but is_valid_loop says False. "
            f"adj={adj}, path={path}"
        )

    def test_replicate_is_valid_loop_first_stage(self, cube):
        # Mirror the first part of is_valid_loop: build adj from filledIn
        # edges, check that we get 4 vertices each with 2 neighbors.
        # If this passes but is_valid_loop returns False, the walk has the bug.
        fill(cube, [(0, 1), (1, 2), (2, 3), (3, 0)])
        adj = {}
        for ekey in cube.edges():
            if cube.edge_attribute(ekey, 'guess') == 'filledIn':
                (v1, v2) = ekey
                adj.setdefault(v1, []).append(v2)
                adj.setdefault(v2, []).append(v1)
        assert set(adj.keys()) == {0, 1, 2, 3}, f"adj keys: {sorted(adj.keys())}"
        for v, nbrs in adj.items():
            assert len(nbrs) == 2, f"vertex {v} -> {nbrs} (degree {len(nbrs)})"
            assert set(nbrs) <= {0, 1, 2, 3}, f"vertex {v} -> {nbrs}"

    def test_edge_attribute_is_orientation_independent(self, cube):
        # Locks in the assumption that COMPAS stores edge attributes per
        # *undirected* edge: writing via one orientation must be visible
        # when reading via the other. apply_clue_rules relies on this
        # because face_halfedges yields directed pairs that may not match
        # the canonical edges in mesh.edges().
        cube.edge_attribute((0, 1), 'guess', 'filledIn')
        assert cube.edge_attribute((1, 0), 'guess') == 'filledIn'
        cube.edge_attribute((1, 0), 'guess', 'ruledOut')
        assert cube.edge_attribute((0, 1), 'guess') == 'ruledOut'

    def test_face_halfedges_covers_all_face_edges(self, cube):
        # Face 0 = [0, 3, 2, 1], so its 4 edges are (0,3), (3,2), (2,1), (1,0).
        expected = {frozenset(p) for p in [(0, 3), (3, 2), (2, 1), (1, 0)]}
        actual = {frozenset(h) for h in cube.face_halfedges(0)}
        assert actual == expected


# --- tests ---

class TestIsValidLoop:
    def test_no_filled_edges(self, cube):
        # Early return: `if not adj`.
        fill(cube, [])
        assert is_valid_loop(cube) is False

    def test_single_edge_has_degree_1_endpoints(self, cube):
        # degree(0) = degree(1) = 1; fails the degree check.
        fill(cube, [(0, 1)])
        assert is_valid_loop(cube) is False

    def test_two_edge_path(self, cube):
        # 0-1-2: degree(0)=1, degree(1)=2, degree(2)=1; fails degree check.
        fill(cube, [(0, 1), (1, 2)])
        assert is_valid_loop(cube) is False

    def test_4_cycle_around_cube_face(self, cube):
        # The simplest valid loop: bottom face boundary.
        fill(cube, [(0, 1), (1, 2), (2, 3), (3, 0)])
        assert is_valid_loop(cube) is True

    def test_two_disjoint_4_cycles(self, cube):
        # Top and bottom face boundaries — same shape, no shared vertices.
        # All degrees are 2 (degree check passes), but the walk only
        # traverses one cycle and returns early.
        fill(cube, [(0, 1), (1, 2), (2, 3), (3, 0),
                    (4, 5), (5, 6), (6, 7), (7, 4)])
        assert is_valid_loop(cube) is False

    def test_triangle_on_octahedron(self, octahedron):
        # Smallest possible valid loop: one triangular face.
        fill(octahedron, [(0, 2), (2, 3), (0, 3)])
        assert is_valid_loop(octahedron) is True

    def test_two_disjoint_triangles_on_octahedron(self, octahedron):
        # A north face and a south face that share no vertices.
        fill(octahedron, [(0, 2), (2, 3), (0, 3),
                          (1, 4), (4, 5), (1, 5)])
        assert is_valid_loop(octahedron) is False

    def test_figure_eight_at_polar_vertex(self, octahedron):
        # Two triangles sharing vertex 0 (the north pole).
        # Vertex 0 has degree 4 in the filled subgraph -> degree check fails.
        fill(octahedron, [(0, 2), (0, 3), (2, 3),
                          (0, 4), (0, 5), (4, 5)])
        assert is_valid_loop(octahedron) is False

    def test_6_cycle_on_cube(self, cube):
        # A "Hamiltonian-like" 6-cycle that's not a face boundary, exercising
        # the walk over more than one face's worth of edges.
        # Path: 0-1-5-6-7-4-0 (a hexagonal slice).
        fill(cube, [(0, 1), (1, 5), (5, 6), (6, 7), (7, 4), (4, 0)])
        assert is_valid_loop(cube) is True


# --- helpers for the next set of tests ---

def set_all_edges(mesh, guess):
    """Set every edge's 'guess' attribute to the given value."""
    for ekey in mesh.edges():
        mesh.edge_attribute(ekey, 'guess', guess)


# --- is_complete_solution ---

class TestIsCompleteSolution:
    def test_all_unknown_returns_false(self, cube):
        set_all_edges(cube, 'unknown')
        assert is_complete_solution(cube) is False

    def test_all_filled_in_returns_true(self, cube):
        set_all_edges(cube, 'filledIn')
        assert is_complete_solution(cube) is True

    def test_all_ruled_out_returns_true(self, cube):
        set_all_edges(cube, 'ruledOut')
        assert is_complete_solution(cube) is True

    def test_mix_of_filled_and_ruled_out_returns_true(self, cube):
        for i, ekey in enumerate(cube.edges()):
            cube.edge_attribute(ekey, 'guess',
                                'filledIn' if i % 2 == 0 else 'ruledOut')
        assert is_complete_solution(cube) is True

    def test_one_unknown_among_otherwise_complete_returns_false(self, cube):
        # The typical near-complete state during DFS — worth its own case.
        set_all_edges(cube, 'filledIn')
        target = next(iter(cube.edges()))
        cube.edge_attribute(target, 'guess', 'unknown')
        assert is_complete_solution(cube) is False


# --- save_state / restore_state ---

class TestSaveRestoreState:
    def test_round_trip_preserves_all_edges(self, cube):
        # Set a deterministic mix using the three legal values.
        guess_cycle = ['unknown', 'filledIn', 'ruledOut']
        original = {}
        for i, ekey in enumerate(cube.edges()):
            g = guess_cycle[i % 3]
            cube.edge_attribute(ekey, 'guess', g)
            original[ekey] = g

        saved = save_state(cube)

        # Trash everything.
        set_all_edges(cube, 'unknown')

        restore_state(cube, saved)

        for ekey, expected in original.items():
            assert cube.edge_attribute(ekey, 'guess') == expected, (
                f"edge {ekey}: expected {expected}, "
                f"got {cube.edge_attribute(ekey, 'guess')}"
            )

    def test_save_state_length_matches_edge_count(self, cube):
        set_all_edges(cube, 'unknown')
        # Materialize via list() so this works whether save_state returns
        # a list or a generator.
        state = list(save_state(cube))
        assert len(state) == sum(1 for _ in cube.edges())

    def test_edge_iteration_is_order_stable_across_calls(self, cube):
        # restore_state's correctness depends on this. If COMPAS ever made
        # mesh.edges() non-deterministic, restore_state would silently
        # scramble edge attributes (zip pairs the i-th saved value with
        # the i-th edge in iteration order).
        order_a = list(cube.edges())
        order_b = list(cube.edges())
        assert order_a == order_b


# --- apply_clues ---

class TestApplyClues:
    def test_empty_clues_clears_all_faces(self, cube):
        # Pre-set clues so we can verify they're cleared.
        for fkey in cube.faces():
            cube.face_attribute(fkey, 'clue', 99)

        apply_clues([], 0, cube)

        for fkey in cube.faces():
            assert cube.face_attribute(fkey, 'clue') is None

    def test_partial_application_uses_only_first_n(self, cube):
        clues = [(0, 1), (1, 2), (2, 3)]
        apply_clues(clues, 2, cube)

        assert cube.face_attribute(0, 'clue') == 1
        assert cube.face_attribute(1, 'clue') == 2
        # Face 2 was in the list but past num_clues; should remain unset.
        assert cube.face_attribute(2, 'clue') is None
        # Other faces also unset.
        for fkey in (3, 4, 5):
            assert cube.face_attribute(fkey, 'clue') is None

    def test_reapplication_clears_previous_clues(self, cube):
        # First call sets faces 0,1,2.
        apply_clues([(0, 5), (1, 3), (2, 4)], 3, cube)
        # Second call only sets face 0; faces 1 and 2 must be cleared.
        apply_clues([(0, 1)], 1, cube)

        assert cube.face_attribute(0, 'clue') == 1
        assert cube.face_attribute(1, 'clue') is None
        assert cube.face_attribute(2, 'clue') is None

    def test_num_clues_exceeds_list_length_does_not_error(self, cube):
        # itertools.islice silently truncates; we lock in that behavior.
        apply_clues([(0, 1)], 5, cube)
        assert cube.face_attribute(0, 'clue') == 1


# --- select_edge_for_branching ---

class TestSelectEdgeForBranching:
    def test_returns_unknown_edge_when_some_exist(self, cube):
        set_all_edges(cube, 'filledIn')
        # Mark a single edge as unknown; the result should be that edge
        # (or, more loosely, any edge whose guess is 'unknown').
        target = list(cube.edges())[5]
        cube.edge_attribute(target, 'guess', 'unknown')

        result = select_edge_for_branching(cube)
        assert result is not None
        assert cube.edge_attribute(result, 'guess') == 'unknown'

    def test_returns_none_when_no_unknown_edges(self, cube):
        set_all_edges(cube, 'filledIn')
        assert select_edge_for_branching(cube) is None

    def test_returns_unknown_when_all_unknown(self, cube):
        set_all_edges(cube, 'unknown')
        result = select_edge_for_branching(cube)
        assert result is not None
        assert cube.edge_attribute(result, 'guess') == 'unknown'

    def test_returns_specific_edge_when_only_one_is_unknown(self, cube):
        # When exactly one edge is unknown, the contract pins down the
        # answer — there's no other valid choice.
        set_all_edges(cube, 'ruledOut')
        target = list(cube.edges())[3]
        cube.edge_attribute(target, 'guess', 'unknown')

        result = select_edge_for_branching(cube)
        assert result == target


# --- apply_vertex_rules ---

class TestApplyVertexRules:
    """Each test sets vertex 0's three incident edges (to neighbors 1, 3, 4)
    to specific guesses, leaves all other edges 'unknown', and asserts what
    apply_vertex_rules infers. Other vertices stay in states (f<=1, u>=2)
    where no rule fires, so they don't interfere.
    """

    @staticmethod
    def _setup_v0(cube, e01, e03, e04):
        for ekey in cube.edges():
            cube.edge_attribute(ekey, 'guess', 'unknown')
        cube.edge_attribute((0, 1), 'guess', e01)
        cube.edge_attribute((0, 3), 'guess', e03)
        cube.edge_attribute((0, 4), 'guess', e04)

    def test_f2_u1_rules_out_unknown(self, cube):
        self._setup_v0(cube, 'filledIn', 'filledIn', 'unknown')
        (ok, changed) = apply_vertex_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((0, 4), 'guess') == 'ruledOut'

    def test_f1_u1_fills_unknown(self, cube):
        self._setup_v0(cube, 'filledIn', 'ruledOut', 'unknown')
        (ok, changed) = apply_vertex_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((0, 4), 'guess') == 'filledIn'

    def test_f0_u1_rules_out_unknown(self, cube):
        self._setup_v0(cube, 'ruledOut', 'ruledOut', 'unknown')
        (ok, changed) = apply_vertex_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((0, 4), 'guess') == 'ruledOut'

    def test_f2_u0_no_change(self, cube):
        self._setup_v0(cube, 'filledIn', 'filledIn', 'ruledOut')
        (ok, changed) = apply_vertex_rules(cube)
        assert ok is True
        assert changed is False
        # State preserved.
        assert cube.edge_attribute((0, 1), 'guess') == 'filledIn'
        assert cube.edge_attribute((0, 3), 'guess') == 'filledIn'
        assert cube.edge_attribute((0, 4), 'guess') == 'ruledOut'

    def test_all_unknown_no_inference(self, cube):
        for ekey in cube.edges():
            cube.edge_attribute(ekey, 'guess', 'unknown')
        (ok, changed) = apply_vertex_rules(cube)
        assert ok is True
        assert changed is False

    def test_f1_u2_no_inference(self, cube):
        self._setup_v0(cube, 'filledIn', 'unknown', 'unknown')
        (ok, changed) = apply_vertex_rules(cube)
        assert ok is True
        assert changed is False
        # The two unknowns at vertex 0 stay unknown.
        assert cube.edge_attribute((0, 3), 'guess') == 'unknown'
        assert cube.edge_attribute((0, 4), 'guess') == 'unknown'

    def test_f3_contradiction(self, cube):
        self._setup_v0(cube, 'filledIn', 'filledIn', 'filledIn')
        (ok, _) = apply_vertex_rules(cube)
        assert ok is False

    def test_f1_u0_contradiction(self, cube):
        self._setup_v0(cube, 'filledIn', 'ruledOut', 'ruledOut')
        (ok, _) = apply_vertex_rules(cube)
        assert ok is False


# --- apply_clue_rules ---

class TestApplyClueRules:
    """Each test sets a clue on cube face 0 (bottom, edges (0,3) (3,2)
    (2,1) (1,0)), sets those edges' guesses, and asserts what
    apply_clue_rules infers. Faces 1-5 have no clue, so they're skipped.
    """

    # In face_halfedges order for face [0, 3, 2, 1]:
    FACE0_EDGES = [(0, 3), (3, 2), (2, 1), (1, 0)]

    # Compact aliases for readability in test bodies.
    F = 'filledIn'
    R = 'ruledOut'
    U = 'unknown'

    @staticmethod
    def _setup(cube, clue, edge_states):
        """Reset all edges to 'unknown', set face-0 edges to the given
        states, and (optionally) set face 0's clue. clue=None leaves the
        face unclued."""
        for ekey in cube.edges():
            cube.edge_attribute(ekey, 'guess', 'unknown')
        for ekey, state in zip(TestApplyClueRules.FACE0_EDGES, edge_states):
            cube.edge_attribute(ekey, 'guess', state)
        if clue is not None:
            cube.face_attribute(0, 'clue', clue)

    def test_f_eq_n_rules_out_unknowns(self, cube):
        # n=2, f=2, u=2 → both unknowns become ruledOut.
        self._setup(cube, 2, [self.F, self.F, self.U, self.U])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((2, 1), 'guess') == 'ruledOut'
        assert cube.edge_attribute((1, 0), 'guess') == 'ruledOut'

    def test_f_plus_u_eq_n_fills_unknowns(self, cube):
        # n=3, f=2, u=1, r=1 → f+u == n with f < n; case 4 fires.
        # (Note: if f == n, case 3 fires first and rules out the unknown
        # instead — case 4 only applies when the face still needs fills.)
        self._setup(cube, 3, [self.F, self.F, self.U, self.R])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((2, 1), 'guess') == 'filledIn'

    def test_clue_zero_rules_out_all(self, cube):
        # n=0, f=0, u=4 → case 3 (f == n == 0) fills nothing, rules out all.
        self._setup(cube, 0, [self.U, self.U, self.U, self.U])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is True
        for ekey in self.FACE0_EDGES:
            assert cube.edge_attribute(ekey, 'guess') == 'ruledOut'

    def test_clue_d_fills_all(self, cube):
        # n=4 (== d), f=0, u=4 → case 4 (f+u == n) fills everything.
        self._setup(cube, 4, [self.U, self.U, self.U, self.U])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is True
        for ekey in self.FACE0_EDGES:
            assert cube.edge_attribute(ekey, 'guess') == 'filledIn'

    def test_no_inference_between_extremes(self, cube):
        # n=2, f=1, u=3 → 0 < n-f < u, nothing forced.
        self._setup(cube, 2, [self.F, self.U, self.U, self.U])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is False
        # The three unknowns stay unknown.
        for ekey in self.FACE0_EDGES[1:]:
            assert cube.edge_attribute(ekey, 'guess') == 'unknown'

    def test_f_gt_n_contradiction(self, cube):
        # n=1, f=2 → over the limit.
        self._setup(cube, 1, [self.F, self.F, self.U, self.U])
        (ok, _) = apply_clue_rules(cube)
        assert ok is False

    def test_f_plus_u_lt_n_contradiction(self, cube):
        # n=3, f=0, u=2, r=2 → can't reach 3.
        self._setup(cube, 3, [self.R, self.R, self.U, self.U])
        (ok, _) = apply_clue_rules(cube)
        assert ok is False

    def test_satisfied_with_no_unknowns_no_change(self, cube):
        # n=2, f=2, r=2, u=0 → already satisfied, the u >= 1 guards bite.
        self._setup(cube, 2, [self.F, self.F, self.R, self.R])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is False

    def test_unclued_face_is_ignored(self, cube):
        # No clue → no rule, no contradiction even though n=2 here would fire.
        self._setup(cube, None, [self.F, self.F, self.U, self.U])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is False
        # Edges untouched.
        assert cube.edge_attribute((2, 1), 'guess') == 'unknown'
        assert cube.edge_attribute((1, 0), 'guess') == 'unknown'

    def test_unclued_face_with_all_filled_is_not_a_contradiction(self, cube):
        # Without a clue, "all 4 filled" is not over any limit. This guards
        # against a future bug where someone might validate every face
        # against an implicit limit.
        self._setup(cube, None, [self.F, self.F, self.F, self.F])
        (ok, changed) = apply_clue_rules(cube)
        assert ok is True
        assert changed is False


# --- propagate_constraints ---

class TestPropagateConstraints:
    """End-to-end tests of the orchestrator: vertex rules and clue rules
    alternating to a fixed point, with contradiction detection from either
    side.
    """

    @staticmethod
    def _reset_edges(cube):
        for ekey in cube.edges():
            cube.edge_attribute(ekey, 'guess', 'unknown')

    # 1. Empty no-op: nothing to infer.
    def test_empty_state_returns_true_no_changes(self, cube):
        self._reset_edges(cube)
        result = propagate_constraints(cube, [], 0)
        assert result is True
        for ekey in cube.edges():
            assert cube.edge_attribute(ekey, 'guess') == 'unknown'

    # 2. Already satisfied state — a complete bottom-loop solution with
    #    consistent clues. Every rule's preconditions fail because u==0
    #    everywhere, so the loop converges in one pass with no changes.
    def test_already_at_fixed_point(self, cube):
        bottom = [(0, 3), (3, 2), (2, 1), (1, 0)]
        top    = [(4, 5), (5, 6), (6, 7), (7, 4)]
        verticals = [(0, 4), (1, 5), (2, 6), (3, 7)]
        for e in bottom:
            cube.edge_attribute(e, 'guess', 'filledIn')
        for e in top + verticals:
            cube.edge_attribute(e, 'guess', 'ruledOut')
        cube.face_attribute(0, 'clue', 4)   # bottom: all filled
        cube.face_attribute(1, 'clue', 0)   # top:    none filled

        result = propagate_constraints(cube, [], 0)
        assert result is True
        for e in bottom:
            assert cube.edge_attribute(e, 'guess') == 'filledIn'
        for e in top + verticals:
            assert cube.edge_attribute(e, 'guess') == 'ruledOut'

    # 3. Clue-rule fires first, then vertex rules cascade.
    def test_clue_then_vertex_cascade(self, cube):
        self._reset_edges(cube)
        cube.face_attribute(0, 'clue', 4)   # bottom: all filled

        result = propagate_constraints(cube, [], 0)
        assert result is True
        # Bottom (filled by clue rule):
        for e in [(0, 3), (3, 2), (2, 1), (1, 0)]:
            assert cube.edge_attribute(e, 'guess') == 'filledIn'
        # Verticals (ruled out by vertex rule once each face-0 vertex has f=2):
        for e in [(0, 4), (1, 5), (2, 6), (3, 7)]:
            assert cube.edge_attribute(e, 'guess') == 'ruledOut'
        # Top (no constraint reaches here, stays unknown):
        for e in [(4, 5), (5, 6), (6, 7), (7, 4)]:
            assert cube.edge_attribute(e, 'guess') == 'unknown'

    # 4. Vertex-rule fires first, then a clue rule fires using the new
    #    state, then vertex rules cascade further. Verifies multi-round
    #    alternation between families.
    def test_vertex_then_clue_then_vertex_cascade(self, cube):
        self._reset_edges(cube)
        # Pre-set 2 of vertex 0's 3 incident edges as filled.
        cube.edge_attribute((0, 1), 'guess', 'filledIn')
        cube.edge_attribute((0, 4), 'guess', 'filledIn')
        # Set clue=1 on face 5 (left). After the vertex rule rules out (0,3),
        # face 5 has f=1, n=1 with two unknowns — the clue rule rules them out.
        # Those rule-outs then cascade back into more vertex inferences.
        cube.face_attribute(5, 'clue', 1)

        result = propagate_constraints(cube, [], 0)
        assert result is True

        # From vertex rule at vertex 0 (round 1):
        assert cube.edge_attribute((0, 3), 'guess') == 'ruledOut'
        # From clue rule at face 5 (round 1, after vertex rule):
        assert cube.edge_attribute((4, 7), 'guess') == 'ruledOut'
        assert cube.edge_attribute((3, 7), 'guess') == 'ruledOut'
        # From vertex rules cascading after clue rule (round 2):
        assert cube.edge_attribute((4, 5), 'guess') == 'filledIn'  # vertex 4: f=1,r=1,u=1
        assert cube.edge_attribute((6, 7), 'guess') == 'ruledOut'  # vertex 7: f=0,r=2,u=1
        assert cube.edge_attribute((2, 3), 'guess') == 'ruledOut'  # vertex 3: f=0,r=2,u=1

    # 5. Vertex-rule contradiction (3 filled at one vertex) → False.
    def test_vertex_contradiction_returns_false(self, cube):
        self._reset_edges(cube)
        # Vertex 0 incident edges: (0,1), (0,3), (0,4). All three filled.
        cube.edge_attribute((0, 1), 'guess', 'filledIn')
        cube.edge_attribute((0, 3), 'guess', 'filledIn')
        cube.edge_attribute((0, 4), 'guess', 'filledIn')

        result = propagate_constraints(cube, [], 0)
        assert result is False

    # 6. Clue-rule contradiction (f > n) → False. Vertex rules fire first
    #    and may make some changes, but then clue rules detect f > n.
    def test_clue_contradiction_returns_false(self, cube):
        self._reset_edges(cube)
        # Two of face 0's edges filled, but clue says only 1.
        cube.edge_attribute((0, 3), 'guess', 'filledIn')
        cube.edge_attribute((1, 0), 'guess', 'filledIn')
        cube.face_attribute(0, 'clue', 1)

        result = propagate_constraints(cube, [], 0)
        assert result is False


# --- solution_is_unique (integration) ---

class TestSolutionIsUnique:
    """End-to-end small-puzzle tests. Each builds a cube + clues + a known
    solution and asserts uniqueness. dualG is unused by the solver, so we
    pass None.
    """

    def test_unique_solution_one_face_loop(self, cube):
        # clue 4 on bottom + clue 0 on top → propagation alone determines
        # every edge, leaving exactly one valid loop (the bottom 4-cycle).
        clues = [(0, 4), (1, 0)]
        solution = [0, 3, 2, 1]
        result = solution_is_unique(clues, len(clues), solution, cube, None)
        assert result is True

    def test_unique_solution_via_negative_clue(self, cube):
        # clue 0 on the front face → all 4 front edges ruled out, isolating
        # the 4 front-side vertices to degree-1 in the remaining graph.
        # The only valid loop on the remaining edges is the back 4-cycle.
        clues = [(2, 0)]
        solution = [2, 3, 7, 6]
        result = solution_is_unique(clues, len(clues), solution, cube, None)
        assert result is True

    def test_no_single_loop_returns_false(self, cube):
        # clue 4 on bottom AND top forces both faces filled — but those
        # two 4-cycles are disjoint, not a single loop. is_valid_loop
        # rejects it; solutions_found stays at 0; uniqueness check fails.
        clues = [(0, 4), (1, 4)]
        # Provide any "solution"; the function counts valid loops, not
        # matches against the input.
        solution = [0, 3, 2, 1]
        result = solution_is_unique(clues, len(clues), solution, cube, None)
        assert result is False

    def test_exhausted_time_budget_returns_false(self, cube):
        # This puzzle is unique (see test_unique_solution_one_face_loop),
        # but with a zero time budget the search can't complete, so
        # uniqueness must NOT be claimed. (A False here is conservative:
        # the generator just uses more clues.)
        clues = [(0, 4), (1, 0)]
        solution = [0, 3, 2, 1]
        result = solution_is_unique(clues, len(clues), solution, cube, None,
                                    time_budget=0)
        assert result is False

    def test_generous_time_budget_does_not_change_result(self, cube):
        # A budget large enough for the search to finish must behave
        # exactly like no budget at all.
        clues = [(0, 4), (1, 0)]
        solution = [0, 3, 2, 1]
        result = solution_is_unique(clues, len(clues), solution, cube, None,
                                    time_budget=30)
        assert result is True

    def test_no_clues_admits_multiple_solutions(self, cube):
        # No clues → many valid loops exist on the cube (face cycles,
        # hex slices, Hamiltonian cycles). Solver should find ≥2 and
        # abort early.
        clues = []
        solution = [0, 3, 2, 1]
        result = solution_is_unique(clues, 0, solution, cube, None)
        assert result is False


# --- dodecahedron integration ---

class TestDodecahedronIntegration:
    """Exercise the solver on a 30-edge mesh — large enough that worst-case
    DFS (2^30 leaves) is intractable, so a passing test confirms propagation
    is doing real work."""

    def test_dodecahedron_fixture_loads(self, dodecahedron):
        # Guard against silent fixture breakage (data file moved/changed).
        assert sum(1 for _ in dodecahedron.vertices()) == 20
        assert sum(1 for _ in dodecahedron.faces()) == 12
        assert sum(1 for _ in dodecahedron.edges()) == 30

    def test_existing_puzzle_terminates_quickly(self, dodecahedron, dodec_puzzle):
        """Timing-only check on the existing dodecahedron puzzle. Guards
        against propagation regressions that would push the 30-edge solve
        into worst-case 2^30 territory."""
        (clues, solution) = dodec_puzzle

        start = time.time()
        solution_is_unique(clues, len(clues), solution, dodecahedron, None)
        elapsed = time.time() - start

        assert elapsed < 30.0, (
            f"solver took {elapsed:.1f}s on a 30-edge puzzle — "
            f"propagation is likely too weak (or there's a bug)"
        )

    def test_existing_puzzle_solution_is_unique(self, dodecahedron, dodec_puzzle):
        """The puzzle in data/D-puzzles.json has exactly one valid solution.
        (Verified this by hand.)
        """
        (clues, solution) = dodec_puzzle
        result = solution_is_unique(clues, len(clues), solution, dodecahedron, None)
        assert result is True


class TestFaceColoring:
    """The parity union-find underneath apply_color_rules: it answers
    'same color or opposite?' without ever assigning an absolute color."""

    def test_unrelated_faces_have_no_relation(self):
        coloring = FaceColoring()
        assert coloring.relation(1, 2) is None

    def test_same_and_opposite_are_remembered(self):
        coloring = FaceColoring()
        assert coloring.relate(1, 2, opposite=True) is True
        assert coloring.relation(1, 2) is True
        assert coloring.relate(3, 4, opposite=False) is True
        assert coloring.relation(3, 4) is False

    def test_relations_compose_along_a_chain(self):
        # opposite + opposite = same; add one more opposite and it flips again.
        coloring = FaceColoring()
        coloring.relate(1, 2, opposite=True)
        coloring.relate(2, 3, opposite=True)
        assert coloring.relation(1, 3) is False
        coloring.relate(3, 4, opposite=True)
        assert coloring.relation(1, 4) is True

    def test_same_relations_compose_to_same(self):
        coloring = FaceColoring()
        coloring.relate(1, 2, opposite=False)
        coloring.relate(2, 3, opposite=False)
        assert coloring.relation(1, 3) is False

    def test_contradiction_is_reported(self):
        # 1 and 3 are forced same by the chain, so claiming they're opposite
        # must be rejected.
        coloring = FaceColoring()
        coloring.relate(1, 2, opposite=True)
        coloring.relate(2, 3, opposite=True)
        assert coloring.relate(1, 3, opposite=True) is False
        # Restating what's already known is fine, not a contradiction.
        assert coloring.relate(1, 3, opposite=False) is True

    def test_relation_is_symmetric(self):
        coloring = FaceColoring()
        coloring.relate(7, 8, opposite=True)
        assert coloring.relation(8, 7) is True

    def test_long_chain_stays_consistent(self):
        # 40 links, alternating: parity should still be exact at the far end.
        coloring = FaceColoring()
        for i in range(40):
            assert coloring.relate(i, i + 1, opposite=True) is True
        # An even number of flips means same color, odd means opposite.
        assert coloring.relation(0, 40) is False
        assert coloring.relation(0, 39) is True


class TestApplyColorRules:
    """Coloring inference over a cube. Face keys: 0 bottom, 1 top,
    2 front, 3 right, 4 back, 5 left."""

    def test_empty_board_deduces_nothing(self, cube):
        fill(cube, [])
        (ok, changed) = apply_color_rules(cube)
        assert ok is True
        assert changed is False

    def test_three_faces_at_a_vertex_force_the_third_edge(self, cube):
        # Faces 0 (bottom), 2 (front) and 5 (left) all meet at vertex 0, so
        # each pair shares an edge. Decide two of those edges and the third
        # is forced: bottom/front opposite (filled) and bottom/left same
        # (ruled out) makes front/left opposite, so edge (0,4) must be filled.
        fill(cube, [])
        set_edge(cube, 0, 1, 'filledIn')   # bottom | front
        set_edge(cube, 0, 3, 'ruledOut')   # bottom | left

        (ok, changed) = apply_color_rules(cube)
        assert ok is True
        assert changed is True
        assert guess_of(cube, 0, 4) == 'filledIn'

    def test_deduces_what_vertex_and_clue_rules_cannot(self, cube):
        """The distinguishing case: a relationship carried around a ring of
        faces, forcing an edge that no local rule can touch.

        Ruling out the three edges (1,5), (2,6), (3,7) makes all four side
        faces the same color, so the fourth side edge (0,4) must be ruled out
        too. None of those three edges touches vertex 0 or vertex 4, so the
        vertex rule sees nothing at either end of (0,4); there are no clues,
        so the clue rule sees nothing either.
        """
        fill(cube, [])
        set_edge(cube, 1, 5, 'ruledOut')   # front | right
        set_edge(cube, 2, 6, 'ruledOut')   # right | back
        set_edge(cube, 3, 7, 'ruledOut')   # back  | left

        # First: confirm the other two rule families really are helpless here.
        (ok_v, changed_v) = apply_vertex_rules(cube)
        (ok_c, changed_c) = apply_clue_rules(cube)
        assert (ok_v, changed_v) == (True, False)
        assert (ok_c, changed_c) == (True, False)
        assert guess_of(cube, 0, 4) == 'unknown'

        # Coloring closes the ring and forces the edge.
        (ok, changed) = apply_color_rules(cube)
        assert ok is True
        assert changed is True
        assert guess_of(cube, 0, 4) == 'ruledOut'

    def test_detects_a_coloring_contradiction(self, cube):
        # Same ring, but with the fourth side edge filled in: the four side
        # faces are all one color, yet (0,4) claims front and left differ.
        fill(cube, [])
        set_edge(cube, 1, 5, 'ruledOut')
        set_edge(cube, 2, 6, 'ruledOut')
        set_edge(cube, 3, 7, 'ruledOut')
        set_edge(cube, 0, 4, 'filledIn')

        (ok, _changed) = apply_color_rules(cube)
        assert ok is False

    def test_odd_ring_of_filled_edges_is_a_contradiction(self, cube):
        # Three of the four side edges filled and the fourth ruled out means
        # going around the ring flips color an odd number of times, which
        # can't close up. (This is the parity constraint that the per-vertex
        # rule cannot see.)
        fill(cube, [])
        set_edge(cube, 1, 5, 'filledIn')
        set_edge(cube, 2, 6, 'filledIn')
        set_edge(cube, 3, 7, 'filledIn')
        set_edge(cube, 0, 4, 'ruledOut')

        (ok, _changed) = apply_color_rules(cube)
        assert ok is False


class TestApplyPatternRules:
    """Tier-1 clue patterns, stated in terms of a face's deficit (sides minus
    clue). Cube faces: 0 bottom, 1 top, 2 front, 3 right, 4 back, 5 left.
    A cube face with clue 3 is a "-1 face"."""

    def test_no_clues_deduces_nothing(self, cube):
        fill(cube, [])
        assert apply_pattern_rules(cube) == (True, False)

    def test_mid_range_clue_alone_deduces_nothing(self, cube):
        # Deficit 2 isn't a tier-1 pattern: nothing is forced.
        fill(cube, [])
        cube.face_attribute(0, 'clue', 2)
        assert apply_pattern_rules(cube) == (True, False)

    def test_rule_a_fills_both_edges_of_a_minus_one_face(self, cube):
        """A -1 face at a vertex whose other edges are ruled out: its two
        edges there must both be filled, because the face can't afford two
        ruled-out edges and the vertex can't hold just one filled edge."""
        fill(cube, [])
        cube.face_attribute(0, 'clue', 3)       # bottom, 4 sides -> -1 face
        # Vertex 0's edges are (0,1) and (0,3) of the bottom face, plus (0,4).
        set_edge(cube, 0, 4, 'ruledOut')

        (ok, changed) = apply_pattern_rules(cube)
        assert ok is True
        assert changed is True
        assert guess_of(cube, 0, 1) == 'filledIn'
        assert guess_of(cube, 0, 3) == 'filledIn'

    def test_rule_b_rules_out_both_edges_of_a_clue_one_face(self, cube):
        """The mirror image: a clue-1 face can't have two filled edges at one
        vertex, so with the vertex's other edges ruled out it must have none."""
        fill(cube, [])
        cube.face_attribute(0, 'clue', 1)
        set_edge(cube, 0, 4, 'ruledOut')

        (ok, changed) = apply_pattern_rules(cube)
        assert ok is True
        assert changed is True
        assert guess_of(cube, 0, 1) == 'ruledOut'
        assert guess_of(cube, 0, 3) == 'ruledOut'

    def test_rule_a_reports_a_contradiction(self, cube):
        # Same setup, but one of the two edges is already ruled out, so the
        # vertex could only ever reach one filled edge: impossible.
        fill(cube, [])
        cube.face_attribute(0, 'clue', 3)
        set_edge(cube, 0, 4, 'ruledOut')
        set_edge(cube, 0, 1, 'ruledOut')

        (ok, _changed) = apply_pattern_rules(cube)
        assert ok is False

    def test_rule_d_adjacent_minus_one_faces_fill_the_far_edges(self, cube):
        """Rule D: two -1 faces sharing an edge fill each other's edges that
        touch neither end of it.

        Bottom (face 0) and front (face 2) share edge (0,1). Away from vertices
        0 and 1, the bottom has only (3,2) and the front only (5,4), so both
        are filled. Nothing else is forced: the shared edge and the four edges
        beside it stay unknown, because the loop could still be the boundary of
        these two faces together, in which case (0,1) is ruled out.
        """
        fill(cube, [])
        cube.face_attribute(0, 'clue', 3)   # bottom
        cube.face_attribute(2, 'clue', 3)   # front; shares edge (0,1) with bottom

        (ok, changed) = apply_pattern_rules(cube)
        assert (ok, changed) == (True, True)
        assert guess_of(cube, 3, 2) == 'filledIn'   # bottom's far edge
        assert guess_of(cube, 5, 4) == 'filledIn'   # front's far edge

        # The shared edge and its four neighbours are deliberately untouched.
        assert guess_of(cube, 0, 1) == 'unknown'    # the shared edge
        for (u, v) in [(0, 3), (2, 1), (1, 5), (4, 0)]:
            assert guess_of(cube, u, v) == 'unknown', f"edge {(u, v)} shouldn't be forced"

    def test_rule_d_holds_even_for_the_domino_solution(self, cube):
        """The exception to "the shared edge is filled" doesn't threaten the
        rest of Rule D: with the loop running around bottom+front together,
        the far edges really are filled and the shared edge really is ruled
        out, so Rule D's conclusions still hold."""
        # Loop around the union of the bottom and front faces.
        fill(cube, [(0, 3), (3, 2), (2, 1), (1, 5), (5, 4), (4, 0)])
        for e in cube.edges():
            if cube.edge_attribute(e, 'guess') == 'unknown':
                cube.edge_attribute(e, 'guess', 'ruledOut')
        cube.face_attribute(0, 'clue', 3)
        cube.face_attribute(2, 'clue', 3)

        (ok, _changed) = apply_pattern_rules(cube)
        assert ok is True, "Rule D must not contradict a legal solution"
        assert guess_of(cube, 3, 2) == 'filledIn'
        assert guess_of(cube, 5, 4) == 'filledIn'
        assert guess_of(cube, 0, 1) == 'ruledOut'

    def test_rule_d_forces_nothing_between_adjacent_triangles(self, octahedron):
        """A triangle's three edges all touch an end of any given edge, so a
        shared-edge pair of -1 triangles leaves nothing 'away' to fill."""
        fill(octahedron, [])
        # Faces 0 and 1 are adjacent triangles; -1 for a triangle means clue 2.
        octahedron.face_attribute(0, 'clue', 2)
        octahedron.face_attribute(1, 'clue', 2)

        assert apply_pattern_rules(octahedron) == (True, False)

    def test_rule_c_two_minus_one_faces_meeting_only_at_a_vertex(self, octahedron):
        """Two -1 faces that share only a vertex: each contributes exactly one
        filled edge there, so each one's single ruled-out edge is at that
        vertex and all its other edges are filled.

        On the octahedron, vertex 0 has four triangles around it (faces 0-3).
        Faces 0 and 2 are opposite there, sharing only vertex 0. A triangle
        with clue 2 is a -1 face.
        """
        fill(octahedron, [])
        assert 2 not in octahedron.face_neighbors(0), "faces 0 and 2 should meet only at a vertex"
        octahedron.face_attribute(0, 'clue', 2)   # [0,2,3]
        octahedron.face_attribute(2, 'clue', 2)   # [0,4,5]

        (ok, changed) = apply_pattern_rules(octahedron)
        assert ok is True
        assert changed is True
        # Each face's edge away from vertex 0 is forced filled.
        assert guess_of(octahedron, 2, 3) == 'filledIn'
        assert guess_of(octahedron, 4, 5) == 'filledIn'

    def test_patterns_never_contradict_a_real_solution(self, dodecahedron, dodec_puzzle):
        """Soundness spot-check on real data: every edge the rules determine
        must agree with the puzzle's stored solution."""
        (clues, solution) = dodec_puzzle
        for e in dodecahedron.edges():
            dodecahedron.edge_attribute(e, 'guess', 'unknown')
        apply_clues(clues, len(clues), dodecahedron)
        assert propagate_constraints(dodecahedron, clues, len(clues)) is True

        loop_edges = {frozenset((solution[i], solution[(i + 1) % len(solution)]))
                      for i in range(len(solution))}
        for e in dodecahedron.edges():
            guess = dodecahedron.edge_attribute(e, 'guess')
            if guess == 'unknown':
                continue
            assert (guess == 'filledIn') == (frozenset(e) in loop_edges), (
                f"edge {tuple(e)} deduced {guess}, contradicting the solution")
