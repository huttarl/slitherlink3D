/**
 * The main panel's two shapes: a one-line strip, and the full drawer.
 *
 * Nothing here knows about the game -- only about the panel's own DOM -- so
 * this module has no imports. Other UI modules ask it whether the panel is
 * collapsed (which decides where a message should go) and tell it what to put
 * in the where-am-I button.
 */

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

/** Where each strip button lives when the panel is expanded, so it can be put
 *  back exactly where it was. Keyed by element id. */
const buttonHomes = new Map();

/** initPanelLayout's collapse/expand function, published for expandDrawer. */
let setPanelCollapsed = null;

/**
 * Opens the drawer, for something outside this module that needs what's inside
 * it -- the title screen's "How to Play", which lands on a phone with the panel
 * collapsed and the instructions therefore out of sight.
 *
 * Counts as the player expressing a preference (they did click a button), so
 * the panel won't re-collapse itself on the next viewport change.
 */
export function expandDrawer() {
    if (setPanelCollapsed) setPanelCollapsed(false, {playerChose: true});
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
 * Called FIRST, before the grid and puzzle are loaded: this only needs the DOM,
 * and doing it after loading meant a phone showed the full panel through the
 * whole load and then snapped to the strip. main.html's inline script sets the
 * collapsed class earlier still, before the first paint; this agrees with it
 * and moves the buttons.
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

    /**
     * Moves the in-play buttons into the strip, or back into the drawer.
     *
     * @param {boolean} collapsed
     * @param {{playerChose: boolean}} [options] - set playerChose when the
     *     change came from something the player did, which stops later viewport
     *     changes overriding it (see the listener below)
     */
    function setCollapsed(collapsed, {playerChose = false} = {}) {
        if (playerChose) playerChoseState = true;
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
        setCollapsed(!info.classList.contains('collapsed'), {playerChose: true});
    });
    // Where-am-I is a shortcut to the pickers, which live in the drawer.
    document.getElementById('whereAmI').addEventListener('click', () => {
        setCollapsed(false, {playerChose: true});
    });

    setCollapsed(narrowScreen.matches);
    // Publish it, so expandDrawer can reach in (see above).
    setPanelCollapsed = setCollapsed;
}

/** True when the panel is collapsed, so check results belong in the toast. */
export function isPanelCollapsed() {
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
export function setWhereAmI(gridName, puzzleNumber) {
    document.getElementById('whereAmIGrid').textContent = gridName;
    document.getElementById('whereAmIPuzzle').textContent =
        puzzleNumber ? `· ${puzzleNumber}` : '· (none)';
}
