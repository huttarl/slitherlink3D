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
 * The grids worth offering the player: those that actually have puzzles.
 *
 * A grid can be in the catalogue with none -- its data/<id>-puzzles.json
 * missing, empty, or not generated yet -- and there is nothing to do on such a
 * grid, so it doesn't belong in the polyhedron picker. nextPuzzleLocation skips
 * the same grids when advancing, so the picker and the Next button agree on
 * what exists.
 *
 * @param {Object} catalogue - the parsed data/grids.json
 * @param {string|null} alwaysInclude - a grid file stem to keep regardless.
 *     Pass the currently loaded grid, so the picker can never name a different
 *     polyhedron than the one on screen. Belt and braces today: loading a
 *     puzzleless grid with an explicit ?grid= fails before the UI is built (a
 *     missing puzzle file 404s; an empty puzzles array trips "puzzle index out
 *     of range"), so there is no such grid to keep. It matters the moment that
 *     path is made to fail gracefully.
 * @returns {Array<Object>} catalogue entries, in catalogue (progression) order
 */
export function playableGrids(catalogue, alwaysInclude = null) {
    return catalogue.grids.filter(
        grid => grid.numPuzzles > 0 || grid.file === alwaysInclude);
}

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
