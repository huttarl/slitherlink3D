"""Tests for genSymmetric.py, the tetrahedrally symmetric random solids.

The group arithmetic is pinned first, since everything else depends on it, and
then the two claims the generator's design rests on: that relaxing keeps the
symmetry exact, and that every orbit's faces are congruent -- which is what
makes the face census come in blocks of 12.
"""
import functools

import numpy as np
from scipy.spatial import ConvexHull

import grid_checks
from genGoldberg import polar_dual
from genSymmetric import (EDGE_AXES, FACE_AXES, VERTEX_AXES, all_points, draw,
                          dual_edge_lengths, dual_edges_of, has_mirror_symmetry,
                          index_of, orbit, relax, separate_short_edges,
                          source_arguments, symmetry_problems,
                          tetrahedral_rotations, triangle_set)
from grid_topology import edges_of

ROTATIONS = tetrahedral_rotations()


def is_closed_under_rotations(points):
    """Every rotation carries every point onto a point of the set."""
    return all(index_of(r @ p, points) is not None
               for r in ROTATIONS for p in points)


class TestGroup:
    def test_twelve_distinct_rotations(self):
        assert len(ROTATIONS) == 12
        flattened = {tuple(np.round(r, 9).ravel()) for r in ROTATIONS}
        assert len(flattened) == 12

    def test_each_is_a_proper_rotation(self):
        for r in ROTATIONS:
            assert np.allclose(r @ r.T, np.eye(3))
            assert np.isclose(np.linalg.det(r), 1.0)

    def test_closed_under_composition(self):
        known = {tuple(np.round(r, 9).ravel()) for r in ROTATIONS}
        for a in ROTATIONS:
            for b in ROTATIONS:
                assert tuple(np.round(a @ b, 9).ravel()) in known

    def test_generic_orbit_has_twelve_points(self):
        point = np.array([0.3, 0.5, 0.8])
        point /= np.linalg.norm(point)
        images = orbit(point, ROTATIONS)
        gaps = np.linalg.norm(images[:, None] - images[None, :], axis=2)
        np.fill_diagonal(gaps, np.inf)
        assert gaps.min() > 1e-6

    def test_each_axis_set_is_one_orbit(self):
        for axes in (VERTEX_AXES, FACE_AXES, EDGE_AXES):
            assert is_closed_under_rotations(axes)
            # ...and a single orbit, not several: one point reaches them all.
            assert len({index_of(r @ axes[0], axes) for r in ROTATIONS}) == len(axes)


class TestRelaxing:
    def test_keeps_the_symmetry_exact(self):
        rng = np.random.default_rng(3)
        reps = rng.normal(size=(3, 3))
        reps /= np.linalg.norm(reps, axis=1, keepdims=True)
        relaxed = relax(reps, EDGE_AXES, ROTATIONS)
        assert is_closed_under_rotations(all_points(relaxed, EDGE_AXES, ROTATIONS))

    def test_keeps_the_points_on_the_sphere(self):
        rng = np.random.default_rng(4)
        reps = rng.normal(size=(3, 3))
        reps /= np.linalg.norm(reps, axis=1, keepdims=True)
        relaxed = relax(reps, np.empty((0, 3)), ROTATIONS)
        assert np.allclose(np.linalg.norm(relaxed, axis=1), 1.0)


