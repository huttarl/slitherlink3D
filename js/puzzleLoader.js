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
 *
 * TODO: Degrade more gracefully if the file isn't valid.
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
        // throw new Error('Invalid or missing puzzles array (must be non-empty)');
        console.log('Invalid or missing puzzles array (must be non-empty)');
    }

    return data;
}
