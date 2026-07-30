/**
 * Module for setting up and executing UI actions
 */
import {makeInteraction} from "./interaction.js";
import {GameState} from "./GameState.js";
import {DEFAULT_GRID} from "./constants.js";

/**
 * Sets up the UI event listeners for the game.
 * @param gameState
 */
export function setupUI(gameState) {
    // Set up interaction - pass GameState directly
    gameState.setInteraction(makeInteraction(gameState));

    // Register this layer's observers on the puzzle grid. PuzzleGrid reports
    // events but knows nothing about the DOM or GameState, so the wiring
    // happens here (see the note atop PuzzleGrid.js).
    const puzzleGrid = gameState.getPuzzleGrid();
    puzzleGrid.onHistoryChanged = () => {
        updateUndoRedoButtons(puzzleGrid);
        // Any board change makes the last check's feedback stale.
        hideCheckFeedback();
    };
    puzzleGrid.onSolved = () => celebrateSolved(gameState);
    // Sync the buttons now: setupScene already loaded a puzzle (and so reset
    // the history) before these observers existed.
    updateUndoRedoButtons(puzzleGrid);

    // Populate the grid and puzzle pickers in the background; the rest of
    // the UI doesn't depend on them.
    setupSelectors().catch(err => {
        console.error('Could not set up the grid/puzzle selectors:', err);
    });

    // Wire up checkbox toggles and buttons
    const showIDsToggle = document.getElementById('showIDs');
    showIDsToggle.addEventListener('change', (e) => {
        gameState.toggleShowIDs(e.target.checked);
    });

    const showSolutionToggle = document.getElementById('showSolution');
    showSolutionToggle.addEventListener('change', (e) => {
        gameState.toggleShowSolution(e.target.checked);
    });

    // Player setting: passive red highlighting of rule violations.
    const highlightToggle = document.getElementById('highlightViolations');
    puzzleGrid.highlightRuleViolations = highlightToggle.checked;
    highlightToggle.addEventListener('change', (e) => {
        puzzleGrid.highlightRuleViolations = e.target.checked;
        if (!e.target.checked) {
            // Remove any red marks already on the board.
            puzzleGrid.clearEdgeHighlights();
        }
    });

    const checkSolutionButton = document.getElementById('checkSolution');
    checkSolutionButton.addEventListener('click', () => {
        const result = gameState.getPuzzleGrid().checkUserSolution(true);
        showCheckResults(result);
    });

    const clearErrorsButton = document.getElementById('clearErrors');
    clearErrorsButton.addEventListener('click', () => {
        const numCleared = gameState.getPuzzleGrid().clearErrors();
        // clearErrors fires onHistoryChanged, which hides the feedback area;
        // confirm the action afterward. (Recovery hint, since it's one move.)
        setCheckStatus(`Cleared ${numCleared} wrong ${numCleared === 1 ? 'mark' : 'marks'}. Undo restores them.`);
    });

    const undoButton = document.getElementById('undoMove');
    undoButton.addEventListener('click', () => {
        gameState.getPuzzleGrid().undo();
    });

    const redoButton = document.getElementById('redoMove');
    redoButton.addEventListener('click', () => {
        gameState.getPuzzleGrid().redo();
    });

    // No confirmation dialog for Reset: it's recorded as a single undoable
    // move, so an accidental reset is recovered with one Undo.
    const resetButton = document.getElementById('resetPuzzle');
    resetButton.addEventListener('click', () => {
        gameState.getPuzzleGrid().resetPuzzle();
    });

    const overlay = document.getElementById('overlayMessage');
    overlay.addEventListener('click', e => {
        hideOverlay();
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') hideOverlay();

        // Undo/redo keyboard shortcuts: Ctrl+Z (Cmd+Z on Mac) to undo;
        // add Shift, or use Ctrl+Y, to redo.
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
            e.preventDefault(); // Don't let the browser attempt its own undo.
            if (e.shiftKey) {
                gameState.getPuzzleGrid().redo();
            } else {
                gameState.getPuzzleGrid().undo();
            }
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
            e.preventDefault();
            gameState.getPuzzleGrid().redo();
        }
    })
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
async function setupSelectors() {
    const response = await fetch('data/grids.json');
    if (!response.ok) {
        throw new Error(`Failed to load data/grids.json: ${response.statusText}`);
    }
    const catalogue = await response.json();
    const params = new URLSearchParams(window.location.search);
    const currentGrid = params.get('grid') || DEFAULT_GRID;

    // Grid picker.
    const gridSelect = document.getElementById('gridSelect');
    for (const grid of catalogue.grids) {
        const option = document.createElement('option');
        option.value = grid.file;
        option.textContent = `${grid.gridName} (${grid.faces} faces)`;
        option.selected = (grid.file === currentGrid);
        gridSelect.appendChild(option);
    }
    gridSelect.addEventListener('change', () => {
        // Reload the page with the chosen grid. Drop the puzzle number:
        // it referred to the previous grid's puzzle list.
        const newParams = new URLSearchParams(window.location.search);
        newParams.set('grid', gridSelect.value);
        newParams.delete('puzzle');
        window.location.search = newParams.toString();
    });

    // Puzzle picker: one entry per puzzle of the current grid.
    const puzzleSelect = document.getElementById('puzzleSelect');
    const currentGridEntry = catalogue.grids.find(g => g.file === currentGrid);
    const numPuzzles = currentGridEntry ? currentGridEntry.numPuzzles : 0;
    if (numPuzzles === 0) {
        // Not in the catalogue, or a grid without puzzles.
        const option = document.createElement('option');
        option.textContent = '(no puzzles)';
        puzzleSelect.appendChild(option);
        puzzleSelect.disabled = true;
        return;
    }
    // The same clamping as GameState.setupScene: an out-of-range ?puzzle=
    // means the last puzzle gets loaded, so show that one as selected.
    const currentPuzzle = Math.min(parseInt(params.get('puzzle'), 10) || 1, numPuzzles);
    for (let n = 1; n <= numPuzzles; n++) {
        const option = document.createElement('option');
        option.value = String(n);
        option.textContent = `Puzzle ${n}`;
        option.selected = (n === currentPuzzle);
        puzzleSelect.appendChild(option);
    }
    puzzleSelect.addEventListener('change', () => {
        const newParams = new URLSearchParams(window.location.search);
        newParams.set('puzzle', puzzleSelect.value);
        window.location.search = newParams.toString();
    });
}