class TestTheSolid:
    """One whole draw, from a fixed seed so the test is repeatable."""

    orbits = 5

    def solid(self):
        rng = np.random.default_rng(1)
        result = None
        while result is None:
            result = draw(self.orbits, np.empty((0, 3)), ROTATIONS, 0.0, rng)
        (_, points, hull) = result
        (vertices, faces) = polar_dual(points)
        return (points, hull, vertices, faces)

    def test_triangulation_is_symmetric(self):
        (points, hull, _, _) = self.solid()
        assert symmetry_problems(points, hull.simplices, ROTATIONS) == []

    def test_passes_the_shared_checks(self):
        (_, _, vertices, faces) = self.solid()
        assert (grid_checks.check_euler(vertices, faces)
                + grid_checks.check_flat_faces(vertices, faces, 1e-9)
                + grid_checks.check_closed_surface(faces)
                + grid_checks.check_outward_winding(vertices, faces)
                + grid_checks.check_vertex_degrees(faces, [3])) == []

    def test_each_orbit_gives_twelve_congruent_faces(self):
        # polar_dual returns one face per input point, in input order, and
        # all_points lists each orbit's 12 images together.
        (_, _, _, faces) = self.solid()
        for n in range(self.orbits):
            sizes = {len(face) for face in faces[12 * n:12 * (n + 1)]}
            assert len(sizes) == 1, f'orbit {n} has faces of sizes {sizes}'

    def test_euler_budget(self):
        # Summing (6 - sides) over the faces of any solid with three faces at
        # every vertex gives 12.
        (_, _, _, faces) = self.solid()
        assert sum(6 - len(face) for face in faces) == 12


class TestMirrorCheck:
    def test_the_cube_is_achiral(self):
        # The cube's vertices: both tetrahedra together, symmetric under inversion.
        assert has_mirror_symmetry(np.vstack([VERTEX_AXES, FACE_AXES]))

    def test_a_random_draw_is_chiral(self):
        rng = np.random.default_rng(1)
        result = None
        while result is None:
            result = draw(4, np.empty((0, 3)), ROTATIONS, 0.0, rng)
        (_, points, _) = result
        assert not has_mirror_symmetry(points)


@functools.lru_cache(maxsize=None)
def separated():
    """A draw with short edges, before and after separation. Cached, since the
    relaxation and the separation are the slowest things in this file.

    Seed 2 at relax 0.25 is the draw that main() makes for those arguments, and
    its shortest edge starts at about 21% of the median.
    """
    rng = np.random.default_rng(2)
    fixed = np.empty((0, 3))
    result = None
    while result is None:
        result = draw(6, fixed, ROTATIONS, 0.25, rng)
    (reps, points, hull) = result
    (moved, before, after) = separate_short_edges(reps, fixed, ROTATIONS, 0.4)
    moved_points = all_points(moved, fixed, ROTATIONS)
    return (points, hull, moved_points, ConvexHull(moved_points), before, after)


class TestSeparatingShortEdges:
    def test_starts_short(self):
        (*_, before, _) = separated()
        assert before < 0.4

    def test_reaches_the_target(self):
        (*_, after) = separated()
        assert after >= 0.4

    def test_keeps_the_triangulation(self):
        # A flip would change vertex degrees, and so the census.
        (_, hull, _, moved_hull, _, _) = separated()
        assert triangle_set(moved_hull.simplices) == triangle_set(hull.simplices)

    def test_keeps_the_symmetry_exact(self):
        (_, _, moved_points, moved_hull, _, _) = separated()
        assert symmetry_problems(moved_points, moved_hull.simplices,
                                 ROTATIONS) == []

    def test_keeps_the_faces_exactly_flat(self):
        # The point of moving the primal points rather than the dual's vertices.
        (_, _, moved_points, _, _, _) = separated()
        (vertices, faces) = polar_dual(moved_points)
        assert grid_checks.check_flat_faces(vertices, faces, 1e-9) == []


def test_dual_edge_lengths_measure_the_real_dual():
    """The separation optimizes dual_edge_lengths, so it must agree with the
    edges of the solid polar_dual actually builds."""
    (points, hull, _, _, _, _) = separated()
    predicted = sorted(dual_edge_lengths(points, hull.simplices,
                                         dual_edges_of(hull.simplices)))
    (vertices, faces) = polar_dual(points)
    actual = sorted(grid_checks.distance(vertices[a], vertices[b])
                    for (a, b) in edges_of(faces))
    assert np.allclose(predicted, actual)


def test_source_names_the_seed():
    options = {'orbits': 6, 'relax': 0.25, 'min_edge': 0.4, 'seed': 42,
               'axes': ['edge'], 'id': None, 'name': None}
    assert source_arguments(options) == ['6', '--relax=0.25', '--min-edge=0.4',
                                         '--seed=42', '--edge-axes']
