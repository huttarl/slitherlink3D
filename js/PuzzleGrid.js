import { Grid } from './Grid.js';
import {EDGE_COLORS, EDGE_STATES} from './constants.js';
import {checkSingleLoop, findClueViolations, findSolutionMismatches, findVertexViolations} from './solutionChecker.js';
// NOTE: deliberately no imports of ui.js or GameState.js here. This class is
// the puzzle model; reaching up into the UI/coordinator layer above it created
// import cycles (PuzzleGrid -> GameState -> PuzzleGrid, and
// PuzzleGrid -> ui -> GameState -> PuzzleGrid). Instead, the UI layer
// registers the observer callbacks declared in the constructor below.

/**
 * Extended Grid class that includes puzzle data and cross-references to THREE.js objects.
 * Manages the relationship between puzzle logic and 3D visualization.
 * 
 * @class PuzzleGrid
 * @extends Grid
 */
export class PuzzleGrid extends Grid {
    constructor() {
        super();
        
        // Puzzle-specific data
        this.puzzleData = null;
        this.currentPuzzleIndex = 0;
        this.gridId = null;

        // Undo/redo history of the user's edge-guess changes.
        // Each move is an ARRAY of deltas {edgeId, prevState, newState}:
        // a normal click produces a one-delta move; a puzzle reset produces
        // one compound move covering every edge it cleared, so the whole
        // reset undoes in a single step.
        this.undoStack = [];
        this.redoStack = [];

        // Observer callbacks, registered by the UI layer (see setupUI in
        // ui.js). They stay null-safe so this class works headless, e.g. in
        // tests, and so events that fire during scene setup -- before the UI
        // is wired up -- are simply ignored.
        //   onHistoryChanged() - the undo/redo history changed
        //   onSolved()         - the user's guesses form a correct solution
        this.onHistoryChanged = null;
        this.onSolved = null;

        // Player setting (a checkbox in the panel, wired up by ui.js):
        // whether passive checks highlight rule violations in red as the
        // player clicks. Explicit "Check solution" requests always highlight.
        this.highlightRuleViolations = true;
    }

    /** Notify the UI layer (if any) that the undo/redo history changed. */
    historyChanged() {
        if (this.onHistoryChanged) this.onHistoryChanged();
    }

    /**
     * Sets the puzzle data and validates it matches the grid
     * @param {Object} puzzleData - Puzzle data with gridId and puzzles array
     * @param {string} expectedGridId - Expected grid ID to validate against
     */
    setPuzzleData(puzzleData, expectedGridId = null) {
        this.puzzleData = puzzleData;
        
        // Validate gridId matches
        if (expectedGridId && puzzleData.gridId !== expectedGridId) {
            throw new Error(`Grid ID mismatch: expected "${expectedGridId}", got "${puzzleData.gridId}"`);
        }
        
        this.gridId = puzzleData.gridId;
    }

    /**
     * Sets the current puzzle index and validates it
     * @param {number} puzzleIndex - Index of puzzle to use
     */
    setCurrentPuzzle(puzzleIndex) {
        if (!this.puzzleData) {
            throw new Error('Puzzle data must be set before selecting a puzzle');
        }
        
        if (puzzleIndex < 0 || puzzleIndex >= this.puzzleData.puzzles.length) {
            throw new Error(`Invalid puzzle index: ${puzzleIndex} (available: 0-${this.puzzleData.puzzles.length - 1})`);
        }
        
        this.currentPuzzleIndex = puzzleIndex;

        // A different puzzle means a fresh undo history.
        this.undoStack.length = 0;
        this.redoStack.length = 0;
        this.historyChanged();
    }

    /**
     * Gets the current puzzle object
     * @returns {Object} Current puzzle data
     */
    getCurrentPuzzle() {
        if (!this.puzzleData) {
            throw new Error('No puzzle data available');
        }
        return this.puzzleData.puzzles[this.currentPuzzleIndex];
    }

