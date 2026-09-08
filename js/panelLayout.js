/**
 * The main panel's two shapes: a one-line strip, and the full drawer.
 *
 * Nothing here knows about the game -- only about the panel's own DOM. Its one
 * import is settings.js, which is equally free of the game and of the DOM;
 * the panel needs it because whether the player has collapsed the panel has to
 * outlive the page, changing puzzle being a reload. Other UI modules ask this
 * module whether the panel is collapsed (which decides where a message should
 * go) and tell it what to put in the where-am-I button.
 */
import {hasStoredSetting, loadSettings, saveSetting} from './settings.js';

// Buttons that live in the strip while the panel is collapsed: the things
// wanted DURING a puzzle. Everything else (pickers, Reset, how-to-play, the
// settings) is only wanted between puzzles or rarely, so it stays in the
// drawer. These are moved, not duplicated, so each button keeps one set of
// listeners and one disabled state.
// "Right side up" (levelCamera) is deliberately NOT here, though it is a
// mid-puzzle button: on a polyhedron floating in space (or water), "up" isn't
// important, so being rolled is a look rather than a problem, and the
// background carries what orientation cue there is. It stays in the drawer for
// anyone who does want it.
const STRIP_BUTTON_IDS = ['undoMove', 'redoMove', 'checkSolution'];

// A viewport this small in EITHER dimension starts the panel collapsed, which
// is what catches phones in both orientations while leaving tablets and
// desktops expanded. Width alone did not: a phone in landscape is wider than
// most thresholds and shorter than any of them, and the drawer's cost is
// height.
//
// The value lives on #info as data-narrow-query, because main.html's inline
// script needs the same breakpoint to collapse the panel before the first
// paint, and two copies would eventually disagree. The literal here is only a
// fallback for a page that somehow lacks the attribute.
const NARROW_SCREEN_QUERY_FALLBACK = '(max-width: 700px), (max-height: 500px)';

// How much room where-am-I needs before it is worth showing at all, in pixels.
// Below this it has been squeezed past saying anything -- at a browser zoom of
// 170% it came out as a one-pixel dot -- while still holding room the buttons
// need, so it is hidden instead and its space goes to them.
//
// About four characters at the strip's 14px. The label truncates with an
// ellipsis long before this, which is the intended behaviour and not what this
// is for: the point here is the difference between a short label and no label.
const MIN_WHERE_AM_I_WIDTH = 56;

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

/** initPanelLayout's fitStrip, published for setWhereAmI. */
let refitStrip = null;

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
        if (playerChose) {
            playerChoseState = true;
            // Remembered across the reload that changing puzzle performs, and
            // across visits. Only a deliberate toggle is written: an automatic
            // collapse would otherwise record itself as a preference and stop
            // the screen's width having a say ever again.
            saveSetting('panelCollapsed', collapsed);
        }
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
        fitStrip();
    }

    /**
     * Decides whether the strip can afford its where-am-I label.
     *
     * The strip's buttons do not shrink, and where-am-I is the only thing that
     * yields, so a narrow strip squeezes it away to nothing and THEN pushes the
     * last button off the right edge, out of reach. That is not a rare case: a
     * browser zoom of 170% -- an ordinary accessibility setting -- leaves a
     * 1080px phone with about 240 CSS pixels, where the buttons alone want 252.
     *
     * So: show the label, measure what it actually got, and drop it if that is
     * too little to read. Dropping it costs nothing that was working (it was a
     * dot) and returns its width to the buttons. Nothing is lost but the label
     * itself -- the panel toggle beside it opens the same drawer.
     *
     * Measured rather than decided by a width breakpoint, because what has to
     * fit is the buttons, and their number and wording can change.
     */
    function fitStrip() {
        const label = document.getElementById('whereAmI');
        if (!info.classList.contains('collapsed')) {
            label.hidden = false;    // the drawer's header always has room
            return;
        }
        // Un-hide before measuring, or a label hidden once would stay hidden:
        // its width would read 0 forever, however wide the strip became.
        label.hidden = false;
        label.hidden = label.offsetWidth < MIN_WHERE_AM_I_WIDTH;
    }

    // Screen width decides the starting state, and keeps deciding until the
    // player expresses a preference -- after that it's theirs to keep. Without
    // the listener, a phone rotated to landscape would stay collapsed, and a
    // page that happened to load at zero width (a hidden container, say) would
    // stay collapsed even once it became wide.
    const narrowScreen = window.matchMedia(narrowScreenQuery());
    // A stored value means the player has chosen before, on some earlier page.
    // Treat that exactly like choosing during this one, so the width stops
    // overriding it -- otherwise rotating the phone would undo their choice.
    let playerChoseState = hasStoredSetting('panelCollapsed');

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

    // Rotating the phone, or zooming, changes what the strip can hold without
    // changing whether it is collapsed -- so this listens to resize as well,
    // where the media-query listener above would never fire.
    window.addEventListener('resize', fitStrip);

    // The player's own choice if they have ever made one, the screen's width
    // otherwise. main.html's inline script applies the same rule before the
    // first paint; this agrees with it and moves the buttons.
    setCollapsed(playerChoseState
        ? loadSettings().panelCollapsed : narrowScreen.matches);
    // Publish them, so expandDrawer and setWhereAmI can reach in (see above).
    setPanelCollapsed = setCollapsed;
    refitStrip = fitStrip;
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
    // The text decides how much room the label asks for, so what fits has to be
    // decided again -- this arrives well after the strip was first laid out.
    if (refitStrip) refitStrip();
}
