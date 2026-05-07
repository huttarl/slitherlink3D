"""Unit tests for slisolver.py.

Strategy:
    Build small known meshes (a cube, an octahedron) once per test via
    fixtures. Each test sets up edge guesses or face clues directly, then
    invokes the function under test.
"""
import pytest
from compas.datastructures import Mesh

from slisolver import (
    apply_clues,
    apply_vertex_rules,
    is_complete_solution,
    is_valid_loop,
    restore_state,
    save_state,
    select_edge_for_branching,
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
    # So edge (0, 1) is the same as (1, 0).
    target = {frozenset(p) for p in edge_endpoints}
    for ekey in mesh.edges():
        guess = 'filledIn' if frozenset(ekey) in target else 'unknown'
        mesh.edge_attribute(ekey, 'guess', guess)


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
                v1, v2 = ekey
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
            a, b = adj[cur]
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
                v1, v2 = ekey
                adj.setdefault(v1, []).append(v2)
                adj.setdefault(v2, []).append(v1)
        assert set(adj.keys()) == {0, 1, 2, 3}, f"adj keys: {sorted(adj.keys())}"
        for v, nbrs in adj.items():
            assert len(nbrs) == 2, f"vertex {v} -> {nbrs} (degree {len(nbrs)})"
            assert set(nbrs) <= {0, 1, 2, 3}, f"vertex {v} -> {nbrs}"


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
        ok, changed = apply_vertex_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((0, 4), 'guess') == 'ruledOut'

    def test_f1_u1_fills_unknown(self, cube):
        self._setup_v0(cube, 'filledIn', 'ruledOut', 'unknown')
        ok, changed = apply_vertex_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((0, 4), 'guess') == 'filledIn'

    def test_f0_u1_rules_out_unknown(self, cube):
        self._setup_v0(cube, 'ruledOut', 'ruledOut', 'unknown')
        ok, changed = apply_vertex_rules(cube)
        assert ok is True
        assert changed is True
        assert cube.edge_attribute((0, 4), 'guess') == 'ruledOut'

    def test_f2_u0_no_change(self, cube):
        self._setup_v0(cube, 'filledIn', 'filledIn', 'ruledOut')
        ok, changed = apply_vertex_rules(cube)
        assert ok is True
        assert changed is False
        # State preserved.
        assert cube.edge_attribute((0, 1), 'guess') == 'filledIn'
        assert cube.edge_attribute((0, 3), 'guess') == 'filledIn'
        assert cube.edge_attribute((0, 4), 'guess') == 'ruledOut'

    def test_all_unknown_no_inference(self, cube):
        for ekey in cube.edges():
            cube.edge_attribute(ekey, 'guess', 'unknown')
        ok, changed = apply_vertex_rules(cube)
        assert ok is True
        assert changed is False

    def test_f1_u2_no_inference(self, cube):
        self._setup_v0(cube, 'filledIn', 'unknown', 'unknown')
        ok, changed = apply_vertex_rules(cube)
        assert ok is True
        assert changed is False
        # The two unknowns at vertex 0 stay unknown.
        assert cube.edge_attribute((0, 3), 'guess') == 'unknown'
        assert cube.edge_attribute((0, 4), 'guess') == 'unknown'

    def test_f3_contradiction(self, cube):
        self._setup_v0(cube, 'filledIn', 'filledIn', 'filledIn')
        ok, _ = apply_vertex_rules(cube)
        assert ok is False

    def test_f1_u0_contradiction(self, cube):
        self._setup_v0(cube, 'filledIn', 'ruledOut', 'ruledOut')
        ok, _ = apply_vertex_rules(cube)
        assert ok is False
