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

    Alternates apply_vertex_rules, apply_clue_rules, apply_pattern_rules,
    apply_color_rules and apply_pair_rules in a fixed-point loop, cheapest
    first: each family runs only once every cheaper one has stalled, and any
    deduction sends us back to the cheap rules. Bails on the first contradiction
    from any family.

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
        if changed_col:
            continue  # Back to the cheap rules with the new facts.

        # Coloring has stalled too. Edge-pair reasoning is the most expensive
        # family (it builds two stores and then tests each constrained edge both
        # ways), so it goes last, for the same reason coloring goes after the
        # local rules.
        (ok, changed_pair) = apply_pair_rules(mesh)
        if not ok:
            return False
        if not changed_pair:
            return True  # No family can deduce anything further.


# The two determined edge states, each other's negation. Used by the edge-pair
# machinery, which reasons about "the other state" constantly.
OPPOSITE_GUESS = {'filledIn': 'ruledOut', 'ruledOut': 'filledIn'}


def edge_id(ekey):
    """A canonical key for an edge, independent of which end is named first.

    COMPAS treats (u,v) and (v,u) as the same edge for attribute lookups, but a
    plain dict does not, so anything of ours that keys structures by edge has to
    canonicalize first or it will silently hold one edge twice.
    """
    return tuple(sorted(ekey))


class ParityRelation:
    """Tracks which items must be in the same state as each other, and which
    must be in opposite states, without ever deciding which state is which.

    Union-find over items, but each item also carries one parity bit saying
    whether it is the same as, or opposite to, its parent. So the structure
    answers "are these two items the same?" -- never "which one is this?".

    Two subclasses use it, over different variables:

        FaceColoring -- items are faces, "opposite" means opposite colors
        EdgePairing  -- items are edges, "opposite" means exactly one is filled

    Both are the same question asked about different things, and both are
    relative-only, which is what makes one implementation serve them. Any
    hashable item works; subclasses that need a canonical key (as EdgePairing
    does, since (u,v) and (v,u) are one edge) override _key.
    """

    def __init__(self):
        # item -> parent item in the union-find forest.
        self.parent = {}
        # item -> True if this item is the OPPOSITE of its parent.
        self.flipped = {}
        # root item -> list of every item in its group. Doubles as the group
        # size for union by size, and lets group() enumerate without a scan.
        self.members = {}

    def _key(self, item):
        """The canonical form of an item, for use as a dict key. Identity
        here; overridden where two spellings mean the same item."""
        return item

    def _find(self, item):
        """Return (root, opposite): the group's representative, and whether
        `item` is the opposite of it. Compresses the path walked."""
        if item not in self.parent:
            self.parent[item] = item
            self.flipped[item] = False
            self.members[item] = [item]
            return (item, False)

        # Walk up to the root, accumulating parity as we go.
        root = item
        opposite = False
        while self.parent[root] != root:
            opposite ^= self.flipped[root]
            root = self.parent[root]

        # Path compression: re-point everything we walked past straight at the
        # root, each with its own parity relative to the root. Note we must
        # read flipped[current] before overwriting it.
        current = item
        current_opposite = opposite
        while self.parent[current] != current:
            next_item = self.parent[current]
            next_opposite = current_opposite ^ self.flipped[current]
            self.parent[current] = root
            self.flipped[current] = current_opposite
            current = next_item
            current_opposite = next_opposite

        return (root, opposite)

    def relate(self, item1, item2, opposite):
        """Record that the two items are opposites (opposite=True) or the same
        (opposite=False).

        Returns False if that contradicts what we already know about them,
        in which case no solution is possible from here.
        """
        (root1, opposite1) = self._find(self._key(item1))
        (root2, opposite2) = self._find(self._key(item2))

        if root1 == root2:
            # Already in one group, so their relation is already fixed: this
            # new claim either agrees with it or the puzzle is contradictory.
            return (opposite1 ^ opposite2) == opposite

        # Attach the smaller group to the larger, choosing the parity bit that
        # makes the requested relation hold. Note the parity formula is
        # symmetric in the two operands, so the swap doesn't disturb it.
        if len(self.members[root1]) < len(self.members[root2]):
            (root1, root2) = (root2, root1)
            (opposite1, opposite2) = (opposite2, opposite1)
        self.parent[root2] = root1
        self.flipped[root2] = opposite1 ^ opposite ^ opposite2
        self.members[root1].extend(self.members[root2])
        del self.members[root2]  # root2 is no longer a root.
        return True

    def relation(self, item1, item2):
        """True if the items must be opposites, False if they must be the
        same, or None if nothing relates them yet."""
        (root1, opposite1) = self._find(self._key(item1))
        (root2, opposite2) = self._find(self._key(item2))
        if root1 != root2:
            return None
        return opposite1 ^ opposite2

    def group(self, item):
        """Every item whose state is tied to this one, as a list of
        (item, opposite) pairs, where `opposite` is relative to the item asked
        about. So once `item` is known, so is everything in the list.

        The item itself is included, with opposite=False, so that a caller can
        apply one uniform rule to the whole list. Querying an item nothing is
        known about returns just itself.
        """
        (root, opposite) = self._find(self._key(item))
        return [(member, opposite ^ self._find(member)[1])
                for member in self.members[root]]


