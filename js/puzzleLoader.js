/**
 * Puzzle loading and application module.
 * Handles loading puzzle data from JSON files and applying clues to grids.
 */

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
export function applyPuzzleToGrid(grid, puzzleData, puzzleIndex = 0, expectedGridId = null) {
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
    for (const [faceId, face] of grid.faces) {
        const faceIndex = face.metadata.index;

        // Get clue for this face (-1 if beyond clues array)
        const clue = faceIndex < puzzle.clues.length ? puzzle.clues[faceIndex] : -1;

        // Validate clue value - must be -1 or in range 0..numEdges (inclusive)
        // Note: Slitherlink clues indicate how many edges of a face are in the solution loop
        if (clue !== -1) {
            const numEdges = face.edges.length;
            if (!Number.isInteger(clue) || clue < 0 || clue > numEdges) {
                throw new Error(`Invalid clue ${clue} for face ${faceIndex}: must be -1 or 0-${numEdges}`);
            }
        }

        // Apply clue to face metadata
        face.metadata.clue = clue;
    }
}
