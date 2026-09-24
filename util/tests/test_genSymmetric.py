"""Tests for genSymmetric.py, the random solids with tetrahedral or octahedral
symmetry.

The group arithmetic is pinned first, since everything else depends on it, and
then the two claims the generator's design rests on: that relaxing keeps the
symmetry exact, and that every orbit's faces are congruent -- which is what
makes the face census come in blocks of 12 (or 24). Then the octahedral
group's merged facets, which give it vertices where four faces meet.
"""
import functools

import numpy as np
import pytest
from scipy.spatial import ConvexHull

import genSymmetric
import grid_checks
from genGoldberg import polar_dual
from genSymmetric import (EDGE_AXES, FACE_AXES, GROUPS, MIN_FACE_ANGLE,
                          VERTEX_AXES, all_points, draw, dual_edge_lengths,
                          dual_edges_of, face_shape, facet_dual, facet_edges,
                          facet_set, hull_facets, has_mirror_symmetry, index_of,
                          move_axis_faces, octahedral_rotations, orbit, pole_triples, regularize,
                          relax, separate_short_edges, source_arguments,
                          symmetry_problems, tetrahedral_rotations, usable_hull)
from grid_topology import edges_of, vertex_degrees

ROTATIONS = tetrahedral_rotations()
OCTAHEDRAL = octahedral_rotations()


def is_closed_under_rotations(points, rotations=ROTATIONS):
    """Every rotation carries every point onto a point of the set."""
    return all(index_of(r @ p, points) is not None
               for r in rotations for p in points)


@pytest.mark.parametrize('name', GROUPS)
class TestGroup:
    def test_distinct_rotations(self, name):
        rotations = GROUPS[name]['rotations']()
        assert len(rotations) == {'tetrahedral': 12, 'octahedral': 24}[name]
        flattened = {tuple(np.round(r, 9).ravel()) for r in rotations}
        assert len(flattened) == len(rotations)

    def test_each_is_a_proper_rotation(self, name):
        for r in GROUPS[name]['rotations']():
            assert np.allclose(r @ r.T, np.eye(3))
            assert np.isclose(np.linalg.det(r), 1.0)

    def test_closed_under_composition(self, name):
        rotations = GROUPS[name]['rotations']()
        known = {tuple(np.round(r, 9).ravel()) for r in rotations}
        for a in rotations:
            for b in rotations:
                assert tuple(np.round(a @ b, 9).ravel()) in known

    def test_generic_orbit_has_a_point_per_rotation(self, name):
        point = np.array([0.3, 0.5, 0.8])
        point /= np.linalg.norm(point)
        images = orbit(point, GROUPS[name]['rotations']())
        gaps = np.linalg.norm(images[:, None] - images[None, :], axis=2)
        np.fill_diagonal(gaps, np.inf)
        assert gaps.min() > 1e-6

    def test_each_axis_set_is_one_orbit(self, name):
        rotations = GROUPS[name]['rotations']()
        for axes in GROUPS[name]['axes'].values():
            assert is_closed_under_rotations(axes, rotations)
            # ...and a single orbit, not several: one point reaches them all.
            assert len({index_of(r @ axes[0], axes) for r in rotations}) == len(axes)


def test_octahedral_group_starts_with_the_tetrahedral():
    # So that adding O changed nothing about a tetrahedral draw.
    assert all(np.array_equal(o, t) for (o, t) in zip(OCTAHEDRAL, ROTATIONS))


def test_octahedral_axes_have_their_folds():
    # Each axis point is fixed by as many rotations as its axis is fold.
    for (kind, fold) in (('vertex', 4), ('face', 3), ('edge', 2)):
        point = GROUPS['octahedral']['axes'][kind][0]
        assert sum(np.allclose(r @ point, point) for r in OCTAHEDRAL) == fold


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
        (_, points, facets) = result
        (vertices, faces) = facet_dual(points, facets)
        return (points, facets, vertices, faces)

    def test_triangulation_is_symmetric(self):
        (points, facets, _, _) = self.solid()
        assert symmetry_problems(points, facets, ROTATIONS) == []

    def test_every_facet_is_a_triangle(self):
        # T's axes are at most 3-fold, so nothing forces four points coplanar.
        (_, facets, _, _) = self.solid()
        assert {len(f) for f in facets} == {3}

    def test_facet_dual_is_polar_dual(self):
        # With nothing merged the two must agree exactly: the tetrahedral
        # solids already in data/ were made by polar_dual.
        (points, _, vertices, faces) = self.solid()
        (expected_vertices, expected_faces) = polar_dual(points)
        assert np.array_equal(vertices, expected_vertices)
        assert faces == expected_faces

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
    (reps, points, facets) = result
    (moved, before, after) = separate_short_edges(reps, fixed, ROTATIONS, 0.4)
    moved_points = all_points(moved, fixed, ROTATIONS)
    return (points, facets, moved_points, usable_hull(moved_points, ROTATIONS),
            before, after)


