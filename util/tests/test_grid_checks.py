"""Tests for grid_checks.py, the geometric checks every grid generator ends with.

Two things are worth pinning down. The checks must PASS on the real grids in
data/, all of which were generated and verified by the code these replaced -- so
any check that now fails on them is the check being wrong, not the data. And each
must FAIL on a solid deliberately broken in the way it exists to catch, since a
check that cannot fail is worse than none.
"""
import math

import pytest

import grid_checks
from grid_checks import (
    census_text, check_census, check_closed_surface, check_congruent_faces,
    check_counts, check_direction_classes, check_equal_edge_lengths,
    check_equal_vertex_radii, check_euler, check_flat_faces,
    check_outward_winding, check_parallelogram_faces, check_regular_faces,
    check_vertex_degrees, corner_angles, direction_classes, edge_lengths,
    face_bow, face_census, face_normal, face_skew, inscribed_radius,
    sharpest_corner, side_ratio,
)
from grid_topology import load_grid

from test_grid_topology import DATA_DIR

# A unit cube centred on the origin: every face flat and regular, all edges 2.
CUBE_VERTICES = [
    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
]
CUBE_FACES = [
    [0, 3, 2, 1],   # bottom, wound outward (-z)
    [4, 5, 6, 7],   # top
    [0, 1, 5, 4],   # front
    [1, 2, 6, 5],   # right
    [2, 3, 7, 6],   # back
    [3, 0, 4, 7],   # left
]


class TestVectorsAndFaces:
    SQUARE = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]]

    def test_edge_lengths_go_round_the_face(self):
        assert edge_lengths(self.SQUARE) == [2, 2, 2, 2]

    def test_a_square_has_four_right_angles(self):
        assert corner_angles(self.SQUARE) == pytest.approx([90, 90, 90, 90])

    def test_sharpest_corner_of_a_square_is_ninety(self):
        assert sharpest_corner(self.SQUARE) == pytest.approx(90)

    def test_sharpest_corner_finds_a_sliver(self):
        sliver = [[0, 0, 0], [10, 0, 0], [10, 1, 0]]
        assert sharpest_corner(sliver) < 10

    def test_inscribed_radius_of_a_square_is_half_its_side(self):
        assert inscribed_radius(self.SQUARE) == pytest.approx(1.0)

    def test_a_flat_face_has_no_bow(self):
        assert face_bow(self.SQUARE) == pytest.approx(0, abs=1e-15)

    def test_a_bent_face_bows(self):
        bent = [[0, 0, 0], [2, 0, 0], [2, 2, 1], [0, 2, 0]]
        assert face_bow(bent) > 0.1

    def test_normal_survives_three_collinear_corners(self):
        """The reason for Newell's method: a face whose first three corners are
        collinear has no first-three normal at all, and the old formulations would
        have produced a zero or wildly wrong one while reporting nothing amiss."""
        collinear_start = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]]
        normal = face_normal(collinear_start)
        assert grid_checks.norm(normal) > 0
        # It is a flat face in the z=0 plane, so the normal must be along z.
        assert abs(normal[0]) < 1e-12 and abs(normal[1]) < 1e-12
        assert face_bow(collinear_start) == pytest.approx(0, abs=1e-15)

    def test_face_census_and_its_text(self):
        assert face_census(CUBE_FACES) == {4: 6}
        assert census_text(CUBE_FACES) == '6 4-gons'


class TestChecksPassOnACube:
    def test_everything_passes(self):
        assert check_euler(CUBE_VERTICES, CUBE_FACES) == []
        assert check_census(CUBE_FACES, {4: 6}) == []
        assert check_counts(CUBE_VERTICES, CUBE_FACES,
                            {'vertices': 8, 'edges': 12, 'faces': 6}) == []
        assert check_vertex_degrees(CUBE_FACES, {3}) == []
        assert check_equal_edge_lengths(CUBE_VERTICES, CUBE_FACES, 1e-12) == []
        assert check_equal_vertex_radii(CUBE_VERTICES, 1e-12) == []
        assert check_flat_faces(CUBE_VERTICES, CUBE_FACES, 1e-12) == []
        assert check_closed_surface(CUBE_FACES) == []
        assert check_outward_winding(CUBE_VERTICES, CUBE_FACES) == []
        assert check_regular_faces(CUBE_VERTICES, CUBE_FACES, 1e-12) == []
        assert check_congruent_faces(CUBE_VERTICES, CUBE_FACES, 1e-12, 1e-9) == []