    /**
     * Applies clues from the current puzzle to faces in the grid
     */
    applyCurrentPuzzleClues() {
        if (!this.puzzleData) {
            throw new Error('No puzzle data available');
        }
        
        const puzzle = this.getCurrentPuzzle();
        
        // Validate clues array exists
        if (!puzzle.clues || !Array.isArray(puzzle.clues)) {
            throw new Error('Invalid or missing clues array in puzzle');
        }
        
        // Validate clues array length
        if (puzzle.clues.length > this.faces.size) {
            throw new Error(`Clues array length (${puzzle.clues.length}) exceeds number of faces (${this.faces.size})`);
        }
        
        // Apply clues to faces based on their index
        for (const [_faceId, face] of this.faces) {
            const faceIndex = face.metadata.index;
            
            // Get clue for this face (-1 if beyond clues array)
            const clue = faceIndex < puzzle.clues.length ? puzzle.clues[faceIndex] : -1;
            
            // Validate clue value
            if (clue !== -1) {
                const numEdges = face.edgeIDs.length;
                if (!Number.isInteger(clue) || clue < 0 || clue > numEdges) {
                    throw new Error(`Invalid clue ${clue} for face ${faceIndex}: must be -1 or 0-${numEdges}`);
                }
            }
            
            // Apply clue to face metadata
            face.metadata.clue = clue;
        }
    }

    /**
     * Validates the puzzle's solution, which was loaded from a data source
     * (not the user's guesses).
     */
    validatePuzzleSolution() {
        if (!this.puzzleData) {
            throw new Error('No puzzle data available');
        }
        
        const puzzle = this.getCurrentPuzzle();
        const solution = puzzle.solution;
        
        // Validate solution exists
        if (!solution || !Array.isArray(solution)) {
            throw new Error('Invalid or missing solution in puzzle');
        }
        
        // Validate solution length
        if (solution.length < 3 || solution.length > this.vertices.size) {
            throw new Error(`Solution length (${solution.length}) too small or exceeds number of vertices (${this.vertices.size})`);
        }
        
        // Validate no duplicates in solution
        const uniqueVertices = new Set(solution);
        if (uniqueVertices.size !== solution.length) {
            throw new Error('Solution contains duplicate vertices');
        }
        
        // Validate vertex indices exist in grid
        for (const idx of solution) {
            if (!Number.isInteger(idx) || !this.vertices.has(idx)) {
                throw new Error(`Invalid vertex index ${idx} in solution (not found in grid)`);
            }
        }
        
        // Check that each edge in the solution exists
        for (let i = 0; i < solution.length; i++) {
            const v1Id = solution[i];
            const v2Id = solution[(i + 1) % solution.length];
            
            // Find the edge between v1Id and v2Id
            const edgeId = this.findEdgeByVertices(v1Id, v2Id);
            if (edgeId == null) {
                throw new Error(`No edge found between vertices ${v1Id} and ${v2Id} in solution`);
            }
        }
    }

    /**
     * Highlights the current puzzle's solution by coloring solution edges.
     */
    highlightPuzzleSolution() {
        if (!this.puzzleData) {
            throw new Error('No puzzle data available');
        }
        
        const puzzle = this.getCurrentPuzzle();
        const solutionVIds = puzzle.solution;
        
        // For each consecutive pair of vertices in the solution
        for (let i = 0; i < solutionVIds.length; i++) {
            const v1Id = solutionVIds[i];
            const v2Id = solutionVIds[(i + 1) % solutionVIds.length];
            
            // Find the edge between v1 and v2.
            const edgeId = this.findEdgeByVertices(v1Id, v2Id);
            const edgeMesh = this.getEdgeMesh(edgeId);
            if (edgeMesh) {
                // console.log(`Highlighting solution edge ${edgeId} between ${v1Id} and ${v2Id}`);
                edgeMesh.material.color = EDGE_COLORS.solution;
            }
        }
    }