class TestSeparatingShortEdges:
    def test_starts_short(self):
        (*_, before, _) = separated()
        assert before < 0.4

    def test_reaches_the_target(self):
        (*_, after) = separated()
        assert after >= 0.4

    def test_keeps_the_triangulation(self):
        # A flip would change vertex degrees, and so the census.
        (_, facets, _, moved_facets, _, _) = separated()
        assert facet_set(moved_facets) == facet_set(facets)

    def test_keeps_the_symmetry_exact(self):
        (_, _, moved_points, moved_facets, _, _) = separated()
        assert symmetry_problems(moved_points, moved_facets, ROTATIONS) == []

    def test_keeps_the_faces_exactly_flat(self):
        # The point of moving the primal points rather than the dual's vertices.
        (_, _, moved_points, moved_facets, _, _) = separated()
        (vertices, faces) = facet_dual(moved_points, moved_facets)
        assert grid_checks.check_flat_faces(vertices, faces, 1e-9) == []


def test_dual_edge_lengths_measure_the_real_dual():
    """The separation optimizes dual_edge_lengths, so it must agree with the
    edges of the solid facet_dual actually builds."""
    (points, facets, _, _, _, _) = separated()
    predicted = sorted(dual_edge_lengths(points, pole_triples(facets),
                                         dual_edges_of(facets)))
    (vertices, faces) = facet_dual(points, facets)
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
    (_, _, _, moved_facets, _, _) = separated()
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
    return (moved_facets, points, usable_hull(points, ROTATIONS), before, after)


def held_limits(points, facets):
    """(the shortest dual edge as a fraction of the median, the flattest two
    neighboring faces meet in degrees), the two limits regularizing holds.
    Neighboring faces' angle is their points' angle (see regularize)."""
    lengths = dual_edge_lengths(points, pole_triples(facets), dual_edges_of(facets))
    neighbors = {edge for facet in facets for edge in facet_edges(facet)}
    flattest = min(np.degrees(np.arccos(np.clip(points[a] @ points[b], -1, 1)))
                   for (a, b) in neighbors)
    return (lengths.min() / np.median(lengths), flattest)


class TestRegularizing:
    def test_makes_faces_more_regular(self):
        (_, _, _, before, after) = regularized()
        assert after[0] < before[0]          # the irregularity itself
        assert after[2] < before[2]          # the straightest corner
        assert after[3] < before[3]          # sides within a face

    def test_keeps_the_triangulation(self):
        (facets_before, _, facets_after, _, _) = regularized()
        assert facet_set(facets_after) == facet_set(facets_before)

    def test_keeps_the_symmetry_and_flatness(self):
        (_, points, facets, _, _) = regularized()
        assert symmetry_problems(points, facets, ROTATIONS) == []
        (vertices, faces) = facet_dual(points, facets)
        assert grid_checks.check_flat_faces(vertices, faces, 1e-9) == []

    def test_keeps_the_held_limits(self):
        (_, points, facets, _, _) = regularized()
        (shortest, flattest) = held_limits(points, facets)
        assert shortest >= 0.4 * 0.99
        assert flattest >= MIN_FACE_ANGLE * 0.99


def cube_corners():
    return np.array([[x, y, z] for x in (1, -1) for y in (1, -1)
                     for z in (1, -1)], dtype=float) / 3 ** 0.5


class TestMergingFacets:
    """hull_facets merges exactly coplanar triangles, and usable_hull rejects
    triangles that are only nearly so. Tried on a cube, whose faces are
    squares, with no symmetry to lean on."""

    def test_a_cube_has_six_square_facets(self):
        points = cube_corners()
        facets = hull_facets(points, ConvexHull(points))
        assert sorted(len(f) for f in facets) == [4] * 6

    def test_a_square_facet_goes_around_its_side(self):
        # Each corner and the next are the ends of one of the cube's edges.
        points = cube_corners()
        edge = min(grid_checks.distance(points[0], p) for p in points[1:])
        for facet in hull_facets(points, ConvexHull(points)):
            for (a, b) in facet_edges(facet):
                assert np.isclose(grid_checks.distance(points[a], points[b]), edge)

    def test_its_dual_is_an_octahedron(self):
        # One vertex per facet, with four faces around it: the reason for
        # merging, since unmerged, each square would give two vertices.
        points = cube_corners()
        (vertices, faces) = facet_dual(points, usable_hull(points, [np.eye(3)]))
        assert len(vertices) == 6
        assert set(vertex_degrees(faces).values()) == {4}
        assert grid_checks.check_flat_faces(vertices, faces, 1e-9) == []

    def test_a_corner_pulled_well_out_splits_its_squares(self):
        points = cube_corners()
        points[0] *= 1.05
        facets = usable_hull(points, [np.eye(3)])
        assert sorted(len(f) for f in facets) == [3] * 6 + [4] * 3

    def test_a_corner_pulled_barely_out_is_rejected(self):
        # Three pairs of triangles nearly coplanar: the dual would have three
        # pairs of nearly coincident vertices.
        points = cube_corners()
        points[0] *= 1 + 1e-8
        assert usable_hull(points, [np.eye(3)]) is None


