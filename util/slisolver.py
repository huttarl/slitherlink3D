"""Slitherlink puzzle solver."""
import itertools
import time
# import networkx as nx
# from compas.datastructures import Mesh

def solution_is_unique(clues, num_clues, solution, mesh, dualG, time_budget=None):
    """Return True if given solution is the only possible one for given clues.

    Args:
        clues: List of (face, num_walls) tuples representing the clues
        num_clues: How many clues from the list to use
        solution: The known solution (list of vertex indices forming a loop)
        mesh: COMPAS Mesh representing the grid
        dualG: NetworkX dual graph with nodes for faces (may not be needed)
        time_budget: Optional maximum number of seconds to spend searching.
            If the search exceeds it, give up and return False ("not proven
            unique"). Search times have a heavy tail — a rare pathological
            clue set can take minutes where most take milliseconds — and
            this bounds them. Giving up is conservative for puzzle
            generation: a False can only make the generator use more clues
            (or discard the region); uniqueness is never claimed without a
            completed search.

    Returns:
        True if there is exactly one solution; False if multiple solutions
        exist, or if the time budget ran out before uniqueness was proven.
    """
    deadline = None if time_budget is None else time.monotonic() + time_budget
    budget_exhausted = [False]  # mutable so dfs_search can set it

    # Initialize edge states
    for ekey in mesh.edges():
        mesh.edge_attribute(ekey, 'guess', 'unknown')

    # Apply the clues to the mesh
    apply_clues(clues, num_clues, mesh)

    # Counter to track how many solutions we've found
    solutions_found = [0]  # Use list so it's mutable in nested function

    def dfs_search(depth=0):
        """Depth-first search for solutions with constraint propagation.

        Returns True if search should continue, False if we should abort
        (because we've found multiple solutions, or ran out of time).
        """
        if deadline is not None and time.monotonic() > deadline:
            budget_exhausted[0] = True
            return False  # Abort the entire search.

        # Apply deterministic inference rules until no more progress
        contradiction = not propagate_constraints(mesh, clues, num_clues)

        if contradiction:
            # This branch is invalid, backtrack
            return True

        # If all edges are determined, this branch is terminal.
        if is_complete_solution(mesh):
            if is_valid_loop(mesh):
                # TODO: check whether this solution is identical to the known one,
                # and if not, we've found multiple solutions, so abort.
                solutions_found[0] += 1
                if solutions_found[0] > 1:
                    # Found multiple solutions; abort search.
                    return False
            # Either a valid first solution, or invalid — either way, no deeper search.
            return True

        # Choose an edge to guess on
        edge_to_guess = select_edge_for_branching(mesh)

        if edge_to_guess is None:
            # No edges left to guess on but solution incomplete - contradiction
            return True

        # Save current state
        outer_state = save_state(mesh)

        # Try both possibilities for this edge
        for guess_value in ['filledIn', 'ruledOut']:

            # Make the guess
            mesh.edge_attribute(edge_to_guess, 'guess', guess_value)

            # Recursively search
            should_continue = dfs_search(depth + 1)

            # Restore state for next branch
            restore_state(mesh, outer_state)

            if not should_continue:
                # Found multiple solutions, abort entire search
                return False

        return True

    # Start the search
    dfs_search()

    # Return True if exactly one solution was found. An exhausted time
    # budget means the search was incomplete, so uniqueness is unproven
    # even if one solution was found before time ran out.
    return solutions_found[0] == 1 and not budget_exhausted[0]


def apply_clues(clues, num_clues, mesh):
    """Apply the given clues to the mesh by setting face clue values.

    Remember that the 'clue' attribute, when present, is the same as
    the 'num_walls' attribute, but 'num_walls' is present on all faces,
    whereas 'clue' is only present on faces with clues."""
    # Initialize all faces with no clue.
    for fkey in mesh.faces():
        mesh.unset_face_attribute(fkey, 'clue')

    # Apply the clues we're using to the mesh.
    for face, num_walls in itertools.islice(clues, num_clues):
        mesh.face_attribute(face, 'clue', num_walls)