    /** Resets all edge states to unknown, as one undoable compound move.
     * This is the user-initiated puzzle reset (the Reset button). Because
     * the reset is recorded in the undo history as a single move, an
     * accidental reset can be recovered with one Undo.
     */
    resetPuzzle() {
        // Collect a delta for every edge that isn't already unknown.
        const deltas = [];
        for (const [edgeId, edge] of this.edges) {
            if (edge.metadata.userGuess !== 0) {  // 0 = unknown
                deltas.push({ edgeId, prevState: edge.metadata.userGuess, newState: 0 });
            }
        }
        if (deltas.length === 0) {
            return; // Board already pristine; don't record an empty move.
        }
        this.undoStack.push(deltas);
        this.redoStack.length = 0;
        for (const delta of deltas) {
            this.applyEdgeState(delta.edgeId, 0);
        }
        // Remove any error highlighting left over from before the reset.
        this.clearEdgeHighlights();
        this.historyChanged();
    }

    /**
     * Applies an edge's guess state to the model and its mesh color,
     * WITHOUT touching the undo history. Callers that make a new user move
     * should use setEdgeState instead; this is the shared low-level step.
     * @param {number} edgeId - ID of the edge to change
     * @param {number} newState - New state, an index into EDGE_STATES
     *     (0 = unknown, 1 = filled in, 2 = ruled out)
     */
    applyEdgeState(edgeId, newState) {
        const edge = this.edges.get(edgeId);
        edge.metadata.userGuess = newState;
        const edgeMesh = this.getEdgeMesh(edgeId);
        if (edgeMesh) {
            edgeMesh.material.color = EDGE_COLORS[EDGE_STATES[newState]];
        }
    }

    /**
     * Sets an edge's guess state and updates its mesh color, recording the
     * change in the undo history as a one-delta move.
     *
     * This is the choke point for new user guesses: route guess mutations
     * through here (or record them yourself, like resetPuzzle) so the undo
     * history stays complete.
     *
     * @param {number} edgeId - ID of the edge to change
     * @param {number} newState - New state, an index into EDGE_STATES
     *     (0 = unknown, 1 = filled in, 2 = ruled out)
     */
    setEdgeState(edgeId, newState) {
        const edge = this.edges.get(edgeId);
        this.undoStack.push([{ edgeId, prevState: edge.metadata.userGuess, newState }]);
        // A new move invalidates any previously-undone moves.
        this.redoStack.length = 0;
        this.applyEdgeState(edgeId, newState);
        this.historyChanged();
    }

    /**
     * Undoes the user's most recent move (edge-guess change or reset), if any.
     * @returns {boolean} true if a move was undone, false if history was empty
     */
    undo() {
        const move = this.undoStack.pop();
        if (!move) {
            console.log('undo: nothing to undo');
            return false;
        }
        this.redoStack.push(move);
        // Restore in reverse order, in case a compound move ever contains
        // two deltas for the same edge.
        for (let i = move.length - 1; i >= 0; i--) {
            this.applyEdgeState(move[i].edgeId, move[i].prevState);
        }
        this.refreshFeedback(move);
        this.historyChanged();
        return true;
    }

    /**
     * Redoes the most recently undone move, if any.
     * @returns {boolean} true if a move was redone, false if none was available
     */
    redo() {
        const move = this.redoStack.pop();
        if (!move) {
            console.log('redo: nothing to redo');
            return false;
        }
        this.undoStack.push(move);
        for (const delta of move) {
            this.applyEdgeState(delta.edgeId, delta.newState);
        }
        this.refreshFeedback(move);
        this.historyChanged();
        return true;
    }

    /**
     * Recomputes error feedback after an undo/redo: clears any stale error
     * highlights, then reruns the passive check on each changed edge --
     * mirroring what direct clicks on those edges would do.
     * @param {Array} move - the move (array of deltas) that was just applied
     */
    refreshFeedback(move) {
        this.clearEdgeHighlights();
        for (const delta of move) {
            const edge = this.edges.get(delta.edgeId);
            this.checkUserSolution(false, this.getEdgeMesh(delta.edgeId), edge);
        }
    }