class TestChecksCatchWhatTheyAreFor:
    """Each check, given exactly the fault it exists to detect."""

    def test_wrong_counts(self):
        problems = check_counts(CUBE_VERTICES, CUBE_FACES, {'faces': 12})
        assert len(problems) == 1 and '12 faces expected' in problems[0]

    def test_euler_fails_when_a_face_is_missing(self):
        assert check_euler(CUBE_VERTICES, CUBE_FACES[:-1]) != []

    def test_wrong_census(self):
        assert check_census(CUBE_FACES, {3: 6}) != []

    def test_wrong_vertex_degrees(self):
        assert check_vertex_degrees(CUBE_FACES, {4}) != []

    def test_unequal_edges(self):
        stretched = [list(v) for v in CUBE_VERTICES]
        stretched[6] = [3, 3, 3]
        assert check_equal_edge_lengths(stretched, CUBE_FACES, 1e-9) != []

    def test_unequal_radii(self):
        moved = [list(v) for v in CUBE_VERTICES]
        moved[0] = [-2, -2, -2]
        assert check_equal_vertex_radii(moved, 1e-9) != []

    def test_a_bent_face(self):
        bent = [list(v) for v in CUBE_VERTICES]
        bent[6] = [1, 1, 1.5]           # pushes the top and two sides out of plane
        problems = check_flat_faces(bent, CUBE_FACES, 1e-9)
        assert problems != [] and 'not flat' in problems[0]

    def test_a_reversed_face_breaks_winding_and_the_surface(self):
        flipped = [list(reversed(CUBE_FACES[0]))] + CUBE_FACES[1:]
        assert check_outward_winding(CUBE_VERTICES, flipped) != []
        # Reversing one face leaves its directed edges unpaired as well.
        assert check_closed_surface(flipped) != []

    def test_a_repeated_face_is_not_a_closed_surface(self):
        """Euler's formula can miss this when two errors cancel, which is exactly
        why the directed-edge check exists alongside it."""
        assert check_closed_surface(CUBE_FACES + [CUBE_FACES[0]]) != []

    def test_a_rhombus_is_not_regular(self):
        """Equal sides are not enough: a rhombus has four equal sides and is not
        regular. That is why the check also compares corner radii."""
        rhombus_vertices = [[0, 0, 0], [2, 1, 0], [4, 0, 0], [2, -1, 0]]
        rhombus = [[0, 1, 2, 3]]
        assert edge_lengths(
            [rhombus_vertices[i] for i in rhombus[0]]) == pytest.approx(
                [math.sqrt(5)] * 4)
        assert check_regular_faces(rhombus_vertices, rhombus, 1e-9) != []

    def test_faces_of_different_shapes_are_not_congruent(self):
        stretched = [list(v) for v in CUBE_VERTICES]
        stretched[4] = [-1, -1, 4]
        stretched[5] = [1, -1, 4]
        stretched[6] = [1, 1, 4]
        stretched[7] = [-1, 1, 4]
        assert check_congruent_faces(stretched, CUBE_FACES, 1e-6, 1e-3) != []

    def test_congruence_tolerances_are_independent(self):
        """Lengths and angles need separate tolerances: comparing an angle in
        degrees against a length tolerance once condemned a good solid over a
        quarter of a degree."""
        faces = load_grid(DATA_DIR / 'dtI.json')
        # A generous angle tolerance with a tight length one, and vice versa,
        # must be able to disagree -- if one number governed both, they couldn't.
        loose_angle = check_congruent_faces(faces['vertices'], faces['faces'],
                                            1e-2, 1.0)
        tight_angle = check_congruent_faces(faces['vertices'], faces['faces'],
                                            1e-2, 1e-9)
        assert loose_angle == []
        assert tight_angle != []


class TestChecksPassOnStoredGrids:
    """Every grid in data/ must satisfy the checks that apply to all solids.

    Not the uniformity ones: a Catalan solid has no circumsphere, and most grids
    have edges of several lengths.
    """

    STEMS = ['T', 'cube', 'O', 'D', 'I', 'tO', 'eD', 'dbD', 'gp12', 'randD',
             'J75', 'A5', 'P6', 'dsD']

    @pytest.mark.parametrize('stem', STEMS)
    def test_grid_is_a_closed_outward_wound_solid(self, stem):
        grid = load_grid(DATA_DIR / f'{stem}.json')
        (vertices, faces) = (grid['vertices'], grid['faces'])
        assert check_euler(vertices, faces) == []
        assert check_closed_surface(faces) == []
        assert check_outward_winding(vertices, faces) == []

    @pytest.mark.parametrize('stem', STEMS)
    def test_faces_are_flat_enough_to_draw_on(self, stem):
        """obj2json.py rounds coordinates to 3 decimals, so a face imported that
        way bows by a few thousandths; exactly generated ones are at 1e-16."""
        grid = load_grid(DATA_DIR / f'{stem}.json')
        assert check_flat_faces(grid['vertices'], grid['faces'], 1e-2) == []

    def test_the_uniform_solids_really_are_uniform(self):
        for stem in ['cube', 'O', 'D', 'I', 'tO', 'eD']:
            grid = load_grid(DATA_DIR / f'{stem}.json')
            (vertices, faces) = (grid['vertices'], grid['faces'])
            assert check_equal_edge_lengths(vertices, faces, 1e-2) == [], stem
            assert check_equal_vertex_radii(vertices, 1e-2) == [], stem

    def test_a_catalan_solid_has_congruent_faces(self):
        """What makes it Catalan, and what genDual checks hardest."""
        grid = load_grid(DATA_DIR / 'daC.json')
        assert check_congruent_faces(grid['vertices'], grid['faces'],
                                     1e-2, 1.0) == []


