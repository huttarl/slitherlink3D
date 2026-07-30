/**
 * Module for setting up and executing UI actions
 */
import {makeInteraction} from "./interaction.js";
import {GameState} from "./GameState.js";

/**
 * Sets up the UI event listeners for the game.
 * @param gameState
 */
export function setupUI(gameState) {
    // Set up interaction - pass GameState directly
    gameState.setInteraction(makeInteraction(gameState));

    // Wire up checkbox toggles and buttons
    const showIDsToggle = document.getElementById('showIDs');
    showIDsToggle.addEventListener('change', (e) => {
        gameState.toggleShowIDs(e.target.checked);
    });

    const showSolutionToggle = document.getElementById('showSolution');
    showSolutionToggle.addEventListener('change', (e) => {
        gameState.toggleShowSolution(e.target.checked);
    });

    const checkSolutionButton = document.getElementById('checkSolution');
    checkSolutionButton.addEventListener('click', () => {
        gameState.getPuzzleGrid().checkUserSolution(true);
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