class FaceColoring(ParityRelation):
    """Tracks which faces must be the same 'color' as each other, and which
    must be opposite, without ever deciding which color is which.

    A ParityRelation over faces: it answers "are these two faces the same
    color?" -- never "is this face inside?".

    That RELATIVE-only design is not a convenience, it's forced by our
    topology. On a flat Slitherlink grid the region outside the border is
    known to be outside, which anchors every color absolutely. A polyhedron
    has no outer face: a loop cuts the surface into two patches and neither is
    canonically "inside", exactly as genSliPuzzles' Phase A picks its red and
    blue seed faces arbitrarily. Relative relationships are all there is, and
    they're enough -- colorings that never connect to each other still yield
    deductions in their own neighbourhoods.

    To be precise about what "relative" rules out, since it isn't the labels:
    naming the two patches red and blue is perfectly fine, and each group's
    parity bits amount to exactly that, read as "same as my root face" or "not".
    What's missing is an ANCHOR. No face is known red the way a flat grid's
    border region is known outside, so a group's labeling is fixed only up to
    swapping the two colors, and two groups that have never been connected
    can't be compared at all. Hence the interface offers relation() and not
    color_of(): the pairwise answer is invariant under that swap, and an
    absolute one wouldn't be.
    """


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


class EdgePairing(ParityRelation):
    """Which pairs of edges must agree, and which must disagree.

        both or neither    the two edges are in the same state
        exactly one        the two edges are in opposite states

    A ParityRelation over edges, so transitive closure is free: relate e to f
    and f to g, and the relation between e and g is already known, however far
    apart they are on the solid. Contradictions are caught on insertion.

    Why edges need their own structure, when FaceColoring exists: an edge is
    filled exactly when its two faces differ in color, so an edge between
    faces A and B *is* the parity A^B. For two edges sharing a face -- e
    between A and B, f between B and C -- "e agrees with f" reduces to
    "A and C are the same color", which the face coloring can already answer.
    But two edges sharing only a VERTEX give A^B = C^D, a four-face parity that
    no pairwise relation over faces can hold. That case is what this is for.

    Edge keys are canonicalized, since COMPAS spells an edge (u,v) or (v,u)
    interchangeably while a dict would treat those as two items.
    """

    def _key(self, item):
        return edge_id(item)

    def both_or_neither(self, edge1, edge2):
        """Record that the two edges are in the same state. Returns False if
        that contradicts what is already known."""
        return self.relate(edge1, edge2, opposite=False)

    def exactly_one(self, edge1, edge2):
        """Record that exactly one of the two edges is filled. Returns False if
        that contradicts what is already known."""
        return self.relate(edge1, edge2, opposite=True)

    def forced_by(self, edge, guess):
        """The state every tied edge must take, given this edge's state.
        Returns a dict of edge -> guess, including the edge asked about."""
        return {other: (OPPOSITE_GUESS[guess] if opposite else guess)
                for (other, opposite) in self.group(edge)}


