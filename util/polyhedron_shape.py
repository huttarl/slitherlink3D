"""Giving a solid its shape, once a generator has settled its structure.

Two passes, both of which move vertices without ever changing which of them meet,
so whatever combinatorics a generator worked out survives being reshaped. They
answer to different ideas of "right", and which one a solid wants is a real choice:

  canonicalize -- Hart's canonical form: every face flat and every edge grazing one
      common sphere. Mathematically distinguished, unique up to rotation, and the
      right answer when nothing else is known about the shape. But tangency to a
      single sphere is a ROUNDNESS condition, and it buys that roundness with
      unequal edges: it draws C70 exactly as round as a buckyball, when the real
      molecule is the rugby ball, and lets its edges vary by 26% to do it.

  regularize -- every face as near as possible to a regular polygon of one shared
      edge length. This is what a fullerene actually approximates, and it has no
      weight to tune, so the shape it gives is derived rather than chosen. It puts
      C70 at 1.15 times as long as C60, against about 1.11 in the molecule, with
      edges inside 6%. The price is flatness: regular and planar cannot both hold
      on such a cage, so faces end up bowed by around 2% of the radius -- as the
      molecule's own hexagons are, on a curved cage.

Shared rather than kept in the generator that first wanted them, because "the right
faces meeting in the right way, but the wrong shape" is a problem several of the
scripts have and the imported grids have too.

The canonical method (Hart, "Calculating Canonical Polyhedra", and what
polyHédronisme canonicalizes with): replace each face by the pole of its plane,
nudged toward putting that face's edges at distance 1 from the centre. That gives
the dual; doing it again gives the original back, a little nearer canonical. A
canonical solid and its dual are canonical TOGETHER -- tangent to the same sphere
at the same points -- which is why alternating between them settles both.

regularize is checked against a solid that can satisfy it exactly: run on the
truncated icosahedron it reproduces it, edges equal to 1 part in 10^4 and faces flat
to 5e-16, tidying away even the 0.9% edge spread that data/tI.json carries. A
shaping pass that is the identity where the objective is achievable is one to trust
where it isn't.

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


def regularize(points, faces, rounds=MAX_ROUNDS, step=0.3):
    """Pull every face toward a regular polygon of one shared edge length.

    Each round: measure the solid's mean edge, then for every face work out the
    regular polygon of that side length lying in the face's own plane, and move each
    corner a fraction of the way toward where that polygon wants it. A corner
    belonging to three faces hears three opinions and takes their average, so what
    settles is the least-squares compromise between them -- which is what makes this
    a single objective with nothing to weight.

    @param points: the solid's vertices, (n, 3), already roughly in shape
    @param faces: its faces, as index sequences, wound consistently
    @param rounds: iterations; unlike canonicalize this has no convergence test, the
        compromise being approached steadily rather than reached
    @param step: how far to move toward the ideal each round. Well under 1, because
        each face pulls independently and a full step overshoots into ringing.
    @returns the points, reshaped, scaled to a circumradius of 1
    """
    points = points.copy()
    edges = [(a, b) for face in faces
             for (a, b) in zip(face, list(face[1:]) + [face[0]])]
    first = np.array([a for (a, b) in edges])
    second = np.array([b for (a, b) in edges])

    for _ in range(rounds):
        # One size for the whole solid, so the faces cannot settle at sizes that
        # suit themselves and leave the edges between them unequal.
        side = np.linalg.norm(points[second] - points[first], axis=1).mean()
        wanted = np.zeros_like(points)
        opinions = np.zeros(len(points))
        for face in faces:
            corners = points[list(face)]
            middle = corners.mean(axis=0)
            spokes = corners - middle
            normal = np.cross(spokes, np.roll(spokes, -1, axis=0)).sum(axis=0)
            normal /= np.linalg.norm(normal)
            # A frame in the face's own plane. The ideal polygon is built in it, so
            # this asks the face to be regular where it lies rather than to move.
            flat = spokes - np.outer(spokes @ normal, normal)
            across = flat[0] / np.linalg.norm(flat[0])
            up = np.cross(normal, across)
            sides = len(face)
            radius = side / (2 * np.sin(np.pi / sides))
            # Where to start the ideal polygon's corners: the average of where the
            # real ones are, as a circular mean. Anchoring it to the first corner
            # instead would hand that corner's own error to the whole face as a
            # rotation.
            angles = np.arctan2(flat @ up, flat @ across)
            turns = 2 * np.pi * np.arange(sides) / sides
            offset = np.angle(np.exp(1j * (angles - turns)).mean())
            ideal = middle + radius * (np.outer(np.cos(turns + offset), across)
                                       + np.outer(np.sin(turns + offset), up))
            np.add.at(wanted, list(face), ideal)
            np.add.at(opinions, list(face), 1.0)
        points += step * (wanted / opinions[:, None] - points)
        points -= points.mean(axis=0)
    return points / np.abs(np.linalg.norm(points, axis=1)).max()


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