def propagate_constraints(mesh, clues, num_clues):
    """Apply deterministic inference rules until no more progress can be made.

    Alternates apply_vertex_rules, apply_clue_rules, apply_pattern_rules and
    apply_color_rules in a fixed-point loop, cheapest first. Bails on the
    first contradiction from any family.

    Each pass either changes at least one edge or returns. Since the
    set of edge states is finite and rules only refine 'unknown' edges
    (never reverting determined ones), the loop terminates in O(E)
    rule-firings.

    The clues/num_clues arguments are not read here — clue values live
    in face attributes set earlier by apply_clues. They're kept in the
    signature for compatibility with the calling site.

    Returns False if a contradiction is detected, True otherwise.
    """
    while True:
        # The cheap, local rules first, run to their own fixed point.
        (ok, changed_v) = apply_vertex_rules(mesh)
        if not ok:
            return False
        (ok, changed_c) = apply_clue_rules(mesh)
        if not ok:
            return False
        (ok, changed_p) = apply_pattern_rules(mesh)
        if not ok:
            return False
        if changed_v or changed_c or changed_p:
            continue

        # Those two have stalled, so now it's worth paying for coloring,
        # which rebuilds a union-find over all the faces. Measured: running it
        # every round instead made uniqueness checks 25-40% slower, because it
        # rarely finds anything the local rules haven't already, and when it
        # does the local rules usually take it from there.
        (ok, changed_col) = apply_color_rules(mesh)
        if not ok:
            return False
        if not changed_col:
            return True  # No family can deduce anything further.


class FaceColoring:
    """Tracks which faces must be the same 'color' as each other, and which
    must be opposite, without ever deciding which color is which.

    Union-find over faces, but each face also carries one parity bit saying
    whether it is the same as, or opposite to, its parent. So the structure
    answers "are these two faces the same color?" -- never "is this face
    inside?".

    That RELATIVE-only design is not a convenience, it's forced by our
    topology. On a flat Slitherlink grid the region outside the border is
    known to be outside, which anchors every color absolutely. A polyhedron
    has no outer face: a loop cuts the surface into two patches and neither is
    canonically "inside", exactly as genSliPuzzles' Phase A picks its red and
    blue seed faces arbitrarily. Relative relationships are all there is, and
    they're enough -- colorings that never connect to each other still yield
    deductions in their own neighbourhoods.
    """

    def __init__(self):
        # face -> parent face in the union-find forest.
        self.parent = {}
        # face -> True if this face is the OPPOSITE color from its parent.
        self.flipped = {}
        # root face -> size of its group (for union by size).
        self.size = {}

    def _find(self, face):
        """Return (root, opposite): the group's representative, and whether
        `face` is the opposite color from it. Compresses the path walked."""
        if face not in self.parent:
            self.parent[face] = face
            self.flipped[face] = False
            self.size[face] = 1
            return (face, False)

        # Walk up to the root, accumulating parity as we go.
        root = face
        opposite = False
        while self.parent[root] != root:
            opposite ^= self.flipped[root]
            root = self.parent[root]

        # Path compression: re-point everything we walked past straight at the
        # root, each with its own parity relative to the root. Note we must
        # read flipped[current] before overwriting it.
        current = face
        current_opposite = opposite
        while self.parent[current] != current:
            next_face = self.parent[current]
            next_opposite = current_opposite ^ self.flipped[current]
            self.parent[current] = root
            self.flipped[current] = current_opposite
            current = next_face
            current_opposite = next_opposite

        return (root, opposite)

    def relate(self, face1, face2, opposite):
        """Record that the two faces are opposite colors (opposite=True) or
        the same color (opposite=False).

        Returns False if that contradicts what we already know about them,
        in which case no solution is possible from here.
        """
        (root1, opposite1) = self._find(face1)
        (root2, opposite2) = self._find(face2)

        if root1 == root2:
            # Already in one group, so their relation is already fixed: this
            # new claim either agrees with it or the puzzle is contradictory.
            return (opposite1 ^ opposite2) == opposite

        # Attach the smaller group to the larger, choosing the parity bit that
        # makes the requested relation hold.
        if self.size[root1] < self.size[root2]:
            (root1, root2) = (root2, root1)
            (opposite1, opposite2) = (opposite2, opposite1)
        self.parent[root2] = root1
        self.flipped[root2] = opposite1 ^ opposite ^ opposite2
        self.size[root1] += self.size[root2]
        return True

    def relation(self, face1, face2):
        """True if the faces must be opposite colors, False if they must be
        the same, or None if nothing relates them yet."""
        (root1, opposite1) = self._find(face1)
        (root2, opposite2) = self._find(face2)
        if root1 != root2:
            return None
        return opposite1 ^ opposite2


