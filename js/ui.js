/**
 * Wiring the UI to the game, plus the celebration overlay.
 *
 * The bulkier pieces live in their own modules, and this one puts them
 * together: the panel's two shapes in panelLayout.js, check reporting in
 * checkFeedback.js, the pickers and navigation in puzzlePicker.js, and the
 * yes/no dialog in confirmDialog.js.
 */
import {makeInteraction} from "./interaction.js";
import {GameState} from "./GameState.js";
import {hideCheckFeedback, initCheckFeedback, showStartupNotice} from "./checkFeedback.js";
import {markPuzzleSolved, setupSelectors} from "./puzzlePicker.js";
import {isConfirmDialogOpen} from "./confirmDialog.js";

/**
 * Sets up the UI event listeners for the game.
 *
 * The panel's layout is set up before this, by initPanelLayout, so that a phone
 * never shows the full panel while the puzzle loads.
 *
 * @param gameState
 */
export function setupUI(gameState) {
    // Set up interaction - pass GameState directly
    gameState.setInteraction(makeInteraction(gameState));

    const puzzleGrid = gameState.getPuzzleGrid();
    observePuzzleGrid(gameState, puzzleGrid);

    // Populate the grid and puzzle pickers, and wire the "Next puzzle"
    // buttons, in the background; the rest of the UI doesn't depend on them.
    setupSelectors(puzzleGrid).catch(err => {
        console.error('Could not set up the grid/puzzle selectors:', err);
    });

    // If loading fell back to another grid (see createGameState), tell the
    // player why they're looking at something other than what they asked for.
    if (gameState.startupNotice) {
        showStartupNotice(gameState.startupNotice);
    }

    initCheckFeedback(puzzleGrid);
    wireSettingToggles(gameState, puzzleGrid);
    wireActionButtons(gameState, puzzleGrid);
    wireOverlay();
    wireKeyboardShortcuts(puzzleGrid);
}

/**
 * Registers this layer's observers on the puzzle grid. PuzzleGrid reports
 * events but knows nothing about the DOM or GameState, so the wiring happens
 * here (see the note atop PuzzleGrid.js).
 */
function observePuzzleGrid(gameState, puzzleGrid) {
    puzzleGrid.onHistoryChanged = () => {
        updateUndoRedoButtons(puzzleGrid);
        // Any board change makes the last check's feedback stale.
        hideCheckFeedback();
    };
    puzzleGrid.onSolved = () => {
        markPuzzleSolved();
        celebrateSolved(gameState);
    };
    // Sync the buttons now: setupScene already loaded a puzzle (and so reset
    // the history) before these observers existed.
    updateUndoRedoButtons(puzzleGrid);
}

/** The checkboxes in the drawer: what to show, and how much help to give. */
function wireSettingToggles(gameState, puzzleGrid) {
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
}

/** Undo, Redo, Reset, and "Right side up". (Check and Clear errors belong to
 *  checkFeedback.js; the pickers and Next puzzle to puzzlePicker.js.) */
function wireActionButtons(gameState, puzzleGrid) {
    // "Right side up" only matters when the view can roll, i.e. with trackball
    // controls; with orbit controls it would be a button that does nothing.
    const levelButton = document.getElementById('levelCamera');
    if (gameState.sceneManager.controlsStyle === 'trackball') {
        levelButton.classList.remove('hidden');
        levelButton.addEventListener('click', () => {
            gameState.sceneManager.levelCamera();
        });
    }

    document.getElementById('undoMove').addEventListener('click', () => {
        puzzleGrid.undo();
    });

    document.getElementById('redoMove').addEventListener('click', () => {
        puzzleGrid.redo();
    });

    // No confirmation dialog for Reset: it's recorded as a single undoable
    // move, so an accidental reset is recovered with one Undo.
    document.getElementById('resetPuzzle').addEventListener('click', () => {
        puzzleGrid.resetPuzzle();
    });
}

/** A click anywhere on the overlay dismisses it. */
function wireOverlay() {
    document.getElementById('overlayMessage').addEventListener('click', () => {
        hideOverlay();
    });
}

function wireKeyboardShortcuts(puzzleGrid) {
    document.addEventListener('keydown', e => {
        // While the confirmation dialog is up it owns the keyboard: it handles
        // Escape itself, and undoing behind a modal question would be
        // confusing.
        if (isConfirmDialogOpen()) return;

        if (e.key === 'Escape') hideOverlay();

        // Undo/redo keyboard shortcuts: Ctrl+Z (Cmd+Z on Mac) to undo;
        // add Shift, or use Ctrl+Y, to redo.
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
            e.preventDefault(); // Don't let the browser attempt its own undo.
            if (e.shiftKey) {
                puzzleGrid.redo();
            } else {
                puzzleGrid.undo();
            }
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
            e.preventDefault();
            puzzleGrid.redo();
        }
    });
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
    gameState.sceneManager.startTumble();

    const name = gameState.getPuzzleGrid().gridName;
    const elapsedTimeSec = Math.round(gameState.sceneManager.timer.getElapsed());
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

    // Stop the celebration spin, if it was running.
    GameState.getInstance().sceneManager.stopTumble();
}