    /**
     * Check whether the user's current guesses are a correct solution.
     * @param {boolean} isActiveMode - whether checking in active mode or not.
     * @param {THREE.Mesh|null} edgeMesh - mesh of edge whose state has been changed
     * @param {Edge|null} edge - edge whose state has been changed
     * @returns {{status: number, vertexViolations: number[],
     *     clueViolations: {faceId: number, message: string}[],
     *     loopCheck: object|null, mismatchedEdgeIds: number[]|null}}
     *     status: 0 = no problem found (but not solved), 1 = failed, 2 = solved.
     *     loopCheck (active mode only) is checkSingleLoop's result.
     *     mismatchedEdgeIds (active mode only) lists guesses contradicting
     *     the stored solution -- SPOILER data: the UI should present only
     *     its count, not the locations.
     *
     * Passive mode is less thorough, called in response to each new change of user's guesses,
     * and local to the latest change (edgeMesh).
     * Active mode is called when user has explicitly asked for a solution check, and is global.
     *
     * Rule violations are highlighted in red: always in active mode, but
     * passively only if the highlightRuleViolations setting is on.
     *
     * The rule checks themselves are pure queries in solutionChecker.js;
     * this method chooses their scope (local vs. global) and acts on their
     * findings (highlighting, celebration). Reporting to the player is up
     * to the caller (see showCheckResults in ui.js).
     */
    checkUserSolution(isActiveMode, edgeMesh = null, edge = null) {
        if (!this.puzzleData) {
            throw new Error('No puzzle data available');
        }

        const edgeId = edgeMesh?.userData.edgeId;
        console.log(`checkUserSolution, activeMode ${isActiveMode} edgeId ${edgeId}`);

        const result = {
            status: 0, // 0 = unknown, 1 = failed, 2 = solved
            vertexViolations: [],
            clueViolations: [],
            loopCheck: null,
            mismatchedEdgeIds: null,
            // Has the player filled in anything at all? Recorded here rather
            // than left to the loop check (whose 'noEdges' reason says the same
            // thing) because an early return on a rule violation skips that
            // check -- and an untouched board violates every unsatisfied clue,
            // so that early return is exactly the case that needs it.
            hasFilledEdges: false,
        };
        for (const edge of this.edges.values()) {
            if (edge.metadata.userGuess === 1) {   // 1 = filledIn
                result.hasFilledEdges = true;
                break;
            }
        }

        // Keep track of whether we've already reset highlighting on edges and faces.
        let clearedEdgeHighlights = false, clearedFaceHighlights = false;

        // Things to check:
        // - loop doesn't intersect self (no vertex has > 2 edges filled in)
        // - number of edges per face is compatible with hints
        // To check in activeMode:
        // - Loop is a cycle
        // - only one loop

        // Does loop intersect itself?
        const vIDsToCheck = (edge && !isActiveMode ?
            // If edge is marked as filled in, check attached vertices.
            (edge.metadata.userGuess === 1 ? edge.vertexIDs : []) :
            // If global, check all vertices.
            this.vertices.keys());
        result.vertexViolations = findVertexViolations(this, vIDsToCheck);
        for (const vId of result.vertexViolations) {
            result.status = 1; // failed
            console.log(`checkUserSolution: loop intersects itself at vertex ${vId}`);
            if (!isActiveMode && !this.highlightRuleViolations) {
                continue; // The player has passive highlighting turned off.
            }
            if (edge) {
                if (edge.metadata.userGuess === 1) {
                    // Highlight the just-clicked edge in red.
                    clearedEdgeHighlights = this.highlightEdgeError(edgeMesh, clearedEdgeHighlights);
                }
            } else {
                // Highlight all filled-in edges of the vertex in red.
                // console.log(`checkUserSolution: highlighting all filled edges of v${vId} in red`);
                const vertex = this.vertices.get(vId);
                for (const vEdgeId of vertex.edgeIDs) {
                    const vEdge = this.edges.get(vEdgeId);
                    console.log(`   e${vEdgeId} has userGuess ${vEdge.metadata.userGuess}`);
                    if (vEdge.metadata.userGuess === 1) {
                        clearedEdgeHighlights = this.highlightEdgeError(this.getEdgeMesh(vEdgeId), clearedEdgeHighlights);
                    }
                }
            }
        }

        // Does each face have a number of edges filled in / ruled out compatible with its clue?
        const faceIDsToCheck = (edge && !isActiveMode ? edge.faceIDs : this.faces.keys());
        result.clueViolations = findClueViolations(this, faceIDsToCheck, isActiveMode);
        for (const violation of result.clueViolations) {
            result.status = 1; // failed
            console.log(`checkUserSolution: face ${violation.faceId} ${violation.message}`);
            // TODO: highlight clue as error
        }

        // Passive checks stop here.
        if (!isActiveMode) return result;

        // Active mode: count the guesses that contradict the stored solution.
        // (Every rule violation involves at least one such mismatch, so this
        // is THE error count to report; but mind that the edge IDs are
        // spoilers -- see the @returns doc.)
        result.mismatchedEdgeIds = findSolutionMismatches(this, this.getCurrentPuzzle().solution);

        // Don't keep checking if we've already failed.
        if (result.status === 1) return result;

        // Do the filled-in edges form a single complete loop?
        result.loopCheck = checkSingleLoop(this);
        if (!result.loopCheck.ok) {
            result.status = 1;
            return result;
        }

        // If we haven't failed yet, we passed!
        // Success! Puzzle is solved!
        console.log("checkUserSolution: Puzzle is solved!");
        result.status = 2;
        this.celebrateSolved();
        return result;
    }