def apply_color_rules(mesh):
    """Apply the 'coloring' inference to every face and edge (one pass).

    The loop is a closed curve on the sphere, so (Jordan curve theorem) it
    divides the faces into two patches. Hence, in any solution:

        an edge is filled  <=>  its two faces are in DIFFERENT patches
        an edge is ruled out  <=>  its two faces are in the SAME patch

    Read left to right, determined edges tell us how faces relate. Read right
    to left -- which is where the deductive power lies -- known relationships
    force the edges between them:

        faces known opposite, edge between them unknown -> fill it in
        faces known same, edge between them unknown     -> rule it out

    The relationships travel along paths of determined edges, so this reaches
    conclusions the local rules cannot. Three faces meeting at a vertex, with
    two of the three edges between them already decided, force the third --
    and longer chains force edges arbitrarily far from anything decided.

    Worth knowing why this rule is strong: on a sphere, "every vertex has an
    even number of filled edges" (what apply_vertex_rules enforces locally) is
    equivalent, by planar duality, to "the filled edges are exactly the
    boundary between two sets of faces" (what this enforces globally). So this
    rule sees a topological constraint the per-vertex rule cannot.

    Returns (ok, changed) -- same convention as the other rule families.
    """
    coloring = FaceColoring()

    # Every already-decided edge tells us how its two faces relate.
    for ekey in mesh.edges():
        guess = mesh.edge_attribute(ekey, 'guess')
        if guess == 'unknown':
            continue
        (face1, face2) = mesh.edge_faces(ekey)
        if face1 is None or face2 is None:
            continue  # A boundary edge; shouldn't occur on a closed mesh.
        if not coloring.relate(face1, face2, opposite=(guess == 'filledIn')):
            return False, False

    # Any undecided edge whose faces are already related is now forced.
    changed = False
    for ekey in mesh.edges():
        if mesh.edge_attribute(ekey, 'guess') != 'unknown':
            continue
        (face1, face2) = mesh.edge_faces(ekey)
        if face1 is None or face2 is None:
            continue
        opposite = coloring.relation(face1, face2)
        if opposite is None:
            continue  # Nothing known about these two faces yet.
        mesh.edge_attribute(ekey, 'guess', 'filledIn' if opposite else 'ruledOut')
        changed = True

    return True, changed


def face_sides(mesh, fkey):
    """How many edges the given face has."""
    return len(mesh.face_vertices(fkey))


def face_edges_at_vertex(mesh, fkey, vkey):
    """The (two) edges of `fkey` that meet at `vkey`, and the other edges
    there. Returns (own, others) as lists of edge keys."""
    own = []
    others = []
    for nbr in mesh.vertex_neighbors(vkey):
        ekey = (vkey, nbr)
        if fkey in mesh.edge_faces(ekey):
            own.append(ekey)
        else:
            others.append(ekey)
    return (own, others)


def _set_edges(mesh, ekeys, guess):
    """Set each unknown edge to `guess`. Returns (ok, changed): ok is False if
    an edge already says the opposite, which means the position is dead."""
    changed = False
    for ekey in ekeys:
        current = mesh.edge_attribute(ekey, 'guess')
        if current == 'unknown':
            mesh.edge_attribute(ekey, 'guess', guess)
            changed = True
        elif current != guess:
            return (False, changed)
    return (True, changed)


def is_minus_one_face(mesh, fkey):
    """True if this face's clue is one less than its number of sides, i.e. it
    has a deficit of 1: exactly one of its edges is ruled out."""
    clue = mesh.face_attribute(fkey, 'clue')
    return clue is not None and clue == face_sides(mesh, fkey) - 1


