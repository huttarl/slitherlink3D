/**
 * Pure solution-checking queries over a puzzle grid: do the user's edge
 * guesses violate the Slitherlink rules, and do they form a complete,
 * correct solution?
 *
 * These functions only inspect the grid and report findings (plus console
 * diagnostics); acting on the findings -- highlighting errors, celebrating
 * a win -- is up to the caller (PuzzleGrid.checkUserSolution). This keeps
 * the module free of DOM and THREE.js dependencies.
 *
 * The checks deliberately mirror the rule structure of the Python solver
 * (util/slisolver.py), which encodes the same puzzle rules:
 *     findVertexViolations ~ apply_vertex_rules' contradiction (f > 2)
 *     findClueViolations   ~ apply_clue_rules' contradictions
 *     checkSingleLoop      ~ is_valid_loop
 * Keeping the two implementations parallel makes them easier to compare.
 */

/** Count the number of elements in an iterable that satisfy a predicate. */
function count(iter, pred) {
    let n = 0;
    for (const e of iter) if (pred(e)) n++;
    return n;
}

/**
 * Count how many of the given edge IDs are filled in or ruled out.
 * @param {Grid} grid - the grid the edges belong to
 * @param {Set<number>} edgeIDs - Set of edge IDs to count
 * @returns {{numEdgesFilled: number, numEdgesRuledOut: number}}
 */
export function countGuesses(grid, edgeIDs) {
    // count(edgeIDs, (edgeId => grid.edges.get(edgeId)?.metadata.userGuess === 1));
    let numEdgesFilled = 0, numEdgesRuledOut = 0;
    for (const edgeId of edgeIDs) {
        const edge = grid.edges.get(edgeId);
        if (edge) {
            if (edge.metadata.userGuess === 1) numEdgesFilled++;
            if (edge.metadata.userGuess === 2) numEdgesRuledOut++;
        }
    }
    return { numEdgesFilled, numEdgesRuledOut };
}

/**
 * Find vertices where the loop would intersect itself: a valid loop visits
 * each vertex 0 or 2 times, so more than 2 filled edges is a violation.
 * @param {Grid} grid - the grid to check
 * @param {Iterable<number>} vertexIds - the vertex IDs to check
 * @returns {number[]} IDs of vertices with more than 2 filled edges
 */
export function findVertexViolations(grid, vertexIds) {
    const violations = [];
    for (const vId of vertexIds) {
        const vertex = grid.vertices.get(vId);
        const { numEdgesFilled } = countGuesses(grid, vertex.edgeIDs);
        // console.log(`findVertexViolations: v${vId} has ${numEdgesFilled} edges filled in`);
        if (numEdgesFilled > 2) {
            violations.push(vId);
        }
    }
    return violations;
}

/**
 * Find clued faces whose edge guesses are incompatible with their clue.
 * @param {Grid} grid - the grid to check
 * @param {Iterable<number>} faceIds - the face IDs to check
 * @param {boolean} requireExact - if true (active-mode check), each clue
 *     must be matched exactly; if false (passive), a face fails only when
 *     the clue has become impossible (too many filled, or too many ruled out)
 * @returns {{faceId: number, message: string}[]} the violations, with a
 *     human-readable description of each
 */
export function findClueViolations(grid, faceIds, requireExact) {
    const violations = [];
    for (const faceId of faceIds) {
        const face = grid.faces.get(faceId);

        // If the face doesn't have a clue, there's nothing to check.
        if (face.metadata.clue === -1) continue;

        const clue = face.metadata.clue;
        const numEdges = face.vertexIDs.length;
        const { numEdgesFilled, numEdgesRuledOut } = countGuesses(grid, face.edgeIDs);
        if (requireExact && numEdgesFilled !== clue) {
            // In active mode, clues must be exactly matched.
            violations.push({ faceId,
                message: `has ${numEdgesFilled} edges filled in but should have ${clue}` });
        } else if (numEdgesFilled > clue) {
            violations.push({ faceId,
                message: `has ${numEdgesFilled} edges filled in but should only have ${clue}` });
        } else if (numEdges - numEdgesRuledOut < clue) {
            violations.push({ faceId,
                message: `has ${numEdgesRuledOut} edges ruled out, but ${numEdges} - ${numEdgesRuledOut} < ${clue}` });
        }
    }
    return violations;
}