class TestZones:
    """The zone measures, which say whether a zonohedron looks like one.

    A zonohedron is built from n generating vectors and every edge is a translate
    of one, so its edges run in exactly n directions and every face is a
    parallelogram. Both are visible properties -- a player told that a zonohedron's
    edges come in parallel families should be able to see the families -- so they
    are worth measuring rather than assuming from the name.
    """

    # The zonohedra in data/ with the number of zones each should have: the
    # generating star's size. See STARS in genZonohedron.py.
    ZONOHEDRA = [('cube', 3), ('daC', 4), ('zico5', 5), ('daD', 6), ('jtI', 10)]

    # Reading zones back out of a STORED grid needs more slack than the generator's
    # own check, which works on the unrounded solid at 1e-9. Coordinates in data/
    # are written to 6 decimals, so a unit direction can be out by about
    # 2 * 5e-7 / (edge length) -- a few times 1e-6 on these solids, which at a
    # tolerance of 1e-6 split the rhombic icosahedron's 5 zones into 8. Still
    # thousands of times tighter than the angle between any two real zones, which
    # is tens of degrees.
    FILE_TOLERANCE = 1e-4

    def test_a_cubes_edges_run_three_ways(self):
        classes = direction_classes(CUBE_VERTICES, CUBE_FACES, 1e-9)
        assert len(classes) == 3
        assert sorted(len(edges) for edges in classes) == [4, 4, 4]

    @pytest.mark.parametrize(('stem', 'zones'), ZONOHEDRA)
    def test_the_stored_zonohedra_have_the_zones_they_should(self, stem, zones):
        """The count is the point: it was 90 rather than 10 for the rhombic
        enneacontahedron as first imported, because a canonicalised model of that
        combinatorial type is a different shape from the zonohedral one."""
        grid = load_grid(DATA_DIR / f'{stem}.json')
        classes = direction_classes(grid['vertices'], grid['faces'],
                                    self.FILE_TOLERANCE)
        assert len(classes) == zones
        # Every zone is a band right round the solid, so they are all the same size.
        assert len({len(edges) for edges in classes}) == 1

    @pytest.mark.parametrize(('stem', 'zones'), ZONOHEDRA)
    def test_the_stored_zonohedra_have_rhombic_faces(self, stem, zones):
        grid = load_grid(DATA_DIR / f'{stem}.json')
        (vertices, faces) = (grid['vertices'], grid['faces'])
        assert check_parallelogram_faces(vertices, faces, 1e-5) == []
        assert check_direction_classes(vertices, faces, zones,
                                       self.FILE_TOLERANCE) == []
        # Equal-length generators, so every face is a rhombus and not merely a
        # parallelogram.
        for face in faces:
            corners = grid_checks.corners_of(vertices, face)
            assert side_ratio(corners) < 1.001, stem

    def test_face_skew_is_zero_for_a_parallelogram_and_finite_otherwise(self):
        square = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
        assert face_skew(square) < 1e-15
        # Slide one corner: opposite sides no longer cancel.
        kite = [[0, 0, 0], [1, 0, 0], [1.5, 1, 0], [0, 1, 0]]
        assert face_skew(kite) == pytest.approx(0.5)
        # A triangle cannot be a parallelogram, and says so rather than pretending.
        assert face_skew([[0, 0, 0], [1, 0, 0], [0, 1, 0]]) == math.inf

    def test_side_ratio_tells_a_rhombus_from_a_parallelogram(self):
        rhombus = [[0, 0, 0], [1, 0, 0], [1.6, 0.8, 0], [0.6, 0.8, 0]]
        assert side_ratio(rhombus) == pytest.approx(1.0)
        oblong = [[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]]
        assert side_ratio(oblong) == pytest.approx(2.0)

    def test_a_solid_that_is_no_zonohedron_says_so(self):
        """The checks have to be able to fail, and the tetrahedron is the
        clearest case: triangles cannot be parallelograms at all."""
        grid = load_grid(DATA_DIR / 'T.json')
        (vertices, faces) = (grid['vertices'], grid['faces'])
        assert check_parallelogram_faces(vertices, faces, 1e-5) != []
        # Six edges, all in different directions: as far from a zone structure as
        # a solid can be.
        assert len(direction_classes(vertices, faces, self.FILE_TOLERANCE)) == 6