def apply_pattern_rules(mesh):
    """Tier-1 clue patterns: the ones that determine edges outright.

    These are the deductions a player makes at a glance from clue values,
    which the plain per-face and per-vertex rules can't reach. They are stated
    in terms of a face's DEFICIT -- sides minus clue -- rather than the clue
    itself, so they hold for any face size. A "-1 face" has deficit 1: exactly
    one of its edges is ruled out.

    Rule A (-1 face at a settled vertex). Every vertex of a -1 face has
    exactly two filled edges: the face contributes two edges there and they
    can't both be ruled out, since that would be two ruled-out edges in a face
    allowed only one. So if every OTHER edge at that vertex is already ruled
    out, both of the face's edges there must be filled.

    Rule B (clue-1 face at a settled vertex), the mirror image. A face with
    clue 1 has just one filled edge, so it can't have two filled at one
    vertex. With every other edge at that vertex ruled out, the vertex can't
    reach two filled, so it must have none: both of the face's edges there are
    ruled out.

    Rule C (two -1 faces meeting at a vertex but NOT sharing an edge). Each
    contributes at least one filled edge at that vertex (Rule A's reasoning),
    and a vertex holds at most two, so each contributes exactly one and every
    other edge there is ruled out. Since each face's single ruled-out edge is
    therefore at this vertex, all of its other edges are filled.

    Note Rule C needs no condition on the vertex's degree: "at most two
    filled" does the work.

    Rule D (two -1 faces that DO share an edge). Take the shared edge e, with
    endpoints P and Q. Each face's edges away from both P and Q are filled.

    Proof for face A: suppose A's one ruled-out edge were somewhere other than
    e or A's edges at P and Q. Then e and both of A's edges at P and Q are
    filled -- so at P, e plus A's edge there make two filled, forcing B's edge
    at P to be ruled out, and the same at Q. That gives B two ruled-out edges,
    which a -1 face cannot have. So A's ruled-out edge is among e and its two
    neighbours in A, and every other edge of A is filled. Symmetrically for B.

    Rule D says nothing about e itself. That is the exception discussed
    elsewhere: if the loop were exactly the boundary of A and B together, e is
    ruled out and both faces are still satisfied. Excluding that possibility
    needs a global argument (there is loop elsewhere), so the "e is filled"
    half is deliberately left out here. Note the rest of Rule D holds even in
    that exceptional case.

    Nothing else is forced by a shared-edge pair. What IS true there is "not
    zero filled at each end of e", which determines no edge on its own; that
    belongs in a future tier 2 alongside "exactly one of these two" and "both
    or neither".

    The (clue 0, clue 1) and (clue 0, -1) vertex patterns need no code of
    their own: a clue-0 face has all its edges ruled out by the ordinary clue
    rule, which then supplies exactly the "every other edge here is ruled out"
    context that Rules A and B look for.

    Returns (ok, changed) -- same convention as the other rule families.
    """
    changed = False

    # --- Rules A and B: one face, at a vertex whose other edges are settled.
    for fkey in mesh.faces():
        clue = mesh.face_attribute(fkey, 'clue')
        if clue is None:
            continue
        sides = face_sides(mesh, fkey)
        if clue == sides - 1:
            target = 'filledIn'      # Rule A
        elif clue == 1:
            target = 'ruledOut'      # Rule B
        else:
            continue

        for vkey in mesh.face_vertices(fkey):
            (own, others) = face_edges_at_vertex(mesh, fkey, vkey)
            if len(own) != 2:
                continue  # Shouldn't happen on a closed mesh.
            if any(mesh.edge_attribute(e, 'guess') != 'ruledOut' for e in others):
                continue  # The vertex isn't settled enough to conclude anything.
            (ok, did) = _set_edges(mesh, own, target)
            if not ok:
                return (False, changed)
            changed = changed or did

    # --- Rule D: two -1 faces sharing an edge.
    for ekey in mesh.edges():
        (face1, face2) = mesh.edge_faces(ekey)
        if face1 is None or face2 is None:
            continue
        if not (is_minus_one_face(mesh, face1) and is_minus_one_face(mesh, face2)):
            continue
        (p, q) = ekey
        for face in (face1, face2):
            # Every edge of this face that touches neither end of the shared
            # edge. (For a triangle that's nothing, since all three of its
            # edges touch P or Q.)
            away = [e for e in mesh.face_halfedges(face)
                    if p not in e and q not in e]
            (ok, did) = _set_edges(mesh, away, 'filledIn')
            if not ok:
                return (False, changed)
            changed = changed or did

    # --- Rule C: two -1 faces meeting at a vertex only.
    for vkey in mesh.vertices():
        minus_one_faces = [f for f in mesh.vertex_faces(vkey)
                           if f is not None and is_minus_one_face(mesh, f)]
        for i in range(len(minus_one_faces)):
            for j in range(i + 1, len(minus_one_faces)):
                (face1, face2) = (minus_one_faces[i], minus_one_faces[j])
                if face2 in mesh.face_neighbors(face1):
                    continue  # They share an edge: nothing forced (see above).

                (own1, _) = face_edges_at_vertex(mesh, face1, vkey)
                (own2, _) = face_edges_at_vertex(mesh, face2, vkey)
                at_vertex = set(own1) | set(own2)

                # Everything else at this vertex is ruled out...
                elsewhere = [(vkey, nbr) for nbr in mesh.vertex_neighbors(vkey)
                             if (vkey, nbr) not in at_vertex
                             and (nbr, vkey) not in at_vertex]
                (ok, did) = _set_edges(mesh, elsewhere, 'ruledOut')
                if not ok:
                    return (False, changed)
                changed = changed or did

                # ...and each face's edges away from this vertex are filled.
                for (face, own) in ((face1, own1), (face2, own2)):
                    away = [e for e in mesh.face_halfedges(face)
                            if vkey not in e]
                    (ok, did) = _set_edges(mesh, away, 'filledIn')
                    if not ok:
                        return (False, changed)
                    changed = changed or did

    return (True, changed)


