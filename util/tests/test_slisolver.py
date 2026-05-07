"""Unit tests for slisolver.py — focused on is_valid_loop().

Strategy:
    Build small known meshes (a cube, an octahedron) once per test via
    fixtures, then mark specific edges as 'filledIn' to reproduce each
    logical case is_valid_loop has to handle:
        - empty filled set
        - degree-1 vertices (single edge, path)
        - valid cycle (3-cycle on octahedron, 4-cycle on cube)
        - multiple disjoint cycles
        - figure-eight (vertex of degree 4 in the filled subgraph)
"""
import pytest
from compas.datastructures import Mesh

from slisolver import is_valid_loop


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

        # And finally: confirm the actual function agrees on a fresh fixture.
        # (Using `cube` again is fine — fill state is preserved on the same instance.)
        from slisolver import is_valid_loop
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
