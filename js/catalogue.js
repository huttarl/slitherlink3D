/**
 * Navigation over the grid catalogue (data/grids.json).
 *
 * Catalogue order IS the progression order: util/build_catalogue.py sorts
 * grids by size (edges, then faces), so walking the catalogue climbs steadily
 * in difficulty, and the polyhedron families interleave along the way.
 *
 * Pure functions with no imports, so they unit-test headless
 * (see js/tests/catalogue.test.js).
 */

/**
 * Finds the puzzle that follows the given one in progression order.
 *
 * Advances within the current grid while it has more puzzles, then moves to
 * the next grid in catalogue order that has any puzzles (skipping grids whose
 * puzzle file is missing or empty).
 *
 * @param {Object} catalogue - the parsed data/grids.json
 * @param {string} currentFile - the current grid's file stem (e.g. 'cube')
 * @param {number} currentPuzzleNumber - 1-based, as in the ?puzzle= parameter
 * @returns {{file: string, puzzle: number}|null} where to go next (puzzle is
 *     1-based), or null if there is no next puzzle: either this is the last
 *     puzzle in the catalogue, or currentFile isn't in the catalogue at all
 *     (so we can't say what follows it).
 */
export function nextPuzzleLocation(catalogue, currentFile, currentPuzzleNumber) {
    const grids = catalogue.grids;
    const index = grids.findIndex(grid => grid.file === currentFile);
    if (index < 0) return null;

    // More puzzles on this grid?
    if (currentPuzzleNumber < grids[index].numPuzzles) {
        return { file: currentFile, puzzle: currentPuzzleNumber + 1 };
    }

    // Otherwise the first puzzle of the next grid that has any.
    for (let i = index + 1; i < grids.length; i++) {
        if (grids[i].numPuzzles > 0) {
            return { file: grids[i].file, puzzle: 1 };
        }
    }

    return null; // End of the catalogue.
}
