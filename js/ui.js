/**
 * Wiring the UI to the game, plus the celebration overlay.
 *
 * The bulkier pieces live in their own modules, and this one puts them
 * together: the panel's two shapes in panelLayout.js, check reporting in
 * checkFeedback.js, the pickers and navigation in puzzlePicker.js, and the
 * yes/no dialog in confirmDialog.js.
 */
import {makeInteraction} from "./interaction.js";
import {hideCheckFeedback, initCheckFeedback, showStartupNotice} from "./checkFeedback.js";
import {markPuzzleSolved, setupSelectors} from "./puzzlePicker.js";
import {isConfirmDialogOpen} from "./confirmDialog.js";
import {initAboutSolid} from "./aboutSolid.js";
import {updateClueColors} from "./clueRenderer.js";
import {updatePairMark} from "./pairMarkRenderer.js";
import {wantsTitleScreen} from "./titleScreen.js";
import {startCelebration, stopCelebration} from "./celebration.js";
import {CELEBRATION_TIMING} from "./constants.js";
import {isDebugEnabled} from "./debug.js";

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

    // Likewise the "About this solid" card: it waits on the catalogue, and
    // nothing else waits on it.
    initAboutSolid(gameState).catch(err => {
        console.error('Could not set up the About-this-solid card:', err);
    });

    // If loading fell back to another grid (see createGameState), tell the
    // player why they're looking at something other than what they asked for.
    if (gameState.startupNotice) {
        showStartupNotice(gameState.startupNotice);
    }

    initCheckFeedback(puzzleGrid);
    revealDebugPanel();
    wireSettingToggles(gameState, puzzleGrid);
    wireActionButtons(gameState, puzzleGrid);
    wireOverlay();
    wireKeyboardShortcuts(puzzleGrid);
}

/**
 * Shows the developer controls (Show IDs, Show Solution, face details) when
 * ?debug=1 asks for them, and leaves them hidden otherwise.
 *
 * The same switch as the traces and the solve-the-puzzle `s` key, rather than a
 * second one: everything here is for whoever is working on the game, and one
 * flag to remember beats three. It also works on a phone, which the previous
 * arrangement did not -- the panel could only be revealed by hand from the
 * browser console (see the comment on #debugPanel in main.html).
 *
 * The checkboxes inside are wired either way, by wireSettingToggles; this only
 * decides whether the panel can be seen.
 */
function revealDebugPanel() {
    if (!isDebugEnabled()) return;
    document.getElementById('debugPanel').classList.remove('hidden');
}

/**
 * Registers this layer's observers on the puzzle grid. PuzzleGrid reports
 * events but knows nothing about the DOM or GameState, so the wiring happens
 * here (see the note atop PuzzleGrid.js).
 */
function observePuzzleGrid(gameState, puzzleGrid) {
    puzzleGrid.onHistoryChanged = () => {
        updateUndoRedoButtons(puzzleGrid);
        // A change may have satisfied a clue, or unsatisfied one that was.
        updateClueColors(gameState);
        markCheckReady(puzzleGrid);
        // Any board change makes the last check's feedback stale -- and ends any
        // celebration, which was about a loop that may no longer be there.
        hideCheckFeedback();
        cancelCelebration(gameState);
    };
    // Draw, redraw or remove one arc. Fires on the player's own marks and equally
    // on an undo or a Reset, since those go through applyPairMark too -- which is
    // the whole reason the model reports the change rather than the UI inferring it.
    puzzleGrid.onPairMarkChanged = (pairKey, relation) => {
        updatePairMark(gameState, pairKey, relation);
    };
    puzzleGrid.onSolved = () => {
        markPuzzleSolved();
        celebrateSolved(gameState);
    };
    // Sync the buttons now: setupScene already loaded a puzzle (and so reset
    // the history) before these observers existed.
    updateUndoRedoButtons(puzzleGrid);
    // Likewise the clue colors, which start with every 0 clue already gray.
    // Not on the title screen, though: its board has the whole solution loop
    // drawn on it, so every clue there is satisfied and every digit would go
    // gray -- and there is nothing to scan for on a board nobody is playing.
    if (!wantsTitleScreen()) updateClueColors(gameState);
    markCheckReady(puzzleGrid);
}

