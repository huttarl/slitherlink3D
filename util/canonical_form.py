"""Hart's canonical form: the one shape in a polyhedron's combinatorial family
whose faces are all flat and whose every edge grazes one common sphere.

Shared rather than kept in the generator that first wanted it, because "the right
faces meeting in the right way, but the wrong shape" is a problem several of the
scripts have and the imported grids have too. A C70 straight off a point
relaxation has bonds varying by a factor of 1.8; canonicalized it holds them
inside 1.3, in line with the fullerenes already in data/. Canonicalizing moves
vertices but never changes which of them meet, so whatever structure a generator
worked out survives having its shape put right.

The method (Hart, "Calculating Canonical Polyhedra", and what polyHédronisme
canonicalizes with): replace each face by the pole of its plane, nudged toward
putting that face's edges at distance 1 from the centre. That gives the dual;
doing it again gives the original back, a little nearer canonical. A canonical
solid and its dual are canonical TOGETHER -- tangent to the same sphere at the
same points -- which is why alternating between them settles both.

Needs numpy, unlike grid_checks and grid_topology, which are deliberately
stdlib-only so that genPrism needs nothing installed. Only the scripts that
already require numpy can use this.

For a triangulation there is also polar_dual in genGoldberg.py: the exact
one-shot reciprocal, whose faces come out flat to floating-point noise rather
than approaching flatness. Taking that as the last step, after canonicalizing,
gets both -- canonical proportions and exactly flat faces.
"""
import numpy as np

# How still the iteration has to go to count as settled, set by what the output can
# hold: grid coordinates are written to 6 decimals, so movement at this size cannot
# change a data file whatever it does, and on a solid of radius 1 it is a hundredth
# of the width of an atom. Tighter thresholds were tried and are not worth their
# rounds -- convergence here is linear, so C70 needs about 2000 rounds to reach 1e-8
# and would need thousands more for 1e-12, all of it in digits that get rounded away
# before anyone sees them.
SETTLED = 1e-8

# A backstop, not a target. Both fullerene recipes settle well inside it, and a
# solid that doesn't gets said so out loud by the caller rather than silently
# written out mid-drift.
MAX_ROUNDS = 2000


def reciprocate(points, faces):
    """Each face's reciprocal point: where the dual solid's vertex belongs.

    The pole of the face's plane -- the point p with x.p = 1 across that plane --
    moved halfway toward putting the face's own edges at distance 1 from the
    centre. Reciprocating alone would only dualize back and forth; that nudge is
    what makes repeating it converge. Halving the discrepancy rather than taking
    it whole keeps the iteration from overshooting and ringing.

    @param points: the solid's vertices, (n, 3)
    @param faces: its faces, each a sequence of indices into points, wound
        consistently -- the winding decides which way the normals point
    @returns one point per face, (len(faces), 3)
    """
    poles = np.empty((len(faces), 3))
    for (f, face) in enumerate(faces):
        corners = points[list(face)]
        middle = corners.mean(axis=0)
        # Newell's normal, taken about the centroid, so a face whose first three
        # corners fall nearly in line can't spoil it -- the same reasoning as
        # face_normal in grid_checks.py.
        spokes = corners - middle
        normal = np.cross(spokes, np.roll(spokes, -1, axis=0)).sum(axis=0)
        normal /= np.linalg.norm(normal)
        # The foot of the perpendicular from the centre to the face's plane. The
        # pole is its reciprocal: same direction, reciprocal distance.
        foot = np.dot(middle, normal) * normal
        pole = foot / np.dot(foot, foot)
        # How far this face's edges pass from the centre, averaged. The canonical
        # form wants that to be exactly 1.
        following = np.roll(corners, -1, axis=0)
        along = following - corners
        stride = (np.einsum('ij,ij->i', along, corners)
                  / np.einsum('ij,ij->i', along, along))
        grazing = np.linalg.norm(corners - stride[:, None] * along, axis=1).mean()
        poles[f] = pole * (1 + grazing) / 2
    return poles


def canonicalize(points, faces, dual_faces, rounds=MAX_ROUNDS):
    """Move a solid's vertices to their canonical positions.

    @param points: its vertices, (n, 3), roughly placed already -- this settles a
        shape, it does not find a structure
    @param faces: its faces, as index sequences into points
    @param dual_faces: the dual's faces, as index sequences into `faces`. That is
        what polar_dual returns alongside its vertices, so a caller that built the
        solid by reciprocation already has it.
    @returns (points, rounds_used, last_shift) -- the caller reports, so that this
        module needs no opinion about where diagnostics go. A last_shift above
        SETTLED means it ran out of rounds and the shape is still drifting.
    """
    shift = float('inf')
    for round_number in range(rounds):
        # Out to the dual and back: one full pass over the pair.
        moved = reciprocate(reciprocate(points, faces), dual_faces)
        shift = np.abs(moved - points).max()
        points = moved
        if shift < SETTLED:
            return (points, round_number + 1, shift)
    return (points, rounds, shift)
