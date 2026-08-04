/**
 * Module for setting up and executing UI actions
 */
import {makeInteraction} from "./interaction.js";
import {GameState} from "./GameState.js";
import {DEFAULT_GRID} from "./constants.js";
import {nextPuzzleLocation, playableGrids} from "./catalogue.js";

// Set true once the current puzzle has been solved, so that navigating away
// from it doesn't pointlessly ask whether to discard the player's marks.
let currentPuzzleSolved = false;

// Buttons that live in the strip while the panel is collapsed: the things
// wanted DURING a puzzle. Everything else (pickers, Reset, how-to-play, the
// settings) is only wanted between puzzles or rarely, so it stays in the
// drawer. These are moved, not duplicated, so each button keeps one set of
// listeners and one disabled state.
const STRIP_BUTTON_IDS = ['undoMove', 'redoMove', 'levelCamera', 'checkSolution'];

// Below this viewport width the panel starts collapsed. Chosen to catch
// phones in both orientations while leaving tablets and desktops expanded.
//
// The value lives on #info as data-narrow-query, because main.html's inline
// script needs the same breakpoint to collapse the panel before the first
// paint, and two copies would eventually disagree. The literal here is only a
// fallback for a page that somehow lacks the attribute.
const NARROW_SCREEN_QUERY_FALLBACK = '(max-width: 700px)';

/** The narrow-screen media query, as declared in main.html. */
function narrowScreenQuery() {
    const info = document.getElementById('info');
    return (info && info.getAttribute('data-narrow-query'))
        || NARROW_SCREEN_QUERY_FALLBACK;
}

// How long an informational check result stays up. One carrying the
// Clear-errors button ignores this and waits to be used instead.
const TOAST_SECONDS = 4;

// Longer, for the "that grid isn't available" notice at startup: it's a
// sentence, it's unexpected, and the player has just arrived.
const STARTUP_NOTICE_SECONDS = 8;

/** Where each strip button lives when the panel is expanded, so it can be put
 *  back exactly where it was. Keyed by element id. */
const buttonHomes = new Map();

