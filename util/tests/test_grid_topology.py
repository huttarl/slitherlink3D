"""Tests for grid_topology.py, the shared topology helpers.

These matter more than their size suggests: several scripts used to carry their
own copy of this logic, and the one that counts -- "largest patch of faces the loop
never touches" -- is now a puzzle-quality gate. The last test here pins
genSliPuzzles' own measure to this module's, since those two look at the same
thing from different directions (a painted region vs a stored solution) and would
otherwise be free to disagree.
"""
import json
import os

# genSliPuzzles imports matplotlib.pyplot; pick a non-interactive backend first.
os.environ.setdefault('MPLBACKEND', 'Agg')

from pathlib import Path

import pytest
from compas.datastructures import Mesh

import grid_topology
from grid_topology import (
    connected_groups, edge_key, edges_of, face_adjacency, face_edges,
    is_connected, largest_group, largest_quiet_patch, loop_ceiling, loop_edges,
    quiet_faces, vertex_degrees, walls_per_face,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / 'data'

# A cube, as the JSON stores one: 8 vertices, 6 quad faces.
CUBE_FACES = [
    [0, 3, 2, 1],   # bottom
    [4, 5, 6, 7],   # top
    [0, 1, 5, 4],   # front
    [1, 2, 6, 5],   # right
    [2, 3, 7, 6],   # back
    [3, 0, 4, 7],   # left
]


class TestEdges:
    def test_edge_key_is_orientation_independent(self):
        assert edge_key(5, 2) == edge_key(2, 5) == (2, 5)

    def test_face_edges_go_round_the_face(self):
        assert face_edges([0, 3, 2, 1]) == [(0, 3), (2, 3), (1, 2), (0, 1)]

    def test_a_cube_has_twelve_edges(self):
        assert len(edges_of(CUBE_FACES)) == 12

    def test_every_edge_is_shared_by_two_faces(self):
        # The property the adjacency and loop logic both rely on.
        counts = {}
        for face in CUBE_FACES:
            for ekey in face_edges(face):
                counts[ekey] = counts.get(ekey, 0) + 1
        assert set(counts.values()) == {2}


class TestVertexDegrees:
    def test_cube_vertices_all_have_degree_three(self):
        assert set(vertex_degrees(CUBE_FACES).values()) == {3}

    def test_degrees_sum_to_twice_the_edges(self):
        degrees = vertex_degrees(CUBE_FACES)
        assert sum(degrees.values()) == 2 * len(edges_of(CUBE_FACES))

    def test_loop_ceiling_is_the_vertex_count(self):
        assert loop_ceiling(CUBE_FACES) == 8


class TestFaceAdjacency:
    def test_each_cube_face_has_four_neighbors(self):
        adjacency = face_adjacency(CUBE_FACES)
        assert all(len(nbrs) == 4 for nbrs in adjacency.values())

    def test_opposite_faces_are_not_adjacent(self):
        adjacency = face_adjacency(CUBE_FACES)
        assert 1 not in adjacency[0]      # top is not adjacent to bottom
        assert 4 not in adjacency[2]      # back is not adjacent to front

    def test_adjacency_is_symmetric(self):
        adjacency = face_adjacency(CUBE_FACES)
        for (face, neighbors) in adjacency.items():
            assert all(face in adjacency[nbr] for nbr in neighbors)

    def test_a_face_is_never_its_own_neighbor(self):
        adjacency = face_adjacency(CUBE_FACES)
        assert all(face not in nbrs for (face, nbrs) in adjacency.items())


class TestGrouping:
    ADJACENCY = face_adjacency(CUBE_FACES)

    # A shape the cube cannot express: one group of three plus two lone members.
    # A cube face is adjacent to every face but its opposite, so isolating a face
    # from a group of three would need all three to be its opposite, and it has
    # only one -- meaning any three or more cube faces are connected, and the most
    # disconnection available is 1 + 1. Group SIZES need something else.
    CHAIN = {0: {1}, 1: {0, 2}, 2: {1}, 3: set(), 4: set()}

    def test_the_whole_solid_is_one_group(self):
        assert len(connected_groups(range(6), self.ADJACENCY)) == 1
        assert is_connected(range(6), self.ADJACENCY) is True

    def test_two_opposite_faces_are_two_groups(self):
        # Bottom and top share no edge, so they cannot be one group.
        assert len(connected_groups([0, 1], self.ADJACENCY)) == 2
        assert is_connected([0, 1], self.ADJACENCY) is False

    def test_only_the_members_given_are_traversed(self):
        """A group stops at the edge of the set, even though the faces continue.
        This is what lets a caller ask about one face of a puzzle at a time."""
        assert len(connected_groups([0, 2], self.ADJACENCY)) == 1
        assert largest_group([0, 2], self.ADJACENCY) == 2

    def test_largest_group_of_nothing_is_zero(self):
        assert largest_group([], self.ADJACENCY) == 0

    def test_empty_is_not_connected(self):
        assert is_connected([], self.ADJACENCY) is False

    def test_largest_group_picks_the_biggest_not_the_total(self):
        """The distinction the quiet-patch measure rests on: five untouched faces
        in three separate groups is not the same defect as five in one."""
        assert len(connected_groups(range(5), self.CHAIN)) == 3
        assert largest_group(range(5), self.CHAIN) == 3

    def test_a_lone_member_is_a_group_of_one(self):
        assert largest_group([3], self.CHAIN) == 1


class TestPuzzleMeasures:
    def test_loop_edges_closes_the_loop(self):
        """The stored form does not repeat the first vertex, so the closing edge
        has to be inferred -- get that wrong and every measure is off by one."""
        assert loop_edges([0, 1, 2, 3]) == {(0, 1), (1, 2), (2, 3), (0, 3)}

    def test_walls_count_a_face_boundary(self):
        loop = loop_edges([0, 3, 2, 1])          # exactly the bottom face
        walls = walls_per_face(CUBE_FACES, loop)
        assert walls[0] == 4                     # bottom: all four edges
        assert walls[1] == 0                     # top: none
        assert walls[2] == 1                     # each side: one

    def test_quiet_faces_are_the_zero_clue_ones(self):
        loop = loop_edges([0, 3, 2, 1])
        assert quiet_faces(CUBE_FACES, loop) == {1}

    def test_largest_quiet_patch_of_one_face_loop(self):
        # Only the top face is untouched, so the biggest blank patch is 1.
        assert largest_quiet_patch(CUBE_FACES, loop_edges([0, 3, 2, 1])) == 1

    def test_scattered_blanks_score_lower_than_one_big_patch(self):
        """Six untouched faces in two groups of three must measure 3, not 6 --
        the distinction the whole measure rests on, since scattered blanks are
        fine and one big blank area is the defect.

        Uses the octahedron, whose eight triangles the loop can split evenly; a
        cube can't show this, since its top face borders all four sides.
        """
        faces = grid_topology.load_grid(DATA_DIR / 'O.json')['faces']
        adjacency = face_adjacency(faces)
        quiet = quiet_faces(faces, loop_edges([0, 2, 1, 3]))
        assert largest_quiet_patch(faces, loop_edges([0, 2, 1, 3])) == largest_group(
            quiet, adjacency)
        # However the faces fall, no patch can be bigger than the quiet set.
        assert largest_quiet_patch(faces, loop_edges([0, 2, 1, 3])) <= len(quiet)

    def test_passing_adjacency_in_gives_the_same_answer(self):
        loop = loop_edges([0, 3, 2, 1])
        assert (largest_quiet_patch(CUBE_FACES, loop, face_adjacency(CUBE_FACES))
                == largest_quiet_patch(CUBE_FACES, loop))


class TestAgainstRealData:
    """The measures have to hold on the actual grids, not just a cube."""

    @pytest.mark.parametrize('stem', ['cube', 'O', 'D', 'dbD'])
    def test_stored_puzzles_measure_sanely(self, stem):
        faces = grid_topology.load_grid(DATA_DIR / f'{stem}.json')['faces']
        puzzles = json.loads(
            (DATA_DIR / f'{stem}-puzzles.json').read_text())['puzzles']
        for puzzle in puzzles:
            loop = loop_edges(puzzle['solution'])
            assert len(loop) == len(puzzle['solution'])
            # The loop is a simple cycle through vertices, so it cannot use more
            # edges than there are vertices.
            assert len(loop) <= loop_ceiling(faces)
            assert 0 <= largest_quiet_patch(faces, loop) < len(faces)

    def test_clues_agree_with_the_walls_the_loop_uses(self):
        """Every stored clue must equal the wall count this module computes --
        which is the same claim test_data_puzzles makes, arrived at
        independently, so agreement means both are right about the format."""
        faces = grid_topology.load_grid(DATA_DIR / 'D.json')['faces']
        data = json.loads((DATA_DIR / 'D-puzzles.json').read_text())
        for puzzle in data['puzzles']:
            walls = walls_per_face(faces, loop_edges(puzzle['solution']))
            for (fkey, clue) in enumerate(puzzle['clues']):
                if clue != -1:
                    assert walls[fkey] == clue

    def test_same_patch_measure_as_grid_topology(self):
        """genSliPuzzles measures the same quantity from a painted REGION, and
        this module from a stored SOLUTION. They must agree, or the generator will
        optimize one thing while the report shows another."""
        from genSliPuzzles import RegionColoring

        grid = grid_topology.load_grid(DATA_DIR / 'dtO.json')
        mesh = Mesh.from_vertices_and_faces(grid['vertices'], grid['faces'])
        coloring = RegionColoring(mesh, None)
        faces = grid['faces']
        adjacency = face_adjacency(faces)

        # A handful of grown regions, so this isn't testing one lucky shape.
        for size in (4, 8, 12, 16):
            region = coloring.grow_region(size)
            from_region = coloring.largest_quiet_patch(region)
            loop = {edge_key(*ekey) for ekey in mesh.edges()
                    if len({f for f in mesh.edge_faces(ekey) if f is not None}
                           & region) == 1}
            from_loop = largest_quiet_patch(faces, loop, adjacency)
            assert from_region == from_loop, f'disagree on a region of {size}'
