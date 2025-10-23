"""Slitherlink puzzle solver."""

import networkx as nx
from compas.datastructures import Mesh

def solution_is_unique(clues, num_clues, solution, mesh, dualG):
    """Return True if given solution is the only possible one for given clues."""

    progress_deterministically()
    fork_on_guess()
    As soon as we find > 1 solution, abort.


    # Wipe out any old state for edge guesses.
    for ekey in mesh.edges():
        mesh.edge_attribute(ekey, 'guess', 'unknown')

    return True