def propagate_with_lookahead(mesh, clues, num_clues, depth=1):
    """Propagate, then reason by cases: what a player does when stuck.

    Plain propagate_constraints only draws conclusions that follow from a
    single vertex or face at a time, so it stalls on any position where the
    next step needs "suppose this edge were filled...". Players don't stop
    there -- they try the supposition, follow it a little way, and if it breaks
    a rule they conclude the opposite. That is exactly what this adds:

        assume an unknown edge is filled; propagate; if that contradicts,
        the edge must be ruled out (and vice versa)

    `depth` is how many nested suppositions are allowed. depth=0 is plain
    propagation; depth=1 is one supposition at a time, which is what a
    competent player does routinely; depth>=2 means suppositions inside
    suppositions, which is where it starts to feel like guessing rather than
    solving. So depth doubles as our difficulty dial.

    Everything here is sound by construction: it only ever concludes the
    negation of a supposition that provably breaks a rule. That makes it a
    useful oracle for checking hand-written patterns (set up the pattern's
    premises, ask what lookahead forces, compare) -- but it does not replace
    them. Logically it subsumes apply_pattern_rules, yet a player recognises a
    clue pattern at a glance while a supposition costs real effort, so the two
    say different things about difficulty. Patterns are the cheap, human-like
    reasoning; this is the deliberate case analysis after a stall.

    Returns False if the position is contradictory, True otherwise. Edge
    states are left at whatever was deduced.
    """
    if not propagate_constraints(mesh, clues, num_clues):
        return False
    if depth <= 0:
        return True

    # Keep sweeping: each forced edge may unlock others.
    progress = True
    while progress:
        progress = False
        for ekey in list(mesh.edges()):
            if mesh.edge_attribute(ekey, 'guess') != 'unknown':
                continue

            forced = None
            for (supposition, opposite) in (('filledIn', 'ruledOut'),
                                            ('ruledOut', 'filledIn')):
                saved = save_state(mesh)
                mesh.edge_attribute(ekey, 'guess', supposition)
                survived = propagate_with_lookahead(mesh, clues, num_clues, depth - 1)
                restore_state(mesh, saved)
                if not survived:
                    forced = opposite
                    break

            if forced is not None:
                mesh.edge_attribute(ekey, 'guess', forced)
                # The new fact may cascade, and may even expose a
                # contradiction, in which case the whole position is dead.
                if not propagate_constraints(mesh, clues, num_clues):
                    return False
                progress = True

    return True


def solvable_by_deduction(mesh, clues, num_clues, depth=1):
    """Can this clue set be solved by reasoning alone, with no guessing?

    Applies the clues to a blank board, then deduces as far as `depth` allows.
    True only if every edge ends up determined and the result really is a
    single loop.

    Note this is a STRONGER property than solution_is_unique: a position
    determined entirely by sound rules admits no other solution, so anything
    solvable by deduction is automatically unique. The converse fails badly --
    most minimal-clue puzzles are unique but need search.
    """
    for ekey in mesh.edges():
        mesh.edge_attribute(ekey, 'guess', 'unknown')
    apply_clues(clues, num_clues, mesh)

    if not propagate_with_lookahead(mesh, clues, num_clues, depth):
        return False
    return is_complete_solution(mesh) and is_valid_loop(mesh)


