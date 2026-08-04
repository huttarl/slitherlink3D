/**
 * Choosing what to play: the polyhedron and puzzle pickers, the "Next puzzle"
 * buttons, and the "are you sure?" that guards leaving a part-worked board.
 */
import {DEFAULT_GRID} from "./constants.js";
import {nextPuzzleLocation, playableGrids} from "./catalogue.js";
import {confirmDialog} from "./confirmDialog.js";
import {setWhereAmI} from "./panelLayout.js";

// Set true once the current puzzle has been solved, so that navigating away
// from it doesn't pointlessly ask whether to discard the player's marks.
let currentPuzzleSolved = false;

/** Told to us by the solved observer; see confirmLeavingPuzzle. */
export function markPuzzleSolved() {
    currentPuzzleSolved = true;
}

/**
 * Populates the grid (polyhedron) and puzzle pickers from the
 * data/grids.json catalogue (regenerate that file with
 * util/build_catalogue.py when data/ changes).
 * Selecting a grid or puzzle reloads the page with ?grid=<file stem> and
 * ?puzzle=<1-based number>, which createGameState() reads -- a page load
 * gives us scene teardown for free, avoiding manual disposal of THREE.js
 * objects. Fine for playtesting; an in-place scene swap can replace it later.
 */
export async function setupSelectors(puzzleGrid) {
    // cache: 'no-cache' forces a conditional request rather than trusting a
    // cached copy. Static servers (including python -m http.server) send no
    // Cache-Control for data files, so browsers guess a freshness lifetime and
    // can serve a stale catalogue for a long time -- and because this fetch
    // happens after page load, even a hard reload doesn't necessarily bypass
    // it. The server answers 304 when nothing changed, so this stays cheap.
    const response = await fetch('data/grids.json', {cache: 'no-cache'});
    if (!response.ok) {
        throw new Error(`Failed to load data/grids.json: ${response.statusText}`);
    }
    const catalogue = await response.json();
    const params = new URLSearchParams(window.location.search);
    const currentGrid = params.get('grid') || DEFAULT_GRID;

    // Grid picker. Only grids that have puzzles: there is nothing to play on
    // one that doesn't, so offering it would be a dead end. (The '(no puzzles)'
    // handling further down still stands, for a grid reached by an explicit
    // ?grid= -- which is why the current grid is kept in the list regardless.)
    const gridSelect = document.getElementById('gridSelect');
    for (const grid of playableGrids(catalogue, currentGrid)) {
        const option = document.createElement('option');
        option.value = grid.file;
        option.textContent = `${grid.gridName} (${grid.faces} faces)`;
        option.selected = (grid.file === currentGrid);
        gridSelect.appendChild(option);
    }
    gridSelect.addEventListener('change', async () => {
        // Keep the picker showing the puzzle that's actually loaded until the
        // move is confirmed; if we do navigate, the reload sets it from the URL.
        const chosen = gridSelect.value;
        gridSelect.value = currentGrid;
        if (await confirmLeavingPuzzle(puzzleGrid)) {
            // Reload the page with the chosen grid. Drop the puzzle number:
            // it referred to the previous grid's puzzle list.
            goToPuzzle(chosen, null);
        }
    });

    // Puzzle picker: one entry per puzzle of the current grid.
    const puzzleSelect = document.getElementById('puzzleSelect');
    const currentGridEntry = catalogue.grids.find(g => g.file === currentGrid);
    const gridName = currentGridEntry ? currentGridEntry.gridName : currentGrid;
    const numPuzzles = currentGridEntry ? currentGridEntry.numPuzzles : 0;
    if (numPuzzles === 0) {
        // Not in the catalogue, or a grid without puzzles.
        const option = document.createElement('option');
        option.textContent = '(no puzzles)';
        puzzleSelect.appendChild(option);
        puzzleSelect.disabled = true;
        setWhereAmI(gridName, null);
        return;
    }
    // The same clamping as GameState.setupScene: an out-of-range ?puzzle=
    // means the last puzzle gets loaded, so show that one as selected.
    const currentPuzzle = Math.min(parseInt(params.get('puzzle'), 10) || 1, numPuzzles);
    setWhereAmI(gridName, currentPuzzle);
    for (let n = 1; n <= numPuzzles; n++) {
        const option = document.createElement('option');
        option.value = String(n);
        option.textContent = `Puzzle ${n}`;
        option.selected = (n === currentPuzzle);
        puzzleSelect.appendChild(option);
    }
    puzzleSelect.addEventListener('change', async () => {
        const chosen = Number(puzzleSelect.value);
        puzzleSelect.value = String(currentPuzzle); // See the grid picker above.
        if (await confirmLeavingPuzzle(puzzleGrid)) {
            goToPuzzle(currentGrid, chosen);
        }
    });

    // "Next puzzle": one button in the panel (to skip ahead mid-solve) and
    // one in the celebration overlay (the natural "what's next?" moment).
    // Both walk the catalogue's progression order.
    const next = nextPuzzleLocation(catalogue, currentGrid, currentPuzzle);
    const panelNextButton = document.getElementById('nextPuzzle');
    const overlayNextButton = document.getElementById('overlayNextPuzzle');
    if (next === null) {
        // End of the catalogue: leave the panel button disabled, and let the
        // overlay say so rather than offering a button that does nothing.
        document.getElementById('overlayEndNote').classList.remove('hidden');
        return;
    }
    panelNextButton.disabled = false;
    panelNextButton.addEventListener('click', async () => {
        if (await confirmLeavingPuzzle(puzzleGrid)) {
            goToPuzzle(next.file, next.puzzle);
        }
    });
    overlayNextButton.classList.remove('hidden');
    overlayNextButton.addEventListener('click', (event) => {
        // Don't let the click also reach the overlay's dismiss handler.
        event.stopPropagation();
        goToPuzzle(next.file, next.puzzle);
    });
}

/**
 * Navigates to a puzzle by reloading with new URL parameters (see the note
 * on setupSelectors for why a reload).
 * @param {string} file - grid file stem, e.g. 'cube'
 * @param {number|null} puzzleNumber - 1-based puzzle number, or null to drop
 *     the parameter (so the new grid starts at its first puzzle)
 */
function goToPuzzle(file, puzzleNumber) {
    const params = new URLSearchParams(window.location.search);
    params.set('grid', file);
    if (puzzleNumber === null) {
        params.delete('puzzle');
    } else {
        params.set('puzzle', String(puzzleNumber));
    }
    window.location.search = params.toString();
}

/**
 * Asks the player before abandoning a partly-worked puzzle, since navigating
 * reloads the page and the undo history goes with it. Silent when there's
 * nothing to lose: an untouched board, or one already solved.
 *
 * A non-empty undo history is our test for "has done something here". It only
 * ever grows from player actions (edge clicks, Reset, Clear errors), so it
 * can't produce false alarms, and it's O(1) rather than a scan of every edge.
 * It's also the more accurate question to ask, since it's the history itself
 * that a page reload destroys: after a Reset the board looks untouched, yet
 * one Undo would bring the player's work back -- so that IS worth asking about.
 *
 * @param {PuzzleGrid} puzzleGrid
 * @returns {boolean} true if it's OK to navigate away
 */
async function confirmLeavingPuzzle(puzzleGrid) {
    if (currentPuzzleSolved) return true;
    if (puzzleGrid.undoStack.length === 0) return true;
    return confirmDialog('Leave this puzzle? Your marks on it will be lost.',
                         'Leave puzzle');
}
