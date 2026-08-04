/**
 * Telling the player how their solution is doing.
 *
 * The same message goes to one of two places depending on the panel's shape:
 * the drawer's status line when the panel is open, and a toast bar along the
 * bottom of the screen when it's collapsed to the strip -- otherwise a phone
 * player presses Check and sees nothing at all. That choice is made in one
 * place, reportCheckMessage, so no caller has to think about it.
 */
import {isPanelCollapsed} from "./panelLayout.js";

// How long an informational check result stays up. One carrying the
// Clear-errors button ignores this and waits to be used instead.
const TOAST_SECONDS = 4;

// Longer, for the "that grid isn't available" notice at startup: it's a
// sentence, it's unexpected, and the player has just arrived.
const STARTUP_NOTICE_SECONDS = 8;

/** Timer for auto-dismissing an informational toast. */
let toastTimer = null;

/**
 * Wires the Check button, the two Clear-errors buttons and the toast's dismiss.
 *
 * @param {PuzzleGrid} puzzleGrid
 */
export function initCheckFeedback(puzzleGrid) {
    document.getElementById('checkSolution').addEventListener('click', () => {
        showCheckResults(puzzleGrid.checkUserSolution(true));
    });

    // Clearing errors is offered in two places -- the drawer's feedback line
    // and the toast -- so both buttons run the same handler.
    const clearErrors = () => {
        const numCleared = puzzleGrid.clearErrors();
        // clearErrors fires onHistoryChanged, which hides the feedback area;
        // confirm the action afterward. (Recovery hint, since it's one move.)
        reportCheckMessage(
            `Cleared ${numCleared} wrong ${numCleared === 1 ? 'mark' : 'marks'}. Undo restores them.`,
            false);
    };
    document.getElementById('clearErrors').addEventListener('click', clearErrors);
    document.getElementById('toastClearErrors').addEventListener('click', clearErrors);

    document.getElementById('toastDismiss').addEventListener('click', hideToast);
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
 * Says why the player is looking at something other than what they asked for
 * (see createGameState's fallback).
 *
 * The toast rather than the drawer's status line: it's visible whether the
 * panel is open or collapsed, and it isn't a check result. Given longer than a
 * check message, since it's unexpected and worth reading.
 *
 * @param {string} message
 */
export function showStartupNotice(message) {
    showToast(message, false, STARTUP_NOTICE_SECONDS);
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
 * Presents the outcome of an explicit "Check solution" to the player.
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

/**
 * Hides the check-feedback area (status line and Clear-errors button), and
 * the toast, wherever the last result was shown. Called on any board change,
 * which makes that result stale.
 */
export function hideCheckFeedback() {
    document.getElementById('checkFeedback').classList.add('hidden');
    document.getElementById('clearErrors').classList.add('hidden');
    hideToast();
}
