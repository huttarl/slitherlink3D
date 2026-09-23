"""Tests for genSymmetric.py, the tetrahedrally symmetric random solids.

The group arithmetic is pinned first, since everything else depends on it, and
then the two claims the generator's design rests on: that relaxing keeps the
symmetry exact, and that every orbit's faces are congruent -- which is what
makes the face census come in blocks of 12.
"""
import functools

import numpy as np
from scipy.spatial import ConvexHull

import genSymmetric
import grid_checks
from genGoldberg import polar_dual
from genSymmetric import (EDGE_AXES, FACE_AXES, MIN_FACE_ANGLE, VERTEX_AXES,
                          all_points, draw, dual_edge_lengths, dual_edges_of,
                          face_shape, has_mirror_symmetry, index_of, orbit,
                          regularize, relax, separate_short_edges,
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


def test_a_regular_face_scores_as_regular():
    """face_shape's zero point: a regular hexagon has no irregularity, no
    corner past the straight-corner limit, 120-degree corners and equal
    sides. Pins the measure the regularizer optimizes."""
    angles = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    poles = np.column_stack([np.cos(angles), np.sin(angles), np.ones(6)])
    (irregularity, straightness, straightest, lopsided) = face_shape(
        poles, {6: np.array([[0, 1, 2, 3, 4, 5]])})
    assert irregularity < 1e-12
    assert straightness == 0
    assert np.isclose(straightest, 120.0)
    assert np.isclose(lopsided, 1.0)


@functools.lru_cache(maxsize=None)
def regularized():
    """The separated draw above, regularized. Fewer rounds than the script
    uses, to keep the suite quick; the tests ask only that it improves and
    keeps what it must keep, which a short run already shows."""
    (points, hull, moved_points, moved_hull, _, _) = separated()
    fixed = np.empty((0, 3))
    rng = np.random.default_rng(2)
    result = None
    while result is None:
        result = draw(6, fixed, ROTATIONS, 0.25, rng)
    (reps, _, _) = result
    (reps, _, _) = separate_short_edges(reps, fixed, ROTATIONS, 0.4)
    saved = genSymmetric.REGULARIZE_ROUNDS
    genSymmetric.REGULARIZE_ROUNDS = 40
    try:
        (reps, before, after) = regularize(reps, fixed, ROTATIONS, 0.4)
    finally:
        genSymmetric.REGULARIZE_ROUNDS = saved
    points = all_points(reps, fixed, ROTATIONS)
    return (moved_hull, points, ConvexHull(points), before, after)


class TestRegularizing:
    def test_makes_faces_more_regular(self):
        (_, _, _, before, after) = regularized()
        assert after[0] < before[0]          # the irregularity itself
        assert after[2] < before[2]          # the straightest corner
        assert after[3] < before[3]          # sides within a face

    def test_keeps_the_triangulation(self):
        (hull_before, _, hull_after, _, _) = regularized()
        assert triangle_set(hull_after.simplices) == triangle_set(hull_before.simplices)

    def test_keeps_the_symmetry_and_flatness(self):
        (_, points, hull, _, _) = regularized()
        assert symmetry_problems(points, hull.simplices, ROTATIONS) == []
        (vertices, faces) = polar_dual(points)
        assert grid_checks.check_flat_faces(vertices, faces, 1e-9) == []

    def test_keeps_the_held_limits(self):
        # Neighboring faces' angle is their points' angle (see regularize).
        (_, points, hull, _, _) = regularized()
        lengths = dual_edge_lengths(points, hull.simplices,
                                    dual_edges_of(hull.simplices))
        assert lengths.min() >= 0.4 * np.median(lengths) * 0.99
        neighbors = {tuple(sorted((int(t[k]), int(t[(k + 1) % 3]))))
                     for t in hull.simplices for k in range(3)}
        flattest = min(np.degrees(np.arccos(np.clip(points[a] @ points[b], -1, 1)))
                       for (a, b) in neighbors)
        assert flattest >= MIN_FACE_ANGLE * 0.99


def test_source_names_the_seed():
    options = {'orbits': 6, 'relax': 0.25, 'min_edge': 0.4, 'regularize': False,
               'seed': 42, 'axes': ['edge'], 'id': None, 'name': None}
    assert source_arguments(options) == ['6', '--relax=0.25', '--min-edge=0.4',
                                         '--seed=42', '--edge-axes']


def test_source_names_regularizing_only_when_on():
    # Off must leave no trace: commands written before the option existed
    # have to go on making the same solid.
    options = {'orbits': 6, 'relax': 0.25, 'min_edge': 0.4, 'regularize': True,
               'seed': 42, 'axes': [], 'id': None, 'name': None}
    assert source_arguments(options)[-1] == '--regularize'