/**
 * Check whether the filled-in edges form a single complete loop.
 *
 * Assumes vertex violations have already been ruled out (every vertex has
 * at most 2 filled edges), so from any vertex there is at most one way
 * forward. Traces the loop from an arbitrary filled edge; if it closes,
 * compares its length against the total filled-edge count to detect
 * additional, disconnected loops.
 *
 * @param {Grid} grid - the grid to check
 * @returns {{ok: boolean, reason?: string, vertexId?: number, loopLength?: number}}
 *     ok: true (with loopLength) if the filled edges are one closed loop.
 *     Otherwise reason is one of:
 *     'noEdges' - nothing is filled in;
 *     'incomplete' - the path dead-ends at vertexId;
 *     'multipleLoops' - a closed loop exists but other filled edges remain.
 */
export function checkSingleLoop(grid) {
    // Find a place to start.
    let startEdgeId = null, startEdge = null;
    for (const [edgeId, edge] of grid.edges) {
        if (edge.metadata.userGuess === 1) {
            startEdgeId = edgeId;
            startEdge = edge;
            break;
        }
    }
    // If no edges are filled in, the puzzle is not solved.
    if (startEdgeId == null) {
        console.log(`checkSingleLoop: no edges are filled in`);
        return { ok: false, reason: 'noEdges' };
    }

    let startVertexId = startEdge.vertexIDs[0], currentVertexId = startEdge.vertexIDs[1];
    console.log(`checkSingleLoop: tracing from v${startVertexId} along e${startEdgeId}`);
    let currentVertex = grid.vertices.get(currentVertexId);
    let currentEdge = startEdge, currentEdgeId = startEdgeId;
    let loopLength = 1;
    // Trace the route
    do {
        console.log(`checkSingleLoop: tracing to v${currentVertexId} via e${currentEdgeId}`);
        // Find an edge of currentVertex besides currentEdge that is filled in.
        let nextEdge = null, nextEdgeId = null;
        for (const edgeId of currentVertex.edgeIDs) {
            if (edgeId !== currentEdgeId) {
                let edge = grid.edges.get(edgeId);
                if (edge.metadata.userGuess === 1) {
                    nextEdgeId = edgeId;
                    nextEdge = edge;
                    break;
                }
            }
        }
        // If no such edge exists, the puzzle is not solved.
        if (nextEdge == null) {
            console.log(`checkSingleLoop: Incomplete loop.\n   No edge of v${currentVertexId} is filled in except e${currentEdgeId}.`);
            return { ok: false, reason: 'incomplete', vertexId: currentVertexId };
        }

        // Move to next vertex.
        currentVertexId = (nextEdge.vertexIDs[0] === currentVertexId ? nextEdge.vertexIDs[1] : nextEdge.vertexIDs[0]);
        currentVertex = grid.vertices.get(currentVertexId);
        currentEdgeId = nextEdgeId;
        console.log(`checkSingleLoop: got to vertex ${currentVertexId} via edge ${currentEdgeId}`);
        currentEdge = nextEdge;
        loopLength++; // Will this give us an off-by-one error?
    } while (currentVertexId !== startVertexId);

    console.log(`checkSingleLoop: loop length ${loopLength}`);

    /// Is there only one loop?
    const numEdgesFilledTotal = count(grid.edges,
        (([_edgeId, edge]) => edge.metadata.userGuess === 1));
    if (numEdgesFilledTotal > loopLength) {
        console.log("checkSingleLoop: More than a single loop.");
        return { ok: false, reason: 'multipleLoops', loopLength };
    }

    return { ok: true, loopLength };
}
