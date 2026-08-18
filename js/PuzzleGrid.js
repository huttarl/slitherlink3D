import { Grid } from './Grid.js';
import {EDGE_COLORS, EDGE_STATES, PAIR_RELATIONS} from './constants.js';
import {checkSingleLoop, findClueViolations, findDeducibleRuleOuts,
        findSolutionMismatches, findVertexViolations} from './solutionChecker.js';
import {debug} from './debug.js';
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

        // Undo/redo history of the user's changes.
        // Each move is an ARRAY of deltas, every one carrying {prevState, newState}:
        // a normal click produces a one-delta move; a puzzle reset produces
        // one compound move covering everything it cleared, so the whole
        // reset undoes in a single step.
        //
        // TWO KINDS of delta, told apart by which id they carry -- `edgeId` for an
        // edge's guess, `pairKey` for a mark on a pair of edges (see pairMarks
        // below). applyDelta is the single place that dispatches on it, so the
        // sites that BUILD deltas didn't have to learn about the distinction and
        // undo/redo work on a mixed move without caring.
        this.undoStack = [];
        this.redoStack = [];

        // What the player has recorded about pairs of edges: a Map from pair key
        // (see pairKey()) to an index into PAIR_RELATIONS. A pair at 'none' is
        // DELETED rather than stored as 0, so the map's size is the number of
        // marks on the board and iterating it visits only real ones.
        //
        // These are the player's own reasoning, and deliberately not checked
        // against the stored solution the way edge guesses are: a wrong pair mark
        // is a wrong deduction, and reporting it would be solving for them. That
        // also keeps solutionChecker.js out of it -- see the note in
        // docs/edge-pair-constraints.md about the browser holding a second
        // implementation of the rules that would have to be kept honest.
        this.pairMarks = new Map();

        // Observer callbacks, registered by the UI layer (see setupUI in
        // ui.js). They stay null-safe so this class works headless, e.g. in
        // tests, and so events that fire during scene setup -- before the UI
        // is wired up -- are simply ignored.
        //   onHistoryChanged() - the undo/redo history changed
        //   onSolved()         - the user's guesses form a correct solution
        //   onPairMarkChanged(pairKey, relation) - a pair mark was set, changed or
        //       cleared, `relation` being an index into PAIR_RELATIONS. The view
        //       layer draws the arcs; this class knows nothing about them, which is
        //       why it can report the change but not render it.
        this.onHistoryChanged = null;
        this.onSolved = null;
        this.onPairMarkChanged = null;

        // Player setting (a checkbox in the panel, wired up by ui.js):
        // whether passive checks highlight rule violations in red as the
        // player clicks. Explicit "Check solution" requests always highlight.
        this.highlightRuleViolations = true;

        // Player setting, likewise: whether each move also rules out the edges
        // it has just made impossible (see findDeducibleRuleOuts, and
        // setEdgeState, which is where it happens).
        //
        // Off by default, unlike the highlighting above, because the two are
        // different in kind: highlighting only REPORTS on the player's marks,
        // while this one makes marks of its own. An assistant that starts
        // uninvited would also make the game look, to a first-time player,
        // like it was playing itself.
        this.autoRuleOut = false;
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

        // A different puzzle means a fresh undo history, and pair marks go with
        // it: they are reasoning about THIS puzzle's clues and mean nothing
        // against the next one's. (In the app a puzzle change reloads the page
        // anyway, so this matters to the headless callers and to whenever that
        // reload finally goes -- see the TODO about switching puzzles in place.)
        this.undoStack.length = 0;
        this.redoStack.length = 0;
        this.pairMarks.clear();
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
        // And for every pair mark, in the SAME move: Reset means the board as the
        // player found it, and a board still carrying their pair reasoning is not
        // that. One Undo brings the whole lot back, marks included.
        for (const [key, relation] of this.pairMarks) {
            deltas.push({ pairKey: key, prevState: relation, newState: 0 });
        }
        if (deltas.length === 0) {
            return; // Board already pristine; don't record an empty move.
        }
        this.undoStack.push(deltas);
        this.redoStack.length = 0;
        for (const delta of deltas) {
            this.applyDelta(delta, 0);
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
     * The canonical key for a pair of edges: their ids, smaller first.
     *
     * Canonical because the caller's order is arbitrary -- the player taps two
     * edges in whichever order suits them, and (3, 7) and (7, 3) are one mark.
     * The same reason EdgePairing canonicalizes in util/slisolver.py, where COMPAS
     * spells an edge (u, v) or (v, u) interchangeably.
     *
     * @param {number} edgeA
     * @param {number} edgeB
     * @returns {string} e.g. '3,7'
     */
    static pairKey(edgeA, edgeB) {
        return edgeA < edgeB ? `${edgeA},${edgeB}` : `${edgeB},${edgeA}`;
    }

    /** The two edge ids a pair key names. The inverse of pairKey.
     * @param {string} key
     * @returns {number[]} the two ids, smaller first
     */
    static pairEdges(key) {
        return key.split(',').map(Number);
    }

    /**
     * Can these two edges carry a pair mark -- and if not, why not?
     *
     * Three conditions, and the third is the interesting one:
     *
     *   - two DISTINCT edges, both of which exist;
     *   - they meet at a vertex, since a relation between edges that never touch
     *     is not something a player reads off the board;
     *   - they share a FACE. Two edges at a vertex share a face exactly when they
     *     are consecutive in the cyclic order around it, and that is what gives
     *     the mark a corner to be drawn in. Non-consecutive pairs at a vertex are
     *     perfectly meaningful -- they are the four-face parity case
     *     docs/edge-pair-constraints.md says the edge-level store exists for --
     *     but there is nowhere on the surface to put the arc, so the UI cannot
     *     express them and this refuses them rather than accepting marks it
     *     cannot show.
     *
     * @param {number} edgeA
     * @param {number} edgeB
     * @returns {string|null} why it is not allowed, or null if it is
     */
    pairProblem(edgeA, edgeB) {
        if (edgeA === edgeB) return 'an edge cannot be paired with itself';
        const a = this.edges.get(edgeA);
        const b = this.edges.get(edgeB);
        if (!a) return `no such edge: ${edgeA}`;
        if (!b) return `no such edge: ${edgeB}`;
        const sharesVertex = a.vertexIDs.some(v => b.vertexIDs.includes(v));
        if (!sharesVertex) return `edges ${edgeA} and ${edgeB} do not meet`;
        const sharesFace = [...a.faceIDs].some(f => b.faceIDs.has(f));
        if (!sharesFace) {
            return `edges ${edgeA} and ${edgeB} meet but share no face, so there `
                 + 'is no corner to mark (see pairProblem)';
        }
        return null;
    }

    /**
     * The two edges meeting at one corner of a face: the pair a mark drawn there
     * would be about.
     *
     * This is the (face, vertex) -> (two edges) direction of the correspondence
     * docs/edge-pair-constraints.md describes, and it is what lets the player name
     * a pair by tapping a vertex and then a face -- two large targets -- rather
     * than having to hit two thin edges or a small corner.
     *
     * @param {number} faceId
     * @param {number} vertexId - must be a corner of that face
     * @returns {number[]|null} [edgeA, edgeB], or null if the vertex isn't on the
     *     face (which is how the interaction tells a valid second tap from a stray
     *     one, so it returns null rather than throwing)
     */
    cornerPair(faceId, vertexId) {
        const face = this.faces.get(faceId);
        if (!face) return null;
        const vids = face.vertexIDs;
        const at = vids.indexOf(vertexId);
        if (at < 0) return null;
        const before = vids[(at - 1 + vids.length) % vids.length];
        const after = vids[(at + 1) % vids.length];
        const edgeA = this.findEdgeByVertices(before, vertexId);
        const edgeB = this.findEdgeByVertices(vertexId, after);
        if (edgeA == null || edgeB == null) return null;
        return [edgeA, edgeB];
    }

    /**
     * Every corner that meets at one vertex -- one per face around it, which is
     * also one per markable pair of its edges (see cornerPair).
     *
     * @param {number} vertexId
     * @returns {{faceId: number, edges: number[]}[]}
     */
    cornersAtVertex(vertexId) {
        const vertex = this.vertices.get(vertexId);
        if (!vertex) return [];
        const corners = [];
        for (const faceId of vertex.faceIDs) {
            const edges = this.cornerPair(faceId, vertexId);
            if (edges) corners.push({faceId, edges});
        }
        return corners;
    }

    /** The relation currently marked on a pair, as an index into PAIR_RELATIONS.
     * 0 for an unmarked pair, which is what an absent entry means.
     * @param {number} edgeA
     * @param {number} edgeB
     * @returns {number}
     */
    getPairMark(edgeA, edgeB) {
        return this.pairMarks.get(PuzzleGrid.pairKey(edgeA, edgeB)) || 0;
    }

    /**
     * Applies a pair mark to the model, WITHOUT touching the undo history --
     * the counterpart of applyEdgeState, and the shared low-level step. Callers
     * making a new player move want setPairMark instead.
     *
     * @param {string} key - from pairKey()
     * @param {number} relation - index into PAIR_RELATIONS; 0 clears the mark
     */
    applyPairMark(key, relation) {
        if (relation === 0) {
            this.pairMarks.delete(key);
        } else {
            this.pairMarks.set(key, relation);
        }
        if (this.onPairMarkChanged) this.onPairMarkChanged(key, relation);
    }

    /**
     * Sets the relation marked on a pair of edges, recording it in the undo
     * history as one move. The choke point for new pair marks, as setEdgeState is
     * for new edge guesses.
     *
     * @param {number} edgeA
     * @param {number} edgeB
     * @param {number} relation - index into PAIR_RELATIONS; 0 clears the mark
     * @throws {Error} if the two edges cannot carry a mark -- see pairProblem.
     *     Thrown rather than ignored: the UI is expected to offer only pairs that
     *     can be marked, so reaching here with a bad one is a bug worth hearing
     *     about, not a player error to absorb.
     */
    setPairMark(edgeA, edgeB, relation) {
        const problem = this.pairProblem(edgeA, edgeB);
        if (problem) throw new Error(`Cannot mark this pair: ${problem}`);

        const key = PuzzleGrid.pairKey(edgeA, edgeB);
        const prevState = this.pairMarks.get(key) || 0;
        if (prevState === relation) return;   // Nothing to record.

        this.undoStack.push([{pairKey: key, prevState, newState: relation}]);
        this.redoStack.length = 0;
        this.applyPairMark(key, relation);
        debug(`setPairMark: ${key} -> ${PAIR_RELATIONS[relation]}`);
        this.historyChanged();
    }

    /**
     * Steps a pair to the next relation, wrapping through 'none' -- the pair
     * equivalent of cycleEdgeState in interaction.js.
     *
     * @param {number} edgeA
     * @param {number} edgeB
     * @param {boolean} [reverse=false] - step backwards, for shift-click and the
     *     long press
     * @returns {number} the relation now marked
     */
    cyclePairMark(edgeA, edgeB, reverse = false) {
        const was = this.getPairMark(edgeA, edgeB);
        // Stepping back by 1 == stepping forward by (length - 1), which avoids a
        // negative operand to %. Same trick as cycleEdgeState.
        const step = reverse ? PAIR_RELATIONS.length - 1 : 1;
        const now = (was + step) % PAIR_RELATIONS.length;
        this.setPairMark(edgeA, edgeB, now);
        return now;
    }

    /**
     * Whether the two edges' current states BEAR OUT a marked relation: both
     * edges decided, and decided the way the mark says they would be.
     *
     * Note what this is not. It never asks whether the mark is *true* of the
     * puzzle -- only whether the player has since settled both edges compatibly
     * with it, which is readable straight off the board and needs no solution.
     * A pair still holding an unknown edge is not satisfied but merely pending;
     * a pair whose edges CONTRADICT the mark is not satisfied either, and
     * deliberately gets the same answer as pending, so that a mark at odds with
     * the board is left standing for the player to see.
     *
     * @param {number} relation - index into PAIR_RELATIONS
     * @param {number} stateA - index into EDGE_STATES
     * @param {number} stateB
     * @returns {boolean}
     */
    static pairMarkSatisfied(relation, stateA, stateB) {
        // 0 = unknown, so the pair has not been settled yet either way.
        if (stateA === 0 || stateB === 0) return false;
        // Both are now 1 (filled in) or 2 (ruled out), so "filled in" and "not
        // filled in" between them cover the two cases each relation talks about.
        const filledA = stateA === 1;
        const filledB = stateB === 1;
        switch (PAIR_RELATIONS[relation]) {
            case 'exactlyOne':    return filledA !== filledB;
            case 'bothOrNeither': return filledA === filledB;
            default:              return false;   // 'none' -- no mark to satisfy.
        }
    }

    /**
     * The pair marks that this move has just used up: deltas that clear every
     * mark whose two edges the move has settled in agreement with it.
     *
     * Convenience, not assistance. The mark said something about two edges while
     * at least one was open; once both are decided compatibly it says nothing the
     * board does not already show, and leaving it there means the player must
     * click marks away by hand to keep the board readable. Compare the note in
     * docs/edge-pair-constraints.md on auto-rule-out, which must NOT read pair
     * marks: deducing an edge FROM a mark would be playing the puzzle, whereas
     * retiring a mark the player's own moves have overtaken adds no information
     * to the board and removes none either.
     *
     * Only pairs touching an edge this move changed are considered, so a mark
     * elsewhere is never disturbed -- and in particular a pair the player marks
     * on two already-decided edges stays put, since making a mark is not a move
     * that changes an edge. It is their deliberate click; swallowing it on the
     * spot would look like the mark never registered.
     *
     * @param {Array} move - the deltas applied so far, both kinds (pair deltas
     *     among them are ignored, having no edge whose state could have changed)
     * @returns {Object[]} pair deltas, each clearing one mark; empty if none
     */
    spentPairMarks(move) {
        if (this.pairMarks.size === 0) return [];
        const changed = new Set(move.filter(delta => delta.pairKey === undefined)
                                    .map(delta => delta.edgeId));
        const spent = [];
        for (const [key, relation] of this.pairMarks) {
            const [edgeA, edgeB] = PuzzleGrid.pairEdges(key);
            if (!changed.has(edgeA) && !changed.has(edgeB)) continue;
            const stateA = this.edges.get(edgeA).metadata.userGuess;
            const stateB = this.edges.get(edgeB).metadata.userGuess;
            if (PuzzleGrid.pairMarkSatisfied(relation, stateA, stateB)) {
                spent.push({pairKey: key, prevState: relation, newState: 0});
            }
        }
        return spent;
    }

    /**
     * Applies one delta of either kind, in the given direction.
     *
     * The single place that knows a move can hold two kinds of delta; see the
     * note on undoStack in the constructor. Undo passes prevState, redo passes
     * newState, and neither has to care what it is looking at.
     *
     * @param {Object} delta - carries edgeId or pairKey
     * @param {number} state - the state to put it into
     */
    applyDelta(delta, state) {
        if (delta.pairKey !== undefined) {
            this.applyPairMark(delta.pairKey, state);
        } else {
            this.applyEdgeState(delta.edgeId, state);
        }
    }

    /**
     * Sets an edge's guess state and updates its mesh color, recording the
     * change in the undo history as one move.
     *
     * This is the choke point for new user guesses: route guess mutations
     * through here (or record them yourself, like resetPuzzle) so the undo
     * history stays complete.
     *
     * With the autoRuleOut setting on, the move also carries whatever the change
     * has just made impossible (see findDeducibleRuleOuts). Those go into the SAME
     * history entry, which is the whole reason this can be one function rather than
     * two: undo already restores a compound move in reverse, so one press takes
     * back the click together with everything it caused. Recorded separately they
     * would be several presses to unwind, in an order the player never chose.
     *
     * The move likewise carries any pair marks the change has used up (see
     * spentPairMarks), for the same reason and in the same entry -- and that
     * sweep runs whatever the autoRuleOut setting says, being cleanup rather
     * than deduction.
     *
     * @param {number} edgeId - ID of the edge to change
     * @param {number} newState - New state, an index into EDGE_STATES
     *     (0 = unknown, 1 = filled in, 2 = ruled out)
     */
    setEdgeState(edgeId, newState) {
        const edge = this.edges.get(edgeId);
        const move = [{ edgeId, prevState: edge.metadata.userGuess, newState }];
        // The player's own change goes in FIRST, before anything is deduced: the
        // rules read the board as it now stands, so they need the new mark in place
        // to see what it rules out.
        this.applyEdgeState(edgeId, newState);

        if (this.autoRuleOut) {
            for (const deducedId of findDeducibleRuleOuts(this, edgeId)) {
                const deduced = this.edges.get(deducedId);
                // prevState is read rather than assumed to be unknown, so that a
                // rule added later which marks an already-marked edge cannot
                // quietly make undo restore the wrong state.
                move.push({ edgeId: deducedId,
                            prevState: deduced.metadata.userGuess,
                            newState: 2 });   // 2 = ruled out
                this.applyEdgeState(deducedId, 2);
            }
            if (move.length > 1) {
                debug(`autoRuleOut: edge ${edgeId} -> ${newState} also ruled out `
                      + `${move.slice(1).map(d => d.edgeId).join(', ')}`);
            }
        }

        // Last, because an auto-ruled-out edge can be the one that settles a pair,
        // so the sweep has to see the board as this move finally leaves it. Also
        // into the SAME history entry, for the reason given above: one Undo takes
        // back the click along with the marks it retired.
        for (const delta of this.spentPairMarks(move)) {
            move.push(delta);
            this.applyPairMark(delta.pairKey, delta.newState);
            debug(`spent pair mark ${delta.pairKey} `
                  + `(${PAIR_RELATIONS[delta.prevState]}) cleared`);
        }

        this.undoStack.push(move);
        // A new move invalidates any previously-undone moves.
        this.redoStack.length = 0;
        this.historyChanged();
    }

    /**
     * Undoes the user's most recent move (edge-guess change or reset), if any.
     * @returns {boolean} true if a move was undone, false if history was empty
     */
    undo() {
        const move = this.undoStack.pop();
        if (!move) {
            debug('undo: nothing to undo');
            return false;
        }
        this.redoStack.push(move);
        // Restore in reverse order, in case a compound move ever contains
        // two deltas for the same edge.
        for (let i = move.length - 1; i >= 0; i--) {
            this.applyDelta(move[i], move[i].prevState);
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
            debug('redo: nothing to redo');
            return false;
        }
        this.undoStack.push(move);
        for (const delta of move) {
            this.applyDelta(delta, delta.newState);
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
            // Edge deltas only. A pair mark breaks no rule and is never checked
            // (see pairMarks in the constructor), so there is nothing to recheck
            // for one -- and it has no edge to hand to the check in any case.
            if (delta.pairKey !== undefined) continue;
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
     * The rule checks themselves are pure queries in solutionChecker.js; the
     * per-rule methods here (checkSelfCrossings, checkClues) choose their scope
     * (local vs. global) and act on their findings by highlighting. This method
     * runs them in order, stops where the mode says to, and decides the overall
     * status. Reporting to the player is up to the caller (see showCheckResults
     * in checkFeedback.js).
     */
    checkUserSolution(isActiveMode, edgeMesh = null, edge = null) {
        if (!this.puzzleData) {
            throw new Error('No puzzle data available');
        }

        debug(`checkUserSolution, activeMode ${isActiveMode} edgeId ${edgeMesh?.userData.edgeId}`);

        const result = {
            status: 0, // 0 = unknown, 1 = failed, 2 = solved
            vertexViolations: [],
            clueViolations: [],
            loopCheck: null,
            mismatchedEdgeIds: null,
            // Has the player done ANYTHING here -- filled an edge in or ruled
            // one out? Recorded here rather than left to the loop check (whose
            // 'noEdges' reason is about filled edges only) because an early
            // return on a rule violation skips that check, and an untouched
            // board violates every unsatisfied clue, so that early return is
            // exactly the case that needs it.
            //
            // Marks of EITHER kind, not just filled ones: ruling edges out is
            // real work, and a player who has only done that is asking a fair
            // question -- were my rule-outs right? -- which the check can answer,
            // since findSolutionMismatches flags a ruled-out edge that is in the
            // solution. Reporting "you haven't filled in any edges yet" refused
            // to answer it.
            hasMarks: this.hasAnyMarks(),
        };

        // Things to check:
        // - loop doesn't intersect self (no vertex has > 2 edges filled in)
        // - number of edges per face is compatible with hints
        // To check in activeMode:
        // - Loop is a cycle
        // - only one loop

        this.checkSelfCrossings(result, isActiveMode, edgeMesh, edge);
        this.checkClues(result, isActiveMode, edge);

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
        debug("checkUserSolution: Puzzle is solved!");
        result.status = 2;
        this.celebrateSolved();
        return result;
    }

    /**
     * Has the player filled in any edge at all?
     * @returns {boolean}
     */
    hasAnyFilledEdges() {
        for (const edge of this.edges.values()) {
            if (edge.metadata.userGuess === 1) return true;   // 1 = filledIn
        }
        return false;
    }

    /**
     * Has the player marked any edge at all, either way?
     *
     * Distinct from hasAnyFilledEdges, which asks the narrower question the loop
     * itself turns on -- isReadyToCheck wants that one, since a loop cannot be
     * complete without filled edges. This one asks whether the player has done
     * anything on this board, which is what decides whether a check has anything
     * to say (see checkUserSolution).
     *
     * @returns {boolean}
     */
    hasAnyMarks() {
        for (const edge of this.edges.values()) {
            if (edge.metadata.userGuess !== 0) return true;   // 0 = unknown
        }
        return false;
    }

    /**
     * Has the player drawn something worth checking: do the filled edges form
     * one complete, non-crossing loop?
     *
     * This deliberately says nothing about the CLUES. A puzzle's clues have a
     * unique solution, so "single loop AND every clue satisfied" is the same
     * statement as "solved" -- a highlight meaning that would only ever appear
     * once the player had already won, telling them the answer and leaving
     * "Check solution" with nothing to report. Closing a loop is instead the
     * player's own sense of being finished, and is worth checking precisely
     * because it may turn out to be wrong.
     *
     * Cheapest test first, so the later ones are usually skipped:
     *   1. any filled edge at all -- an untouched board is not ready;
     *   2. the vertex rule, O(vertices), which also rules out a crossing;
     *   3. only then the loop walk, which is O(edges).
     * None of it is costly enough to need the ordering, mind: a passive
     * checkUserSolution already runs on every click and already scans every edge
     * (hasAnyFilledEdges), so this is the same order of work as the click does
     * anyway -- a few hundred operations on the largest grid here. The ordering
     * is for clarity rather than for speed.
     *
     * @returns {boolean}
     */
    isReadyToCheck() {
        if (!this.hasAnyFilledEdges()) return false;
        // A dangling end or a crossing means the drawing isn't finished. Checking
        // this before the walk also keeps the walk well defined: at a vertex with
        // three filled edges it would have to guess which way to go.
        if (findVertexViolations(this, this.vertices.keys()).length > 0) return false;
        return checkSingleLoop(this).ok;
    }

    /**
     * Rule check: does the loop cross itself -- that is, has any vertex more
     * than two edges filled in? Records what it finds in `result` (setting
     * status to failed) and highlights the offending edges in red.
     *
     * Scope: everything, except in passive mode with a just-changed edge, where
     * only that edge's own vertices can have become crossings -- and not even
     * those if the edge was ruled OUT, since removing an edge can't create one.
     *
     * @private
     * @param {Object} result - accumulating return value of checkUserSolution
     * @param {boolean} isActiveMode
     * @param {THREE.Mesh|null} edgeMesh - mesh of the just-changed edge
     * @param {Edge|null} edge - the just-changed edge
     */
    checkSelfCrossings(result, isActiveMode, edgeMesh, edge) {
        const vIDsToCheck = (edge && !isActiveMode ?
            // If edge is marked as filled in, check attached vertices.
            (edge.metadata.userGuess === 1 ? edge.vertexIDs : []) :
            // If global, check all vertices.
            this.vertices.keys());
        result.vertexViolations = findVertexViolations(this, vIDsToCheck);

        // Highlighting starts by clearing what's already red, but only once per
        // check, however many violations we go on to mark.
        let clearedEdgeHighlights = false;
        for (const vId of result.vertexViolations) {
            result.status = 1; // failed
            debug(`checkUserSolution: loop intersects itself at vertex ${vId}`);
            if (!isActiveMode && !this.highlightRuleViolations) {
                continue; // The player has passive highlighting turned off.
            }
            if (edge) {
                if (edge.metadata.userGuess === 1) {
                    // Highlight the just-clicked edge in red.
                    clearedEdgeHighlights = this.highlightEdgeError(edgeMesh, clearedEdgeHighlights);
                }
            } else {
                clearedEdgeHighlights =
                    this.highlightFilledEdgesAt(vId, clearedEdgeHighlights);
            }
        }
    }

    /**
     * Highlights in red every filled-in edge meeting at the given vertex --
     * the whole crossing, since which of the edges is the wrong one is the
     * player's to work out.
     *
     * @private
     * @param {number} vId
     * @param {boolean} clearedEdgeHighlights - have stale highlights already
     *     been cleared during this check?
     * @returns {boolean} true, for the caller to assign back to
     *     clearedEdgeHighlights (see highlightEdgeError)
     */
    highlightFilledEdgesAt(vId, clearedEdgeHighlights) {
        debug(`checkUserSolution: highlighting all filled edges of v${vId} in red`);
        const vertex = this.vertices.get(vId);
        for (const vEdgeId of vertex.edgeIDs) {
            const vEdge = this.edges.get(vEdgeId);
            debug(`   e${vEdgeId} has userGuess ${vEdge.metadata.userGuess}`);
            if (vEdge.metadata.userGuess === 1) {
                clearedEdgeHighlights =
                    this.highlightEdgeError(this.getEdgeMesh(vEdgeId), clearedEdgeHighlights);
            }
        }
        return clearedEdgeHighlights;
    }

    /**
     * Rule check: does each face have a number of edges filled in / ruled out
     * compatible with its clue? Records what it finds in `result`.
     *
     * Scope: as checkSelfCrossings -- in passive mode a changed edge can only
     * affect the clues of its own two faces.
     *
     * @private
     * @param {Object} result - accumulating return value of checkUserSolution
     * @param {boolean} isActiveMode - clues must match EXACTLY in active mode;
     *     passively it's enough that they still can be satisfied
     * @param {Edge|null} edge - the just-changed edge
     */
    checkClues(result, isActiveMode, edge) {
        const faceIDsToCheck = (edge && !isActiveMode ? edge.faceIDs : this.faces.keys());
        result.clueViolations = findClueViolations(this, faceIDsToCheck, isActiveMode);
        for (const violation of result.clueViolations) {
            result.status = 1; // failed
            debug(`checkUserSolution: face ${violation.faceId} ${violation.message}`);
            // TODO: highlight clue as error. That will want the same
            // clear-stale-highlights-once bookkeeping the edges have
            // (checkSelfCrossings' clearedEdgeHighlights); a `clearedFaceHighlights`
            // flag used to sit in checkUserSolution unused, awaiting it.
        }
    }

    /**
     * Fills in the stored solution outright, as ONE undoable compound move.
     *
     * A DEVELOPMENT shortcut, not player assistance: it hands over the answer.
     * Its only caller is the debug-gated key in wireKeyboardShortcuts, which
     * exists so the solve celebration can be watched over and over without
     * hand-solving a 131-edge loop first.
     *
     * Leaves the ruled-out and unknown marks alone and only clears FILLED edges
     * that aren't in the solution. Two reasons: that is the minimum needed to
     * make the board check out, and it leaves the celebration's first beat -- the
     * non-loop edges fading toward ruled-out -- with something visible to do. If
     * this ruled everything else out, that beat would have nothing to fade and a
     * bug in it could never be seen.
     *
     * @returns {number} how many edges changed
     */
    fillInSolution() {
        const loop = this.getCurrentPuzzle().solution;
        const inSolution = new Set();
        for (let i = 0; i < loop.length; i++) {
            const edgeId = this.findEdgeByVertices(loop[i],
                                                   loop[(i + 1) % loop.length]);
            if (edgeId !== undefined && edgeId !== null) inSolution.add(edgeId);
        }

        const deltas = [];
        for (const [edgeId, edge] of this.edges) {
            const was = edge.metadata.userGuess;
            // 1 = filled in, 0 = unknown.
            const wanted = inSolution.has(edgeId) ? 1 : (was === 1 ? 0 : was);
            if (wanted !== was) {
                deltas.push({edgeId, prevState: was, newState: wanted});
            }
        }
        if (deltas.length === 0) {
            return 0;   // Already solved; don't record an empty move.
        }
        this.undoStack.push(deltas);
        this.redoStack.length = 0;
        for (const delta of deltas) {
            this.applyEdgeState(delta.edgeId, delta.newState);
        }
        this.clearEdgeHighlights();
        this.historyChanged();
        return deltas.length;
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
        debug("clearEdgeHighlights");
        for (const [edgeId, edgeMesh] of this.edgeMeshMap) {
            const edge = this.edges.get(edgeId);
            debug(`   clearing edge ${edgeId} to state ${edge.metadata.userGuess}`);
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
        // Optional chaining: edgeMesh is null when running headless (see below),
        // and debug()'s arguments are built whether or not it prints them.
        debug(`highlightEdgeError: edge ${edgeMesh?.userData.edgeId}`);
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