    /**
     * Clears (sets back to unknown) every guess that contradicts the
     * puzzle's stored solution, as ONE undoable compound move -- so an
     * unwanted "clear errors" is recovered with a single Undo.
     *
     * This is player assistance: it consults the stored solution, but only
     * reveals wrong guesses by removing them. Correct guesses stay put.
     *
     * @returns {number} how many guesses were cleared
     */
    clearErrors() {
        const mismatchedEdgeIds = findSolutionMismatches(this, this.getCurrentPuzzle().solution);
        if (mismatchedEdgeIds.length === 0) {
            return 0; // Nothing to clear; don't record an empty move.
        }
        const deltas = mismatchedEdgeIds.map(edgeId => ({
            edgeId,
            prevState: this.edges.get(edgeId).metadata.userGuess,
            newState: 0,  // 0 = unknown
        }));
        this.undoStack.push(deltas);
        this.redoStack.length = 0;
        for (const delta of deltas) {
            this.applyEdgeState(delta.edgeId, 0);
        }
        // Every rule violation involves a mismatched edge, so any red error
        // highlights are now stale; remove them.
        this.clearEdgeHighlights();
        this.historyChanged();
        return deltas.length;
    }

    /**
     * Clears all edge highlights, that is, sets the color of all edges to their user guess
     * color, removing any red or green highlighting.
     */
    clearEdgeHighlights() {
        console.log("clearEdgeHighlights");
        for (const [edgeId, edgeMesh] of this.edgeMeshMap) {
            const edge = this.edges.get(edgeId);
            // console.log(`   clearing edge ${edgeId} to state ${edge.metadata.userGuess}`);
            // TODO this double lookup seems wasteful. Maybe have a map directly from userGuess values to colors?
            edgeMesh.material.color = EDGE_COLORS[EDGE_STATES[edge.metadata.userGuess]];
        }
    }

    /**
     * Highlights the given edge in red.
     * @param edgeMesh - the mesh with which the edge is rendered
     * @param clearedEdgeHighlights - whether pre-existing edge highlights have been cleared
     * @returns {boolean} true - a convenience for setting clearedEdgeHighlights in the caller.
     */
    highlightEdgeError(edgeMesh, clearedEdgeHighlights) {
        // console.log(`highlightEdgeError: edge ${edgeMesh.userData.edgeId}`);
        if (!clearedEdgeHighlights) this.clearEdgeHighlights();
        if (edgeMesh) {  // null when running headless (e.g. unit tests): no meshes exist
            edgeMesh.material.color = EDGE_COLORS.error;
        }
        return true;
    }

    /**
     * Celebrates the user's success in solving the puzzle.
     *
     * The celebration itself (overlay message, camera animation) belongs to
     * the UI/view layer, so it lives in celebrateSolved() in ui.js; this
     * just reports the event to whoever registered onSolved.
     */
    celebrateSolved() {
        if (this.onSolved) this.onSolved();
    }
}
