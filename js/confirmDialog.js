/**
 * Our own yes/no dialog, in place of window.confirm().
 */

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
export function confirmDialog(message, confirmLabel = 'OK') {
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
export function isConfirmDialogOpen() {
    return !document.getElementById('confirmDialog').classList.contains('hidden');
}
