import { Grid } from './Grid.js';
import { EDGE_COLORS } from './constants.js';

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
        
        // Cross-references to THREE.js geometry
        this.faceMap = new Map();           // geometry face index -> face ID
        this.faceVertexRanges = new Map();  // face ID -> vertex range in geometry
        
        // Edge mesh references for interaction
        this.edgeMeshMap = new Map();       // edge ID -> THREE.Mesh
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
                edgeMesh.material.color.set(EDGE_COLORS.solution);
            }
        }
    }

    /** Resets all edge states to unknown */
    resetEdgeStates() {
        for (const [_edgeId, edge] of this.edges) {
            edge.metadata.userGuess = 0; // 0 = unknown
        }
    }

    /** Count the number of elements in an iterable that satisfy a predicate. */
    count(iter, pred) {
        let n = 0;
        for (const e of iter) if (pred(e)) n++;
        return n;
    }

    /**
     * Check whether the user's current guesses are a correct solution.
     * @param {boolean} isActiveMode - whether checking in active mode or not.
     * @param {THREE.Mesh|null} edgeMesh - mesh of edge whose state has been changed
     * @param {Edge|null} edge - edge whose state has been changed
     *
     * Passive mode is less thorough, called in response to each new change of user's guesses,
     * and local to the latest change (edgeMesh).
     * Active mode is called when user has explicitly asked for a solution check, and is global.
     *
     * Possible outcomes:
     * - highlight (in red) edges (or faces?) in violation of puzzle constraints
     * - "ok" message (so far so good)
     * - "solved" response (solution is complete and correct)
     */
    checkUserSolution(isActiveMode, edgeMesh = null, edge = null) {
        if (!this.puzzleData) {
            throw new Error('No puzzle data available');
        }

        const edgeId = edgeMesh?.userData.edgeId;
        console.log(`checkUserSolution, activeMode ${isActiveMode} edgeId ${edgeId}`);

        // Things to check:
        // - loop doesn't intersect self (no vertex has > 2 edges filled in)
        // - number of edges per face is compatible with hints
        // To check in activeMode:
        // - Loop is a cycle
        // - only one loop
        // Depends on: isActiveMode, autoFeedback

        // Does loop intersect itself?
        const vIDsToCheck = (edge ?
            // If edge is marked as filled in, check attached vertices.
            (edge.metadata.userGuess === 1 ? edge.vertexIDs : []) :
            // If global, check all vertices.
            this.vertices.keys());
        for (const vId of vIDsToCheck) {
            const vertex = this.vertices.get(vId);
            const numEdgesFilled = this.count(vertex.edgeIDs,
                (edgeId => this.edges.get(edgeId)?.metadata.userGuess === 1));
            console.log(`checkUserSolution: vertex ${vId} has ${numEdgesFilled} edges filled in`);
            if (numEdgesFilled > 2) {
                console.log(`checkUserSolution: loop intersects itself at vertex ${vId}`);
                // TODO: highlight offending edges in red only if appropriate to mode and settings.
                edgeMesh.material.color = EDGE_COLORS.error;
            }
        }
    }
}