class TestTheOctahedralSolid:
    """One whole octahedral draw, from a fixed seed."""

    orbits = 3

    def solid(self, fixed=np.empty((0, 3))):
        rng = np.random.default_rng(1)
        result = None
        while result is None:
            result = draw(self.orbits, fixed, OCTAHEDRAL, 0.0, rng)
        (_, points, facets) = result
        (vertices, faces) = facet_dual(points, facets)
        return (points, facets, vertices, faces)

    def test_facets_are_symmetric(self):
        (points, facets, _, _) = self.solid()
        assert symmetry_problems(points, facets, OCTAHEDRAL) == []

    def test_a_square_on_each_four_fold_axis(self):
        # The four images of a point about a 4-fold axis are coplanar.
        (points, facets, _, _) = self.solid()
        squares = [f for f in facets if len(f) == 4]
        assert len(squares) == 6
        centers = np.array([points[list(f)].mean(axis=0) for f in squares])
        centers /= np.linalg.norm(centers, axis=1, keepdims=True)
        assert all(index_of(c, EDGE_AXES) is not None for c in centers)
        assert {len(f) for f in facets} == {3, 4}

    def test_passes_the_shared_checks(self):
        (_, _, vertices, faces) = self.solid()
        assert (grid_checks.check_euler(vertices, faces)
                + grid_checks.check_flat_faces(vertices, faces, 1e-9)
                + grid_checks.check_closed_surface(faces)
                + grid_checks.check_outward_winding(vertices, faces)) == []

    def test_six_vertices_of_four_faces(self):
        (_, _, _, faces) = self.solid()
        degrees = list(vertex_degrees(faces).values())
        assert degrees.count(4) == 6
        assert set(degrees) == {3, 4}

    def test_each_orbit_gives_24_congruent_faces(self):
        (_, _, _, faces) = self.solid()
        for n in range(self.orbits):
            sizes = {len(face) for face in faces[24 * n:24 * (n + 1)]}
            assert len(sizes) == 1, f'orbit {n} has faces of sizes {sizes}'

    def test_euler_budget(self):
        # Summing (6 - sides) gives 12, plus 2 for each vertex of degree 4.
        (_, _, _, faces) = self.solid()
        extra = sum(degree - 3 for degree in vertex_degrees(faces).values())
        assert sum(6 - len(face) for face in faces) == 12 + 2 * extra

    def test_points_on_the_four_fold_axes_leave_no_squares(self):
        # The axis's own point is then the hull's corner there, so every facet
        # is a triangle, and the point's face has a multiple of 4 sides.
        fixed = GROUPS['octahedral']['axes']['vertex']
        (_, facets, _, faces) = self.solid(fixed)
        assert {len(f) for f in facets} == {3}
        assert all(len(face) % 4 == 0 for face in faces[-len(fixed):])


@functools.lru_cache(maxsize=None)
def octahedral_moved():
    """An octahedral draw before and after separation and a short
    regularizing: (facets before, points after, facets after)."""
    fixed = np.empty((0, 3))
    rng = np.random.default_rng(1)
    result = None
    while result is None:
        result = draw(3, fixed, OCTAHEDRAL, 0.25, rng)
    (reps, _, facets) = result
    (reps, _, _) = separate_short_edges(reps, fixed, OCTAHEDRAL, 0.4)
    saved = genSymmetric.REGULARIZE_ROUNDS
    genSymmetric.REGULARIZE_ROUNDS = 40
    try:
        (reps, _, _) = regularize(reps, fixed, OCTAHEDRAL, 0.4)
    finally:
        genSymmetric.REGULARIZE_ROUNDS = saved
    points = all_points(reps, fixed, OCTAHEDRAL)
    return (facets, points, usable_hull(points, OCTAHEDRAL))


class TestMovingOctahedralPoints:
    """Separation and regularizing keep the merged facets: the squares stay
    squares, since the points move only in ways that keep the symmetry."""

    def test_keeps_the_facets(self):
        (facets_before, _, facets_after) = octahedral_moved()
        assert facet_set(facets_after) == facet_set(facets_before)

    def test_keeps_the_symmetry_and_flatness(self):
        (_, points, facets) = octahedral_moved()
        assert symmetry_problems(points, facets, OCTAHEDRAL) == []
        (vertices, faces) = facet_dual(points, facets)
        assert grid_checks.check_flat_faces(vertices, faces, 1e-9) == []

    def test_keeps_the_held_limits(self):
        (_, points, facets) = octahedral_moved()
        (shortest, flattest) = held_limits(points, facets)
        assert shortest >= 0.4 * 0.99
        assert flattest >= MIN_FACE_ANGLE * 0.99