class EdgeClauses:
    """The two edge-pair relations that are NOT equivalences:

        at least one    the two edges are not both ruled out
        at most one     the two edges are not both filled

    These cannot live in a ParityRelation, because they don't relate the two
    edges' states at all -- they forbid one combination and permit the other
    three. So they go in an implication store over literals, a literal being an
    edge together with a state:

        at least one:  e ruled out -> f filled,   f ruled out -> e filled
        at most one:   e filled    -> f ruled out, f filled   -> e ruled out

    Propagation is then a walk from each newly decided edge, and deriving both
    states for one edge is the contradiction.

    The two families compose: "exactly one" is at-least-one AND at-most-one, so
    a pair that collects both clauses -- typically from two different rules --
    can be promoted into EdgePairing as an opposite-parity relation. See
    exactly_one_pairs(), which is where separate rule families start feeding
    each other.

    Both methods expect two distinct edges. A degenerate pair (an edge with
    itself) is still recorded soundly -- at_most_one(e, e) says e is not filled
    -- and forced_by will report the contradiction if both are claimed; only
    exactly_one_pairs ignores such a pair, having nothing to promote.
    """

    def __init__(self):
        # literal -> set of literals it forces, a literal being (edge, guess).
        self.implies = {}
        # frozenset of the two edges -> which clauses we hold for them. Kept
        # only so exactly_one_pairs can spot a pair that has collected both.
        self.kinds = {}

    def _add(self, literal, consequence):
        self.implies.setdefault(literal, set()).add(consequence)

    def _record(self, edge1, edge2, kind, premise, conclusion):
        """Add one clause: from either edge in state `premise`, the other is
        forced to `conclusion`."""
        (a, b) = (edge_id(edge1), edge_id(edge2))
        self._add((a, premise), (b, conclusion))
        self._add((b, premise), (a, conclusion))
        self.kinds.setdefault(frozenset((a, b)), set()).add(kind)

    def at_least_one(self, edge1, edge2):
        """Record that the two edges are not both ruled out."""
        self._record(edge1, edge2, 'at least one', 'ruledOut', 'filledIn')

    def at_most_one(self, edge1, edge2):
        """Record that the two edges are not both filled."""
        self._record(edge1, edge2, 'at most one', 'filledIn', 'ruledOut')

    def implications(self, edge, guess):
        """The literals this one state forces directly, without following the
        chain any further. Sorted, so callers are reproducible."""
        return sorted(self.implies.get((edge_id(edge), guess), ()))

    def forced_by(self, edge, guess):
        """Every edge state that follows from this one, transitively.

        Returns a dict of edge -> guess, including the edge asked about, or
        None if the assumption is contradictory -- which is itself a useful
        answer, since it means the edge must take the other state.
        """
        start = edge_id(edge)
        known = {start: guess}
        queue = [(start, guess)]
        while queue:
            literal = queue.pop()
            for (other, other_guess) in sorted(self.implies.get(literal, ())):
                if other in known:
                    if known[other] != other_guess:
                        return None  # Both states forced for one edge.
                    continue
                known[other] = other_guess
                queue.append((other, other_guess))
        return known

    def exactly_one_pairs(self):
        """The pairs holding BOTH clauses, which therefore mean "exactly one"
        and are ready to be promoted into an EdgePairing. Sorted pairs, in
        sorted order, so promotion is reproducible."""
        return sorted(tuple(sorted(pair))
                      for (pair, kinds) in self.kinds.items()
                      if len(pair) == 2 and len(kinds) == 2)


def emit_vertex_pairs(mesh, pairing, clauses):
    """Read pair constraints off the vertex rule, one vertex at a time.

    A vertex uses 0 or 2 of its edges. With f of them already filled and u
    still unknown, that alone relates the unknowns:

        f == 1, u == 2   exactly one of the two (the vertex needs one more)
        f == 0, u == 2   both or neither (it needs none or both)
        f == 1, u > 2    at most one, for each of the C(u,2) pairs
        f == 2           every unknown is ruled out -- apply_vertex_rules
                         already does that, so nothing pairwise is needed

    Note f == 0, u >= 3 yields NOTHING pairwise: for any two of those edges,
    both-filled is legal (the vertex's two) and both-empty is legal (two others
    are, or none are). The information there is "0 or 2 of these u", which is
    not a statement about any pair.

    The pairs this produces all share a vertex, which is half of the locality
    argument in docs/edge-pair-constraints.md -- we never enumerate a pair no
    rule can speak about.

    Returns False if a relation contradicts one already recorded.
    """
    for vkey in mesh.vertices():
        filled = []
        unknown = []
        for nbr in mesh.vertex_neighbors(vkey):
            ekey = (vkey, nbr)
            guess = mesh.edge_attribute(ekey, 'guess')
            if guess == 'filledIn':
                filled.append(ekey)
            elif guess == 'unknown':
                unknown.append(ekey)
        f = len(filled)
        u = len(unknown)

        if (f, u) == (1, 2):
            if not pairing.exactly_one(unknown[0], unknown[1]):
                return False
        elif (f, u) == (0, 2):
            if not pairing.both_or_neither(unknown[0], unknown[1]):
                return False
        elif f == 1 and u > 2:
            for (edge1, edge2) in itertools.combinations(unknown, 2):
                clauses.at_most_one(edge1, edge2)

    return True