/**
 * Highlights "Check solution" once the board is worth checking -- the filled
 * edges forming one complete loop. See PuzzleGrid.isReadyToCheck for why that,
 * and not "every clue satisfied".
 *
 * The same element carries the highlight in the drawer and in the collapsed
 * strip, since panelLayout moves the button rather than duplicating it.
 *
 * aria-keyshortcuts goes on and off with the highlight, because the two say the
 * same thing to different audiences: this button answers Enter from wherever
 * focus happens to be (see the Enter binding in wireKeyboardShortcuts). That is
 * the "default button" relationship, which a native form gets for free from
 * implicit submission and this has to state for itself. Set only while it's
 * true, so the attribute never advertises a shortcut that would do nothing.
 *
 * @param {PuzzleGrid} puzzleGrid
 */
function markCheckReady(puzzleGrid) {
    const ready = puzzleGrid.isReadyToCheck();
    const checkButton = document.getElementById('checkSolution');
    checkButton.classList.toggle('primary-action', ready);
    if (ready) {
        checkButton.setAttribute('aria-keyshortcuts', 'Enter');
    } else {
        checkButton.removeAttribute('aria-keyshortcuts');
    }
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

    // Player setting: rule out edges a move has just made impossible.
    const autoRuleOutToggle = document.getElementById('autoRuleOut');
    puzzleGrid.autoRuleOut = autoRuleOutToggle.checked;
    autoRuleOutToggle.addEventListener('change', (e) => {
        puzzleGrid.autoRuleOut = e.target.checked;
    });
    // Nothing else to do in either direction, which is the opposite of the
    // highlighting above and worth saying why. Switching ON does not sweep the
    // board: this assists a MOVE, and a sweep would deduce from every face and
    // vertex at once -- a chain reaction landing in the history as one huge entry
    // belonging to no click. Switching OFF leaves the existing marks alone,
    // because by then they are ordinary rule-outs, undone with Undo or Reset like
    // any other. Red highlights are decoration and so get cleared; these are
    // moves, and taking a player's marks away for them would be a liberty.
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

/**
 * A click anywhere on the overlay dismisses it, as does Escape (see
 * wireKeyboardShortcuts) and the "Stay here" button.
 *
 * Three ways to do one thing, which is deliberate: the click and Escape were
 * already there but invisible, so a player who wanted to admire the solid they
 * had just finished had no way of knowing they could. "Stay here" is that
 * affordance. Its own listener is strictly redundant while the whole overlay
 * dismisses on click -- the click would bubble up to that handler anyway -- but
 * a button whose behaviour depends on its container's is a trap for whoever
 * narrows the blanket handler later.
 */
function wireOverlay() {
    document.getElementById('overlayMessage').addEventListener('click', () => {
        hideOverlay();
    });
    document.getElementById('overlayStayHere').addEventListener('click', () => {
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

        // Enter runs the check once there is a loop to check, so the highlighted
        // button and the key agree -- a button that looks like the default action
        // and then ignores Enter is worse than no highlight at all.
        //
        // Bound globally rather than by focusing the button, which would be the
        // obvious way to make Enter work and has two costs this doesn't. Focus
        // would have to be TAKEN from wherever the player had put it, on the
        // click that closed the loop -- and taken again on every later click, or
        // it would snap back the moment they tabbed away. And a focused button
        // answers Space as well as Enter, so a stray Space would check the
        // puzzle. Here the highlight means "Enter does this", which is true from
        // wherever the player's focus happens to be.
        if (e.key === 'Enter' && !isOverlayVisible() && !focusOwnsKeystrokes()) {
            const checkButton = document.getElementById('checkSolution');
            if (!checkButton.disabled && puzzleGrid.isReadyToCheck()) {
                e.preventDefault();
                checkButton.click();
            }
        }

        // DEBUG ONLY, behind ?debug=1: "s" solves the puzzle outright and runs
        // the check, so the celebration can be watched again and again without
        // hand-solving a 131-edge loop each time. Gated because it is a spoiler
        // and a cheat, and a bare letter is safe only while it is gated.
        //
        // Clicks the button rather than calling checkUserSolution directly, so
        // this goes down the same path a player's Check does -- feedback panel
        // and all -- which is the point of a shortcut meant for testing it.
        if (isDebugEnabled() && e.key.toLowerCase() === 's'
                && !e.ctrlKey && !e.metaKey && !e.altKey && !focusOwnsKeystrokes()) {
            e.preventDefault();
            puzzleGrid.fillInSolution();
            document.getElementById('checkSolution').click();
            return;
        }

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

/** Beats 3 and 4, pending while beats 1 and 2 have the stage. */
let celebrationTimers = [];

/**
 * Celebrates the user's success in solving the puzzle. Called via PuzzleGrid's
 * onSolved observer.
 *
 * Four beats, in this order for a reason (see docs/celebration.md). The loop
 * glowing and the two regions colouring in belong to celebration.js; this
 * schedules the two that don't:
 *
 *   3. the TUMBLE, which is not decoration here -- a partition of a closed
 *      surface cannot be seen from one side, so turning the solid is what shows
 *      the two colours carrying on round the back;
 *   4. the DIALOG last, since the box sits over the middle of the board and
 *      hides the very thing it is congratulating.
 *
 * Both happen at once if the animation declined to run, since then there is
 * nothing to wait for (see startCelebration).
 *
 * @param {GameState} gameState
 */
function celebrateSolved(gameState) {
    const name = gameState.getPuzzleGrid().gridName;
    const elapsedTimeSec = Math.round(gameState.sceneManager.timer.getElapsed());
    const min = Math.floor(elapsedTimeSec / 60), sec = elapsedTimeSec % 60;
    // TODO: add HTML markup to body, and name of grid, time taken, etc.
    const tumble = () => gameState.sceneManager.startTumble();
    const show = () => displayOverlay("Congratulations!",
        `You solved this ${name} puzzle in ${min}m ${sec}s!`);

    if (startCelebration(gameState)) {
        celebrationTimers = [
            setTimeout(tumble, CELEBRATION_TIMING.tumbleSeconds * 1000),
            setTimeout(show, CELEBRATION_TIMING.dialogSeconds * 1000),
        ];
    } else {
        tumble();
        show();
    }
}

/**
 * Ends the celebration early, because the board has changed under it.
 *
 * Everything has to go: a glowing loop and a two-coloured surface that no longer
 * describe the marks on the board are nonsense, and so is a "Congratulations"
 * arriving three seconds after the player has broken their own loop.
 *
 * @param {GameState} gameState
 */
function cancelCelebration(gameState) {
    for (const timer of celebrationTimers) clearTimeout(timer);
    celebrationTimers = [];
    stopCelebration(gameState);
}

/** Is the celebration overlay up? While it is, it owns Enter: its own default
 *  button is focused, and checking the puzzle again behind it is exactly the
 *  loop this replaced (see displayOverlay). */
function isOverlayVisible() {
    return !document.getElementById('overlayMessage').classList.contains('hidden');
}

/**
 * Is focus on a control that acts on keystrokes itself?
 *
 * If it is, leave the key alone. For Enter that stops it both working the
 * control and checking the puzzle -- the common case being a player who has just
 * clicked a panel button, which keeps focus afterwards. For the debug solve key
 * it stops a bare letter being stolen from a <select>, where typing a letter
 * jumps to the matching option.
 */
function focusOwnsKeystrokes() {
    const focused = document.activeElement;
    if (!focused || focused === document.body) return false;
    return focused.matches('button, a[href], select, input, textarea, summary');
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

    // Move focus into the box, onto the action a player most likely wants next.
    // Without this, focus stayed on whatever opened the overlay -- normally
    // "Check solution" -- so Enter re-checked the puzzle just solved and reopened
    // this same box with a longer time on it. Focusing the button also makes
    // Enter do the obvious thing without a key handler of our own.
    //
    // Nothing needs to restore focus on dismissal: hiding a focused element
    // moves focus to the body, which leaves Enter doing nothing -- and returning
    // it to "Check solution" is precisely what we're getting away from.
    const nextButton = document.getElementById('overlayNextPuzzle');
    const stayButton = document.getElementById('overlayStayHere');
    (nextButton.classList.contains('hidden') ? stayButton : nextButton).focus();
}

function hideOverlay() {
    document.getElementById('overlayMessage').classList.add('hidden');
    // The celebration spin deliberately KEEPS RUNNING. Dismissing this is the
    // player saying they want to look at what they just solved, and a solid
    // already turning is the invitation to do that -- so stopping it here was
    // taking away the very thing they asked for. The first press on the board
    // hands the view back (see onPointerDown in interaction.js), which is the
    // right moment: that press is someone taking hold of it.
}