/**
 * Presents the outcome of an explicit "Check solution" to the player, in
 * the status line under the buttons.
 *
 * Spoiler policy: solution mismatches are reported only as a COUNT (with
 * the Clear-errors button offered); their locations are never highlighted.
 * Rule violations (self-crossings) are objective and deducible, so those
 * ARE highlighted -- that happened in checkUserSolution itself.
 *
 * @param {Object} result - return value of checkUserSolution(true)
 */
function showCheckResults(result) {
    const clearButton = document.getElementById('clearErrors');
    clearButton.classList.add('hidden');
    const numErrors = result.mismatchedEdgeIds ? result.mismatchedEdgeIds.length : 0;

    if (result.status === 2) {
        // The celebration overlay also appears, via the onSolved observer.
        setCheckStatus('Solved!');
    } else if (numErrors > 0) {
        let message = `${numErrors} of your marks ${numErrors === 1 ? "doesn't" : "don't"} match the solution.`;
        if (result.vertexViolations.length > 0) {
            message += ' Self-crossings are highlighted in red.';
        }
        setCheckStatus(message);
        clearButton.classList.remove('hidden');
    } else {
        // No wrong marks: report why the puzzle nevertheless isn't solved.
        let message;
        if (result.clueViolations.length > 0) {
            message = 'No wrong marks so far, but not every clue is satisfied yet.';
        } else {
            const reasons = {
                noEdges: "You haven't filled in any edges yet.",
                incomplete: 'No wrong marks so far, but the loop is not complete.',
                multipleLoops: 'No wrong marks so far, but there is more than one loop.',
            };
            message = reasons[result.loopCheck?.reason] ?? 'Not solved yet.';
        }
        setCheckStatus(message);
    }
}

/** Shows the given message in the check-feedback status line. */
function setCheckStatus(message) {
    document.getElementById('checkFeedback').classList.remove('hidden');
    document.getElementById('checkStatus').textContent = message;
}

/** Hides the check-feedback area (status line and Clear-errors button). */
function hideCheckFeedback() {
    document.getElementById('checkFeedback').classList.add('hidden');
    document.getElementById('clearErrors').classList.add('hidden');
}

/**
 * Enables/disables the Undo and Redo buttons to reflect whether there is
 * currently anything to undo or redo. Called by PuzzleGrid whenever the
 * undo/redo history changes.
 * @param {PuzzleGrid} puzzleGrid
 */
export function updateUndoRedoButtons(puzzleGrid) {
    document.getElementById('undoMove').disabled = (puzzleGrid.undoStack.length === 0);
    document.getElementById('redoMove').disabled = (puzzleGrid.redoStack.length === 0);
}

/**
 * Celebrates the user's success in solving the puzzle: spins the camera and
 * shows a congratulation overlay. Called via PuzzleGrid's onSolved observer.
 * @param {GameState} gameState
 */
function celebrateSolved(gameState) {
    const controls = gameState.sceneManager.controls;
    controls.autoRotateSpeed = 10.0;
    controls.autoRotate = true;

    const name = gameState.getPuzzleGrid().gridName;
    const elapsedTimeSec = Math.round(gameState.sceneManager.clock.getElapsedTime());
    const min = Math.floor(elapsedTimeSec / 60), sec = elapsedTimeSec % 60;

    // TODO: add HTML markup to body, and name of grid, time taken, etc.
    displayOverlay("Congratulations!", `You solved this ${name} puzzle in ${min}m ${sec}s!`);
    // TODO: give appropriate feedback to the user. special effects.
}

/**
 * Displays an overlay message on the screen. Can be dismissed with a click.
 * @param {string} title - Title of the message
 * @param {string} message - Message body (can contain HTML tags)
 */
export function displayOverlay(title, message) {
    // const overlay = document.getElementById('overlay');
    // overlay.textContent = message;
    // overlay.style.display = 'block';

    const overlay = document.getElementById('overlayMessage');
    const titleEl = document.getElementById('messageTitle');
    const bodyEl = document.getElementById('messageBody');

    titleEl.textContent = title;
    bodyEl.innerHTML = message;

    overlay.classList.remove('hidden');
}

function hideOverlay() {
    document.getElementById('overlayMessage').classList.add('hidden');

    // Stop auto-rotation if enabled.
    const gameState = GameState.getInstance();
    const controls = gameState.sceneManager.controls;
    controls.autoRotate = false;
}