def emit_face_pairs(mesh, pairing, clauses):
    """Read pair constraints off the clue arithmetic, one clued face at a time.

    For a face with clue k, f edges filled and u unknown, the deficit k - f is
    how many of the unknowns must still be filled. Two cases speak about pairs:

        deficit == 1       exactly one more edge is filled, so AT MOST ONE of
                           any pair of unknowns
        deficit == u - 1   exactly one unknown stays empty, so AT LEAST ONE of
                           any pair of unknowns is filled

    When u == 2 and deficit == 1 both conditions hold, so the pair collects both
    clauses and becomes "exactly one" -- which is why the caller promotes rather
    than special-casing it here.

    The extreme deficits (0 and u) determine every unknown outright and belong to
    apply_clue_rules; this only speaks where that rule is silent. `pairing` is
    unused, and is taken so both emitters have one signature.

    Returns True always -- a clause can't contradict on insertion the way a
    parity relation can, since it rules out one combination rather than tying
    two edges together.
    """
    for fkey in mesh.faces():
        clue = mesh.face_attribute(fkey, 'clue')
        if clue is None:
            continue

        filled = []
        unknown = []
        for ekey in mesh.face_halfedges(fkey):
            guess = mesh.edge_attribute(ekey, 'guess')
            if guess == 'filledIn':
                filled.append(ekey)
            elif guess == 'unknown':
                unknown.append(ekey)
        u = len(unknown)
        deficit = clue - len(filled)

        if u < 2:
            continue  # No pair to speak about.

        # Not elif: at u == 2, deficit == 1 satisfies both, which is the point.
        if deficit == 1:
            for (edge1, edge2) in itertools.combinations(unknown, 2):
                clauses.at_most_one(edge1, edge2)
        if deficit == u - 1:
            for (edge1, edge2) in itertools.combinations(unknown, 2):
                clauses.at_least_one(edge1, edge2)

    return True


def pair_forced_by(pairing, clauses, edge, guess):
    """Everything the two stores TOGETHER force, given one edge's state.

    Walks parity groups and clause implications in one search, because the
    payoff is in their interaction: a parity step can land on an edge whose
    clause then forces a third, and so on.

    Returns a dict of edge -> guess including the edge asked about, or None if
    the supposition is impossible. None is the useful answer: it means the edge
    must take the other state.
    """
    known = {}
    queue = [(edge_id(edge), guess)]
    while queue:
        (current, current_guess) = queue.pop()
        if current in known:
            if known[current] != current_guess:
                return None  # Both states forced for one edge.
            continue
        known[current] = current_guess
        # Everything tied to it by parity, then everything its state implies.
        queue.extend(pairing.forced_by(current, current_guess).items())
        queue.extend(clauses.implications(current, current_guess))
    return known


