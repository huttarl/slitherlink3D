/**
 * Puzzle loading and application module.
 * Handles loading puzzle data from JSON files and applying clues to grids.
 */

import {EDGE_COLORS} from "./constants.js";

/**
 * Loads puzzle data from a JSON file.
 *
 * @param {string} relPath - Relative path to the puzzle JSON URL (e.g., 'data/T-puzzles.json')
 * @returns {Promise<Object>} Puzzle data with gridId and puzzles array
 * @throws {Error} If file cannot be loaded or contains invalid data
 */
export async function loadPuzzleData(relPath) {
    const response = await fetch(relPath);
    if (!response.ok) {
        throw new Error(`Failed to load puzzle from ${relPath}: ${response.statusText}`);
    }

    const data = await response.json();

    // Validate required fields per json-format.md
    // !data.gridId will be true if data is an empty string.
    if (!data.gridId || typeof data.gridId !== 'string') {
        throw new Error('Invalid or missing gridId in puzzle file');
    }
    if (!data.puzzles || !Array.isArray(data.puzzles) || data.puzzles.length === 0) {
        throw new Error('Invalid or missing puzzles array (must be non-empty)');
    }

    return data;
}

/**
 * Applies puzzle data (clues) to a grid.
 *
 * @param {Grid} grid - The grid to apply puzzle data to
 * @param {Object} puzzleData - Puzzle data with gridId and puzzles array
 * @param {number} puzzleIndex - Index of puzzle to apply (default 0)
 * @param {string} expectedGridId - Expected gridId to validate against
 * @throws {Error} If validation fails
 *
 * @description
 * The clues array in the puzzle corresponds to faces by their index in the original
 * JSON faces array. Each face stores this index in face.metadata.index.
 * Clue values must be -1 (no clue) or 0..n where n is the number of edges on that face.
 */
