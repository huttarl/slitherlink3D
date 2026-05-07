"""Slitherlink puzzle solver."""
import itertools
# import networkx as nx
# from compas.datastructures import Mesh

def solution_is_unique(clues, num_clues, solution, mesh, dualG):
    """Return True if given solution is the only possible one for given clues.

    Args:
        clues: List of (face, num_walls) tuples representing the clues
        num_clues: How many clues from the list to use
        solution: The known solution (list of vertex indices forming a loop)
        mesh: COMPAS Mesh representing the grid
        dualG: NetworkX dual graph with nodes for faces (may not be needed)

    Returns:
        True if there is exactly one solution, False if multiple solutions exist
    """
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
        (because we've found multiple solutions).
        """
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

    # Return True if exactly one solution was found
    return solutions_found[0] == 1


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

    Alternates apply_vertex_rules and apply_clue_rules in a fixed-point
    loop. Bails on the first contradiction from either family.

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
        (ok, changed_v) = apply_vertex_rules(mesh)
        if not ok:
            return False
        (ok, changed_c) = apply_clue_rules(mesh)
        if not ok:
            return False
        if not (changed_v or changed_c):
            return True


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
    """Select the most constrained unknown edge for branching.

    Good heuristics:
    - Choose edges adjacent to faces with clues
    - Choose edges where one choice would immediately cause propagation
    - Choose edges in high-degree vertices
    - Choose edges that continue the existing loop

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