def corner_angles_by_face(points, facets):
    """Each face's corner angles, sorted, in face (point) order."""
    (vertices, faces) = facet_dual(points, facets)
    result = []
    for face in faces:
        corners = vertices[face]
        (a, b) = (np.roll(corners, 1, axis=0) - corners, np.roll(corners, -1, axis=0) - corners)
        cosines = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
        result.append(np.sort(np.arccos(np.clip(cosines, -1, 1))))
    return result


class TestMovingAxisFaces:
    """--face-axes=D and the like: the axis faces' planes move, and nothing
    else does."""

    AXES = [('face', GROUPS['octahedral']['axes']['face']),
            ('edge', GROUPS['octahedral']['axes']['edge'])]

    def before_and_after(self, distance):
        fixed = np.vstack([p for (_, p) in self.AXES])
        rng = np.random.default_rng(7)
        result = None
        while result is None:
            result = draw(1, fixed, OCTAHEDRAL, 0.0, rng)
        (reps, points, facets) = result
        return (reps, points, facets,
                move_axis_faces(reps, self.AXES, {'face': distance}, OCTAHEDRAL))

    def test_keeps_the_facets_symmetry_and_flatness(self):
        (reps, _, facets, (moved, moved_facets)) = self.before_and_after(0.97)
        assert facet_set(moved_facets) == facet_set(facets)
        points = all_points(reps, moved, OCTAHEDRAL)
        assert symmetry_problems(points, moved_facets, OCTAHEDRAL) == []
        (vertices, faces) = facet_dual(points, moved_facets)
        assert grid_checks.check_flat_faces(vertices, faces, 1e-9) == []

    def test_moves_only_the_chosen_planes(self):
        # A face's plane is x.v = 1, at distance 1/|v| from the center.
        (reps, _, _, (moved, _)) = self.before_and_after(0.97)
        distances = 1 / np.linalg.norm(all_points(reps, moved, OCTAHEDRAL), axis=1)
        faces_of_face_axes = len(reps) * 24 + np.arange(8)
        assert np.allclose(distances[faces_of_face_axes], 0.97)
        others = np.setdiff1d(np.arange(len(distances)), faces_of_face_axes)
        assert np.allclose(distances[others], 1.0)

    def test_leaves_every_angle_alone(self):
        # Sliding a plane without tilting it leaves every edge's direction,
        # and so every corner angle, as it was: only side lengths change.
        (reps, points, facets, (moved, moved_facets)) = self.before_and_after(0.97)
        before = corner_angles_by_face(points, facets)
        after = corner_angles_by_face(all_points(reps, moved, OCTAHEDRAL), moved_facets)
        assert all(np.allclose(b, a) for (b, a) in zip(before, after))

    def test_refuses_a_move_that_changes_which_faces_meet(self):
        (*_, result) = self.before_and_after(0.5)
        assert result is None


OPTIONS = {'orbits': 6, 'group': 'tetrahedral', 'relax': 0.25, 'min_edge': 0.4,
           'regularize': False, 'seed': 42, 'axes': [], 'axis_distances': {},
           'id': None, 'name': None}


def test_source_names_the_seed():
    options = dict(OPTIONS, axes=['edge'])
    assert source_arguments(options) == ['6', '--relax=0.25', '--min-edge=0.4',
                                         '--seed=42', '--edge-axes']


def test_source_names_regularizing_only_when_on():
    # Off must leave no trace: commands written before the option existed
    # have to go on making the same solid.
    options = dict(OPTIONS, regularize=True)
    assert source_arguments(options)[-1] == '--regularize'


def test_source_names_the_group_only_when_not_tetrahedral():
    # Likewise for the files written before --group existed.
    assert not any(a.startswith('--group') for a in source_arguments(OPTIONS))
    options = dict(OPTIONS, group='octahedral')
    assert source_arguments(options)[:2] == ['6', '--group=octahedral']


def test_source_names_an_axis_distance_only_when_given():
    options = dict(OPTIONS, axes=['face', 'edge'], axis_distances={'face': 0.92})
    assert source_arguments(options)[-2:] == ['--face-axes=0.92', '--edge-axes']


def test_an_axis_flag_takes_a_distance():
    options = genSymmetric.parse_arguments(['1', '--face-axes=0.92', '--edge-axes'])
    assert options['axes'] == ['face', 'edge']
    assert options['axis_distances'] == {'face': 0.92}