export function applyCluesToGrid(grid, puzzleData, puzzleIndex = 0, expectedGridId = null) {
    // Validate gridId matches
    if (expectedGridId && puzzleData.gridId !== expectedGridId) {
        throw new Error(`Grid ID mismatch: expected "${expectedGridId}", got "${puzzleData.gridId}"`);
    }

    // Validate puzzle index
    if (puzzleIndex < 0 || puzzleIndex >= puzzleData.puzzles.length) {
        throw new Error(`Invalid puzzle index: ${puzzleIndex} (available: 0-${puzzleData.puzzles.length - 1})`);
    }

    const puzzle = puzzleData.puzzles[puzzleIndex];

    // Validate clues array exists
    if (!puzzle.clues || !Array.isArray(puzzle.clues)) {
        throw new Error('Invalid or missing clues array in puzzle');
    }

    // Validate clues array length per json-format.md spec
    if (puzzle.clues.length > grid.faces.size) {
        throw new Error(`Clues array length (${puzzle.clues.length}) exceeds number of faces (${grid.faces.size})`);
    }

    // Apply clues to faces based on their index
    // For sparse puzzles, looping through all faces would be inefficient. But I don't expect puzzles
    // to be very sparse. If this becomes an issue, we could add an array to map from face indices to face IDs.
    for (const [_faceId, face] of grid.faces) {
        const faceIndex = face.metadata.index;

        // Get clue for this face (-1 if beyond clues array)
        const clue = faceIndex < puzzle.clues.length ? puzzle.clues[faceIndex] : -1;

        // Validate clue value - must be -1 or in range 0..numEdges (inclusive)
        // Note: Slitherlink clues indicate how many edges of a face are in the solution loop
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
 * Show a puzzle's solution to the grid by setting edge colors.
 *
 * @param {Grid} grid - The grid to apply solution to
 * @param {Object} puzzleData - Puzzle data with gridId and puzzles array
 * @param {number} puzzleIndex - Index of puzzle to apply (default 0)
 * @param {THREE.Mesh[]} edgeMeshes - edge mesh geometries
 * @throws {Error} If validation fails or solution is invalid
 *
 * @description
 * The solution array contains vertex indices from the original JSON vertices array that
 * trace out the solution loop. Since Grid vertex IDs correspond to JSON vertex indices,
 * we can use them directly. This function finds edges between consecutive vertices
 * (including last→first to close the loop) and sets the edge's geometry color to EDGE_COLORS.solution.
 *
 * TODO: this doesn't really belong in puzzleLoader. Think about structure...
 */
export function highlightSolution(grid, puzzleData, puzzleIndex = 0, edgeMeshes) {
    // console.log("highlightSolution", puzzleData); // debugging

    const puzzle = puzzleData.puzzles[puzzleIndex];
    const solutionVIds = puzzle.solution;

    // For each consecutive pair of vertices in the solution (including last→first)
    for (let i = 0; i < solutionVIds.length; i++) {
        const v1Id = solutionVIds[i];
        const v2Id = solutionVIds[(i + 1) % solutionVIds.length];

        // Find the edge between v1 and v2
        let foundEdge = false;
        for (const [eId, edge] of grid.edges) {
            if ((edge.vertexIDs[0] === v1Id && edge.vertexIDs[1] === v2Id) ||
                (edge.vertexIDs[0] === v2Id && edge.vertexIDs[1] === v1Id)) {
                // Flag that we found it.
                foundEdge = true;
                console.log("highlightSolution", `Found edge ${eId} between ${v1Id} and ${v2Id}`); // debugging
                edge.metadata.mesh.material.color = EDGE_COLORS.solution;
                break;
            }
        }

        // Validate that adjacent vertices in solution are connected by an edge
        if (!foundEdge) {
            throw new Error(`No edge found between vertices ${v1Id} and ${v2Id} in solution`);
        }
    }
}


/**
 * Checks a solution for obvious problems.
 *
 * @param {Grid} grid - The grid to apply solution to
 * @param {Object} puzzleData - Puzzle data with gridId and puzzles array
 * @param {number} puzzleIndex - Index of puzzle to apply (default 0)
 * @throws {Error} If validation fails or solution is invalid
 *  TODO: may change how we handle errors.
 *
 * @description
 * The solution array contains vertex indices from the original JSON vertices array that
 * trace out the solution loop. Since Grid vertex IDs correspond to JSON vertex indices,
 * we can use them directly. This function finds edges between consecutive vertices
 * (including last→first to close the loop) and ...
 */
export function validateSolution(grid, puzzleData, puzzleIndex) {
    // console.log("applySolutionToGrid", puzzleData); // debugging

    // Validate puzzle index
    if (puzzleIndex < 0 || puzzleIndex >= puzzleData.puzzles.length) {
        throw new Error(`Invalid puzzle index: ${puzzleIndex}`);
    }

    const puzzle = puzzleData.puzzles[puzzleIndex];

    const solution = puzzle.solution;

    // Validate solution exists
    if (!solution || !Array.isArray(solution)) {
        throw new Error('Invalid or missing solution in puzzle');
    }

    // Validate solution length per json-format.md spec
    if (solution.length < 3 || solution.length > grid.vertices.size) {
        throw new Error(`Solution length (${solution.length}) too small or exceeds number of vertices (${grid.vertices.size})`);
    }

    // Validate no duplicates in solution
    const uniqueVertices = new Set(solution);
    if (uniqueVertices.size !== solution.length) {
        throw new Error('Solution contains duplicate vertices');
    }

    // Validate vertex indices exist in grid (since we use JSON indices as Grid IDs)
    for (const idx of solution) {
        if (!Number.isInteger(idx) || !grid.vertices.has(idx)) {
            throw new Error(`Invalid vertex index ${idx} in solution (not found in grid)`);
        }
    }

    // Check that each edge in the solution (including last→first) exists in the grid.
    for (let i = 0; i < solution.length; i++) {
        const v1 = solution[i];
        const v2 = solution[(i + 1) % solution.length];

        // Find the edge between v1 and v2
        let edgeId = null;
        for (const [eId, edge] of grid.edges) {
            if ((edge.vertexIDs[0] === v1 && edge.vertexIDs[1] === v2) ||
                (edge.vertexIDs[0] === v2 && edge.vertexIDs[1] === v1)) {
                // Flag that we found it.
                edgeId = eId;
                // console.log("applySolutionToGrid", `Found edge ${eId} between ${v1} and ${v2}`); // debugging
                break;
            }
        }

        // Validate that adjacent vertices in solution are connected by an existing edge
        if (edgeId === null) {
            throw new Error(`No edge found between vertices ${v1} and ${v2} in solution`);
        }
    }
}