def apply_vertex_rules(mesh):
    """Apply vertex-balance inference at every vertex (one pass).

    In a valid Slitherlink loop, each vertex has exactly 0 or 2 filled
    edges incident. Given the current per-vertex counts of filled (f),
    unknown (u), and ruled-out edges, the deterministic inferences are:

        f >= 3                  -> contradiction
        f == 1 and u == 0       -> contradiction (stuck at 1)
        f == 2 and u >= 1       -> all unknowns become 'ruledOut'
        f == 1 and u == 1       -> the unknown becomes 'filledIn'
        f == 0 and u == 1       -> the unknown becomes 'ruledOut'
        otherwise               -> nothing forced locally

    Returns:
        (ok, changed):
            ok      - False on contradiction; the caller should not
                      trust the resulting mesh state.
            changed - True if any edge's 'guess' attribute was updated.
    """
    changed = False
    for vkey in mesh.vertices():
        # Bucket the incident edges by their guess state (filled, unknown).
        filled = []
        unknown = []
        for nbr in mesh.vertex_neighbors(vkey):
            ekey = (vkey, nbr)
            g = mesh.edge_attribute(ekey, 'guess')
            if g == 'filledIn':
                filled.append(ekey)
            elif g == 'unknown':
                unknown.append(ekey)
        f = len(filled)
        u = len(unknown)

        # Contradictions: bail immediately, propagating whatever changed
        # earlier in this pass (the caller will discard the state anyway).
        if f > 2 or (f == 1 and u == 0):
            return False, changed

        # Forced inferences:
        if f == 2 and u >= 1:
            for ekey in unknown:
                mesh.edge_attribute(ekey, 'guess', 'ruledOut')
            changed = True
        elif (f, u) == (1, 1):
            mesh.edge_attribute(unknown[0], 'guess', 'filledIn')
            changed = True
        elif (f, u) == (0, 1):
            mesh.edge_attribute(unknown[0], 'guess', 'ruledOut')
            changed = True

    return True, changed


def apply_clue_rules(mesh):
    """Apply face/clue inference at every clued face (one pass).

    For a face with clue n and d edges around it, with f filled, u
    unknown, and r ruled out (f + r + u = d), the deterministic
    inferences are:

        f > n                       -> contradiction (over the limit)
        f + u < n                   -> contradiction (can't reach n)
        f == n and u >= 1           -> all unknowns become 'ruledOut'
        f + u == n and u >= 1       -> all unknowns become 'filledIn'
        otherwise                   -> nothing forced locally

    Faces without a clue (face_attribute 'clue' unset / None) are skipped
    entirely — no constraint to enforce.

    Returns (ok, changed) — same convention as apply_vertex_rules.
    """
    changed = False
    for fkey in mesh.faces():
        n = mesh.face_attribute(fkey, 'clue')
        if n is None:
            continue

        # Bucket the face's edges by guess state.
        filled = []
        unknown = []
        for ekey in mesh.face_halfedges(fkey):
            g = mesh.edge_attribute(ekey, 'guess')
            if g == 'filledIn':
                filled.append(ekey)
            elif g == 'unknown':
                unknown.append(ekey)
        f = len(filled)
        u = len(unknown)

        # Contradictions: bail immediately.
        if f > n or f + u < n:
            return False, changed

        # Forced inferences (both guarded by u >= 1, since u == 0 means
        # there are no unknowns left to flip).
        if f == n and u >= 1:
            for ekey in unknown:
                mesh.edge_attribute(ekey, 'guess', 'ruledOut')
            changed = True
        elif f + u == n and u >= 1:
            for ekey in unknown:
                mesh.edge_attribute(ekey, 'guess', 'filledIn')
            changed = True

    return True, changed


def is_complete_solution(mesh):
    """Check if all edges have been determined (no 'unknown' edges remain)."""
    for ekey in mesh.edges():
        if mesh.edge_attribute(ekey, 'guess') == 'unknown':
            return False
    return True


