/**
 * Pure solution-checking queries over a puzzle grid: do the user's edge
 * guesses violate the Slitherlink rules, and do they form a complete,
 * correct solution?
 *
 * These functions only inspect the grid and report findings (plus debug
 * diagnostics -- see debug.js for turning those on); acting on the findings -- highlighting errors, celebrating
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
import {debug} from "./debug.js";

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
 * Is a face's clue satisfied -- exactly as many of its edges filled in as the
 * clue asks for?
 *
 * "Satisfied" here means only that the count matches RIGHT NOW; it is not a
 * claim that the marks around the face are correct, since the loop may still
 * have to change. That is why this is separate from findClueViolations, which
 * asks whether a clue has become impossible. A face can be satisfied and later
 * stop being so, and that is normal play, not an error.
 *
 * A 0 clue therefore starts out satisfied, and stops being so the moment one of
 * its edges is filled in. A face with MORE filled edges than its clue is not
 * satisfied either -- it's over -- which findClueViolations reports as a
 * violation; this query just declines to call it done.
 *
 * Used to gray out satisfied clue digits, so the player can see at a glance
 * which faces still have something to work out.
 *
 * @param {Grid} grid - the grid the face belongs to
 * @param {Face} face - the face to test
 * @returns {boolean} false for a face with no clue, which is never "satisfied"
 */
export function isClueSatisfied(grid, face) {
    const clue = face.metadata.clue;
    if (clue < 0) return false;
    return countGuesses(grid, face.edgeIDs).numEdgesFilled === clue;
}

/**
 * Split the surface into the two regions the solution loop separates.
 *
 * This is what the loop MEANS: a closed curve on a closed surface cuts it in two,
 * and the two regions are exactly the faces you can walk between without crossing
 * the loop. The celebration colours them to show it (see js/celebration.js).
 *
 * A flood fill that refuses to cross a loop edge, and nothing more. Two richer
 * versions were built and removed, which is worth recording so they aren't
 * rebuilt: a distance-to-the-loop map, and a fill order seeded at each region's
 * middle. Both existed to animate the colouring as a spreading front, and both
 * failed as ideas rather than as code. Distance from the loop collapses, because
 * on these solids nearly every face TOUCHES the loop, so almost the whole surface
 * lands in one step. Distance from a seed spreads properly but implies the seed is
 * a meaningful place on the puzzle, and it is only wherever the fill began. The
 * colouring now happens all at once.
 *
 * Takes the loop as a VERTEX cycle, the form the puzzle stores it in.
 *
 * @param {Grid} grid
 * @param {number[]} loop - solution as a cycle of vertex IDs
 * @returns {{regions: number[][]}} one array of face IDs per region -- two for a
 *     valid loop, but however many the marks actually produce, so a caller is
 *     never surprised
 */
export function partitionFacesByLoop(grid, loop) {
    // The loop as edge IDs, which is what "don't cross" has to test.
    const loopEdges = new Set();
    for (let i = 0; i < loop.length; i++) {
        const edgeId = grid.findEdgeByVertices(loop[i], loop[(i + 1) % loop.length]);
        if (edgeId !== undefined && edgeId !== null) loopEdges.add(edgeId);
    }

    /** Faces reachable from `faceId` without crossing the loop. */
    const neighborsWithin = faceId => {
        const found = [];
        for (const edgeId of grid.faces.get(faceId).edgeIDs) {
            if (loopEdges.has(edgeId)) continue;
            for (const other of grid.edges.get(edgeId).faceIDs) {
                if (other !== faceId) found.push(other);
            }
        }
        return found;
    };

    const regionOf = new Map();
    const regions = [];
    for (const faceId of grid.faces.keys()) {
        if (regionOf.has(faceId)) continue;
        const index = regions.length;
        const members = [];
        const queue = [faceId];
        regionOf.set(faceId, index);
        while (queue.length > 0) {
            const current = queue.pop();
            members.push(current);
            for (const next of neighborsWithin(current)) {
                if (!regionOf.has(next)) {
                    regionOf.set(next, index);
                    queue.push(next);
                }
            }
        }
        regions.push(members);
    }

    return {regions};
}

/**
 * Find the user's marks that contradict the puzzle's known solution:
 * edges filled in that aren't part of the solution loop, or ruled out
 * although they are part of it. Unknown edges are never mismatches.
 *
 * NOTE: unlike the rule-violation queries above, this one peeks at the
 * stored solution, so its findings are SPOILERS. UI code should report
 * how many mismatches there are (and offer to clear them), but not
 * reveal their locations unless the player explicitly asks
 * (see the "show errors" idea in ideas/TODOs.md).
 *
 * @param {Grid} grid - the grid to check
 * @param {number[]} solutionVertexIds - the solution loop as a vertex ID list
 * @returns {number[]} IDs of edges whose guess contradicts the solution
 */
export function findSolutionMismatches(grid, solutionVertexIds) {
    // Collect the IDs of the edges on the solution loop.
    const solutionEdges = new Set();
    const n = solutionVertexIds.length;
    for (let i = 0; i < n; i++) {
        solutionEdges.add(grid.findEdgeByVertices(
            solutionVertexIds[i], solutionVertexIds[(i + 1) % n]));
    }

    const mismatches = [];
    for (const [edgeId, edge] of grid.edges) {
        const guess = edge.metadata.userGuess;
        const inSolution = solutionEdges.has(edgeId);
        if ((guess === 1 && !inSolution) || (guess === 2 && inSolution)) {
            mismatches.push(edgeId);
        }
    }
    return mismatches;
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
        debug(`checkSingleLoop: no edges are filled in`);
        return { ok: false, reason: 'noEdges' };
    }

    let startVertexId = startEdge.vertexIDs[0], currentVertexId = startEdge.vertexIDs[1];
    debug(`checkSingleLoop: tracing from v${startVertexId} along e${startEdgeId}`);
    let currentVertex = grid.vertices.get(currentVertexId);
    let currentEdge = startEdge, currentEdgeId = startEdgeId;
    let loopLength = 1;
    // Trace the route
    do {
        debug(`checkSingleLoop: tracing to v${currentVertexId} via e${currentEdgeId}`);
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
            debug(`checkSingleLoop: Incomplete loop.\n   No edge of v${currentVertexId} is filled in except e${currentEdgeId}.`);
            return { ok: false, reason: 'incomplete', vertexId: currentVertexId };
        }

        // Move to next vertex.
        currentVertexId = (nextEdge.vertexIDs[0] === currentVertexId ? nextEdge.vertexIDs[1] : nextEdge.vertexIDs[0]);
        currentVertex = grid.vertices.get(currentVertexId);
        currentEdgeId = nextEdgeId;
        debug(`checkSingleLoop: got to vertex ${currentVertexId} via edge ${currentEdgeId}`);
        currentEdge = nextEdge;
        loopLength++; // Will this give us an off-by-one error?
    } while (currentVertexId !== startVertexId);

    debug(`checkSingleLoop: loop length ${loopLength}`);

    /// Is there only one loop?
    const numEdgesFilledTotal = count(grid.edges,
        (([_edgeId, edge]) => edge.metadata.userGuess === 1));
    if (numEdgesFilledTotal > loopLength) {
        debug("checkSingleLoop: More than a single loop.");
        return { ok: false, reason: 'multipleLoops', loopLength };
    }

    return { ok: true, loopLength };
}