/** Timer for auto-dismissing an informational toast. */
let toastTimer = null;

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
    puzzleGrid.onSolved = () => {
        currentPuzzleSolved = true;
        celebrateSolved(gameState);
    };
    // Sync the buttons now: setupScene already loaded a puzzle (and so reset
    // the history) before these observers existed.
    updateUndoRedoButtons(puzzleGrid);

    // Populate the grid and puzzle pickers, and wire the "Next puzzle"
    // buttons, in the background; the rest of the UI doesn't depend on them.
    setupSelectors(puzzleGrid).catch(err => {
        console.error('Could not set up the grid/puzzle selectors:', err);
    });

    // If loading fell back to another grid (see createGameState), tell the
    // player why they're looking at something other than what they asked for.
    // The toast rather than the drawer's status line: it's visible whether the
    // panel is open or collapsed, and it isn't a check result. Given longer
    // than a check message, since it's unexpected and worth reading.
    if (gameState.startupNotice) {
        showToast(gameState.startupNotice, false, STARTUP_NOTICE_SECONDS);
    }

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

    // "Right side up" only matters when the view can roll, i.e. with trackball
    // controls; with orbit controls it would be a button that does nothing.
    const levelButton = document.getElementById('levelCamera');
    if (gameState.sceneManager.controlsStyle === 'trackball') {
        levelButton.classList.remove('hidden');
        levelButton.addEventListener('click', () => {
            gameState.sceneManager.levelCamera();
        });
    }

    const checkSolutionButton = document.getElementById('checkSolution');
    checkSolutionButton.addEventListener('click', () => {
        const result = gameState.getPuzzleGrid().checkUserSolution(true);
        showCheckResults(result);
    });

    // Clearing errors is offered in two places -- the drawer's feedback line
    // and the toast -- so both buttons run the same handler.
    const clearErrors = () => {
        const numCleared = gameState.getPuzzleGrid().clearErrors();
        // clearErrors fires onHistoryChanged, which hides the feedback area;
        // confirm the action afterward. (Recovery hint, since it's one move.)
        reportCheckMessage(
            `Cleared ${numCleared} wrong ${numCleared === 1 ? 'mark' : 'marks'}. Undo restores them.`,
            false);
    };
    document.getElementById('clearErrors').addEventListener('click', clearErrors);
    document.getElementById('toastClearErrors').addEventListener('click', clearErrors);

    document.getElementById('toastDismiss').addEventListener('click', hideToast);

    // The panel's layout is set up before this, by initPanelLayout, so that a
    // phone never shows the full panel while the puzzle loads.

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
async function setupSelectors(puzzleGrid) {
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

/**
 * Asks the player a yes/no question, using our own overlay rather than
 * window.confirm() (whose placement and styling don't match the app).
 *
 * Unlike window.confirm this can't block, so it returns a promise: callers
 * must await it.
 *
 * Cancelling is the safe answer, so Escape and a click on the backdrop
 * outside the message box both count as "no". The confirm button takes focus,
 * so Enter accepts (native button behavior -- no key handling needed for it).
 *
 * @param {string} message - the question to show
 * @param {string} [confirmLabel] - label for the confirm button; name the
 *     action ("Leave puzzle") rather than saying "OK" where possible
 * @returns {Promise<boolean>} true if the player confirmed
 */
function confirmDialog(message, confirmLabel = 'OK') {
    const dialog = document.getElementById('confirmDialog');
    document.getElementById('confirmMessage').textContent = message;
    const okButton = document.getElementById('confirmOK');
    const cancelButton = document.getElementById('confirmCancel');
    okButton.textContent = confirmLabel;
    dialog.classList.remove('hidden');
    okButton.focus();

    return new Promise(resolve => {
        // All the listeners are removed together, so the dialog leaves no
        // handlers behind and can be reused for the next question.
        function finish(answer) {
            dialog.classList.add('hidden');
            okButton.removeEventListener('click', onOK);
            cancelButton.removeEventListener('click', onCancel);
            dialog.removeEventListener('click', onBackdropClick);
            document.removeEventListener('keydown', onKeyDown);
            resolve(answer);
        }
        function onOK() { finish(true); }
        function onCancel() { finish(false); }
        function onBackdropClick(event) {
            // Only the dark area around the box, not the box itself.
            if (event.target === dialog) finish(false);
        }
        function onKeyDown(event) {
            if (event.key === 'Escape') finish(false);
        }

        okButton.addEventListener('click', onOK);
        cancelButton.addEventListener('click', onCancel);
        dialog.addEventListener('click', onBackdropClick);
        document.addEventListener('keydown', onKeyDown);
    });
}

/** True while the confirmation dialog is waiting for an answer. */
function isConfirmDialogOpen() {
    return !document.getElementById('confirmDialog').classList.contains('hidden');
}

/**
 * Wires the panel's collapse/expand behaviour and sets the starting state.
 *
 * Collapsed, the panel is a one-line strip: menu button, where-am-I, and the
 * buttons a player reaches for mid-puzzle. That's all a phone can spare -- the
 * full panel covered a third of the screen. Wide screens start expanded, as
 * before, but can still collapse for an unobstructed board.
 *
 * Picking a polyhedron or puzzle needs no auto-collapse: those navigate, and
 * the fresh page applies the same starting rule.
 *
 * Exported and called FIRST, before the grid and puzzle are loaded: this only
 * needs the DOM, and doing it after loading meant a phone showed the full panel
 * through the whole load and then snapped to the strip. main.html's inline
 * script sets the collapsed class earlier still, before the first paint; this
 * agrees with it and moves the buttons.
 */
export function initPanelLayout() {
    const info = document.getElementById('info');
    const toggle = document.getElementById('panelToggle');
    const strip = document.getElementById('stripButtons');

    for (const id of STRIP_BUTTON_IDS) {
        const button = document.getElementById(id);
        buttonHomes.set(id, {parent: button.parentElement,
                             next: button.nextSibling,
                             label: button.textContent});
    }

    /** Moves the in-play buttons into the strip, or back into the drawer. */
    function setCollapsed(collapsed) {
        info.classList.toggle('collapsed', collapsed);
        toggle.setAttribute('aria-expanded', String(!collapsed));
        for (const id of STRIP_BUTTON_IDS) {
            const button = document.getElementById(id);
            const home = buttonHomes.get(id);
            if (collapsed) {
                strip.appendChild(button);
                // "Check solution" is too wide for a strip button; the full
                // wording stays in the tooltip.
                if (id === 'checkSolution') button.textContent = 'Check';
            } else {
                home.parent.insertBefore(button, home.next);
                button.textContent = home.label;
            }
        }
    }

    // Screen width decides the starting state, and keeps deciding until the
    // player expresses a preference -- after that it's theirs to keep. Without
    // the listener, a phone rotated to landscape would stay collapsed, and a
    // page that happened to load at zero width (a hidden container, say) would
    // stay collapsed even once it became wide.
    const narrowScreen = window.matchMedia(narrowScreenQuery());
    let playerChoseState = false;

    narrowScreen.addEventListener('change', () => {
        if (!playerChoseState) setCollapsed(narrowScreen.matches);
    });

    toggle.addEventListener('click', () => {
        playerChoseState = true;
        setCollapsed(!info.classList.contains('collapsed'));
    });
    // Where-am-I is a shortcut to the pickers, which live in the drawer.
    document.getElementById('whereAmI').addEventListener('click', () => {
        playerChoseState = true;
        setCollapsed(false);
    });

    setCollapsed(narrowScreen.matches);
}

/** True when the panel is collapsed, so check results belong in the toast. */
function isPanelCollapsed() {
    return document.getElementById('info').classList.contains('collapsed');
}

/** Labels the strip's where-am-I button, which says what's loaded and opens
 *  the pickers. Called once the catalogue is known.
 *
 * The name and the number go in separate spans: on a narrow strip the name is
 * the part that gets truncated, so the number -- the bit that changes as you
 * work through a grid -- stays legible. "Puzzle" is left out for the same
 * reason: it's the least informative word available.
 *
 * @param {string} gridName - e.g. "Truncated icosahedron"
 * @param {number|null} puzzleNumber - null for a grid with no puzzles
 */
function setWhereAmI(gridName, puzzleNumber) {
    document.getElementById('whereAmIGrid').textContent = gridName;
    document.getElementById('whereAmIPuzzle').textContent =
        puzzleNumber ? `· ${puzzleNumber}` : '· (none)';
}

/**
 * Shows a check result in the toast: a full-width bar along the bottom, used
 * while the panel is collapsed so the board stays visible and the message
 * needn't be abbreviated.
 *
 * @param {string} message
 * @param {boolean} offerClear - Show the Clear-errors button.
 */
function showToast(message, offerClear, seconds = TOAST_SECONDS) {
    const toast = document.getElementById('checkToast');
    document.getElementById('toastStatus').textContent = message;
    document.getElementById('toastClearErrors').classList.toggle('hidden', !offerClear);
    toast.classList.remove('hidden');

    clearTimeout(toastTimer);
    toastTimer = null;
    // A toast offering an action has to wait for it; one that only reports
    // gets out of the way on its own.
    if (!offerClear) {
        toastTimer = setTimeout(hideToast, seconds * 1000);
    }
}

/** Hides the check-result toast. */
function hideToast() {
    clearTimeout(toastTimer);
    toastTimer = null;
    document.getElementById('checkToast').classList.add('hidden');
    document.getElementById('toastClearErrors').classList.add('hidden');
}

/**
 * Reports a check message wherever the player is currently looking: the
 * toast when the panel is collapsed, the drawer's status line when it's open.
 *
 * @param {string} message
 * @param {boolean} offerClear - Whether to offer the Clear-errors button.
 */
function reportCheckMessage(message, offerClear) {
    if (isPanelCollapsed()) {
        showToast(message, offerClear);
    } else {
        setCheckStatus(message);
        document.getElementById('clearErrors').classList.toggle('hidden', !offerClear);
    }
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
    document.getElementById('clearErrors').classList.add('hidden');
    const numErrors = result.mismatchedEdgeIds ? result.mismatchedEdgeIds.length : 0;

    if (result.status === 2) {
        // The celebration overlay says this far better than a status line can,
        // so when it's going to appear (via the onSolved observer) the toast
        // stays out of the way; the drawer still notes it for a wide screen.
        if (isPanelCollapsed()) {
            hideToast();
        } else {
            setCheckStatus('Solved!');
        }
        return;
    }

    if (numErrors > 0) {
        let message = `${numErrors} of your marks ${numErrors === 1 ? "doesn't" : "don't"} match the solution.`;
        if (result.vertexViolations.length > 0) {
            message += ' Self-crossings are highlighted in red.';
        }
        reportCheckMessage(message, true);
        return;
    }

    // No wrong marks: report why the puzzle nevertheless isn't solved.
    let message;
    if (!result.hasFilledEdges) {
        // Checked before the clue test on purpose: an untouched board leaves
        // every nonzero clue unsatisfied, so the clue branch would otherwise
        // always answer first and "Looks good so far!" would be the response
        // to having done nothing at all.
        message = "You haven't filled in any edges yet.";
    } else if (result.clueViolations.length > 0) {
        message = 'Looks good so far! (Some clues remain unsatisfied.)';
    } else {
        const reasons = {
            incomplete: 'Looks good so far! (But the loop is not yet complete.)',
            multipleLoops: 'There is more than one loop!',
        };
        message = reasons[result.loopCheck?.reason] ?? 'Not solved yet.';
    }
    reportCheckMessage(message, false);
}

/** Shows the given message in the check-feedback status line. */
function setCheckStatus(message) {
    document.getElementById('checkFeedback').classList.remove('hidden');
    document.getElementById('checkStatus').textContent = message;
}

/** Hides the check-feedback area (status line and Clear-errors button), and
 *  the toast, wherever the last result was shown. Called on any board change,
 *  which makes that result stale. */
function hideCheckFeedback() {
    document.getElementById('checkFeedback').classList.add('hidden');
    document.getElementById('clearErrors').classList.add('hidden');
    hideToast();
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
