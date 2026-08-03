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
    // no-cache: revalidate rather than trusting a cached copy, since puzzle
    // files get regenerated during development (see the note in ui.js).
    const response = await fetch(relPath, {cache: 'no-cache'});
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
        // Throwing again, having been softened to a console.log at some point:
        // continuing left the caller with nothing to load and the page died a
        // few steps later, showing an empty panel and no board. createGameState
        // now catches this and falls back to the default grid, which is the
        // graceful degradation the log was reaching for.
        throw new Error(`No puzzles in ${relPath}`);
    }

    return data;
}