def apply_pair_rules(mesh):
    """Apply edge-pair reasoning: build the pair constraints, then use them.

    Three steps. First the emitters read pairs off the vertex and clue
    arithmetic. Then any pair that collected both an at-least-one and an
    at-most-one is promoted to "exactly one" -- the seam where two rule families
    feed each other, since the two clauses often come from different faces, or
    from a face and a vertex. Finally each constrained edge is tested both ways:
    if supposing it filled forces some edge into both states at once, the edge
    must be ruled out, and vice versa.

    That last step is a restricted lookahead, and worth comparing to
    propagate_with_lookahead, which is strictly stronger: it supposes an edge
    and runs the FULL rule set, so it sees everything this does and more. The
    difference is cost. This walks a few small local structures and touches no
    mesh attributes, cheap enough to sit inside the fixed-point loop, where
    lookahead is an outer layer used only after everything else has stalled.

    Known overlap: this subsumes pattern Rules A and B. Rule A is a -1 face
    (deficit u-1, giving at-least-one) at a vertex whose other edges are ruled
    out (giving both-or-neither), and at-least-one plus both-or-neither forces
    both edges filled. Rule B is the same with clue 1, deficit 1 and
    at-most-one, forcing both ruled out. The patterns are kept because they are
    much cheaper and because they model what a player recognises at a glance --
    the same reason apply_pattern_rules coexists with lookahead.

    The stores are built from scratch on every call and thrown away, exactly as
    apply_color_rules does with its FaceColoring, so save_state stays a plain
    list of edge guesses and backtracking has no constraint database to unwind.

    Returns (ok, changed) -- same convention as the other rule families.
    """
    pairing = EdgePairing()
    clauses = EdgeClauses()

    if not emit_vertex_pairs(mesh, pairing, clauses):
        return (False, False)
    if not emit_face_pairs(mesh, pairing, clauses):
        return (False, False)

    for (edge1, edge2) in clauses.exactly_one_pairs():
        if not pairing.exactly_one(edge1, edge2):
            return (False, False)

    # Every edge any constraint mentions, in a stable order for reproducibility.
    candidates = set(pairing.parent) | {edge for (edge, _guess) in clauses.implies}

    changed = False
    for ekey in sorted(candidates):
        # Earlier deductions in this same scan may have settled it already.
        if mesh.edge_attribute(ekey, 'guess') != 'unknown':
            continue
        impossible = [guess for guess in ('filledIn', 'ruledOut')
                      if pair_forced_by(pairing, clauses, ekey, guess) is None]
        if len(impossible) == 2:
            return (False, changed)  # Neither state works: the position is dead.
        if impossible:
            (ok, did) = _set_edges(mesh, [ekey], OPPOSITE_GUESS[impossible[0]])
            if not ok:
                return (False, changed)
            changed = changed or did

    return (True, changed)


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

    The rules themselves are the functions listed in PATTERN_RULES, one per
    rule; this runs each in turn and stops at the first contradiction. See each
    of them for what it deduces and why.

    The (clue 0, clue 1) and (clue 0, -1) vertex patterns need no code of
    their own: a clue-0 face has all its edges ruled out by the ordinary clue
    rule, which then supplies exactly the "every other edge here is ruled out"
    context that Rules A and B look for.

    Returns (ok, changed) -- same convention as the other rule families.
    """
    changed = False
    for rule in PATTERN_RULES:
        (ok, did) = rule(mesh)
        if not ok:
            return (False, changed)
        changed = changed or did
    return (True, changed)


def apply_rules_a_and_b(mesh):
    """Rules A and B: one face, at a vertex whose other edges are all settled.

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

    The two share a single scan because they are the same deduction in opposite
    directions: the clue decides only whether the face's pair of edges at a
    settled vertex must both be filled or both be ruled out.

    Returns (ok, changed) -- same convention as the other rule families.
    """
    changed = False

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

    return (True, changed)


def apply_rule_d(mesh):
    """Rule D: two -1 faces that DO share an edge.

    Take the shared edge e, with endpoints P and Q. Each face's edges away from
    both P and Q are filled.

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

    Returns (ok, changed) -- same convention as the other rule families.
    """
    changed = False

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

    return (True, changed)


def apply_rule_c(mesh):
    """Rule C: two -1 faces meeting at a vertex but NOT sharing an edge.

    Each contributes at least one filled edge at that vertex (Rule A's
    reasoning), and a vertex holds at most two, so each contributes exactly one
    and every other edge there is ruled out. Since each face's single ruled-out
    edge is therefore at this vertex, all of its other edges are filled.

    Note Rule C needs no condition on the vertex's degree: "at most two
    filled" does the work.

    Returns (ok, changed) -- same convention as the other rule families.
    """
    changed = False

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


# The tier-1 rules, in the order apply_pattern_rules runs them. Each is sound on
# its own, so the order can't change what the set of them concludes at a fixed
# point -- but it does decide which rule gets to a given edge first, so keep it
# stable, since the tests name the rule they expect to fire. Add new tier-1
# rules here.
PATTERN_RULES = (apply_rules_a_and_b, apply_rule_d, apply_rule_c)


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