def is_valid_loop(mesh):
    """Check if the current edge configuration forms a valid single loop.

    A valid solution must:
    - Have at least one filled edge
    - Each vertex incident to a filled edge has exactly 2 filled edges
      (other vertices have 0)
    - The filled edges form a single connected component (one cycle, not several)
    """
    # We can do this with less code using networkx, e.g. using nx.is_connected():
    #   G = nx.Graph()  # build from filled edges
    #   if G.number_of_edges() == 0: return False
    #   if any(d != 2 for _, d in G.degree()): return False
    #   return nx.is_connected(G)
    # But rolling our own is faster and more transparent.

    # Build adjacency dict for filled edges in one pass. len(adj[v]) doubles as
    # the per-vertex filled-edge degree, so we don't need a separate counter.
    adj = {}  # vertex key -> list of filled neighbors
    for ekey in mesh.edges():
        if mesh.edge_attribute(ekey, 'guess') == 'filledIn':
            (v1, v2) = ekey
            # setdefault(v, []): return adj[v], inserting [] first if v is new.
            # We then append to the (possibly new) list in place.
            adj.setdefault(v1, []).append(v2)
            adj.setdefault(v2, []).append(v1)

    # No filled edges at all -> not a loop.
    if not adj:
        return False

    # Every loop vertex must have exactly 2 filled edges, or equivalently,
    # 2 neighbors (connected to the current vertex by filled edges). Vertices not in
    # `adj` implicitly have 0, which is fine.
    if any(len(nbrs) != 2 for nbrs in adj.values()):
        return False

    # With every vertex of degree 0 or 2, the filled subgraph is a disjoint
    # union of simple cycles. Walk from any vertex to count the cycle's
    # length; if it equals the total vertex count, there's exactly one cycle.
    # (If it's smaller, this cycle is one of multiple disjoint ones.)
    start = next(iter(adj))  # Any vertex in adj works as a starting point.
    cur = start
    prev = None
    steps = 0
    # Walk until we return to start. The `prev is None` clause is needed
    # because cur == start initially; without it, the loop would exit
    # before taking a single step.
    while cur != start or prev is None:
        # Each vertex has degree 2, so adj[cur] has exactly two entries:
        # one is `prev` (where we came from), the other is where we go next.
        (a, b) = adj[cur]
        # Compute next BEFORE overwriting prev — otherwise the comparison
        # uses the new prev (== cur) and we'd march straight back to start.
        # On the first step prev is None and vertex keys are never None,
        # so the conditional picks `a`.
        next_vertex = a if a != prev else b
        prev = cur
        cur = next_vertex
        steps += 1

    return steps == len(adj)


def select_edge_for_branching(mesh):
    """Select an unknown edge for branching: the first one, in mesh order.

    Heuristics one might expect to beat this:
    - Choose edges adjacent to faces with clues
    - Choose edges where one choice would immediately cause propagation
    - Choose edges in high-degree vertices
    - Choose edges that continue the existing loop

    NOTE (July 2026): two such heuristics were implemented and benchmarked
    against this naive version on the snub dodecahedron (92 faces, 150
    edges) over 12 clue-set instances (4 clue counts x 3 orderings, 20s
    cap): (a) a weighted score (+20 per dangling-loop-end endpoint, +1 per
    determined incident edge, +4/+1/+6 for adjacent clued faces by
    tightness), and (b) chain-following (absolute priority to extending a
    dangling loop end). Naive won 8 of 12 pairwise against (a), which won
    2, with 3 timeouts each (naive 80.8s total vs 82.7s); (b) was worst
    (96.6s, 4 timeouts). The per-call scoring overhead outweighed any
    search-tree reduction, and no selector helped the pathological
    instances, which dominate total time. Those are bounded instead by
    solution_is_unique's time_budget. So we keep the cheap naive pick.

    Returns an edge key or None if no unknown edges exist.
    """
    for ekey in mesh.edges():
        if mesh.edge_attribute(ekey, 'guess') == 'unknown':
            return ekey
    return None


def save_state(mesh):
    """Save the current state of all edge guesses.
    It's a list of all edge guesses, in the same order as the mesh edges."""
    return mesh.edges_attribute('guess')


def restore_state(mesh, state):
    """Restore edge guesses to a saved state.
    state is a list of all edge guesses, in the same order as the mesh edges."""
    for ekey, guess in zip(mesh.edges(), state):
        mesh.edge_attribute(ekey, 'guess', guess)
