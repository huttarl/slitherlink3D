/**
 * The title screen: the app's name over an impressive solid, tumbling.
 *
 * A cold launch -- main.html with no ?grid= or ?puzzle= -- is a title screen
 * rather than a puzzle. It loads TITLE_SCREEN_GRID (a rhombicosidodecahedron,
 * with its clues on), hides the main panel, and shows a centred box with Start
 * and How to Play. Both buttons take the player to DEFAULT_GRID, which is the
 * tetrahedron: showy for the title, simple for the first puzzle.
 *
 * Any URL that names a grid or puzzle skips all this, so shared and bookmarked
 * links go straight to the board -- and so does everything the test suite loads.
 *
 * The rule for "is this a title screen?" is duplicated in main.html's inline
 * pre-paint script, which has to hide the panel before the first frame and can't
 * wait for a module to load. It's one line in both places; keep them in step.
 */
import {DEFAULT_GRID, TITLE_SCREEN_GRID} from "./constants.js";

/**
 * Should the title screen show, for this query string?
 *
 * @param {string|URLSearchParams} [search] - defaults to the current URL's
 * @returns {boolean} true on a cold launch: no grid and no puzzle asked for
 */
export function wantsTitleScreen(search = window.location.search) {
    const params = typeof search === 'string' ? new URLSearchParams(search) : search;
    return !params.has('grid') && !params.has('puzzle');
}

/**
 * Which grid to load, title screen or not. The single answer for everything
 * that needs to know: createGameState builds it, and the pickers label it.
 *
 * @param {string|URLSearchParams} [search]
 * @returns {string} a data/ filename stem
 */
export function gridIdFromUrl(search = window.location.search) {
    const params = typeof search === 'string' ? new URLSearchParams(search) : search;
    if (wantsTitleScreen(params)) return TITLE_SCREEN_GRID;
    return params.get('grid') || DEFAULT_GRID;
}

/** Was the player sent here by "How to Play"? (see the note in openHowToPlay) */
export function wantsHowToPlay(search = window.location.search) {
    const params = typeof search === 'string' ? new URLSearchParams(search) : search;
    return params.has('howto');
}

/**
 * Shows the title screen and wires its buttons.
 *
 * The overlay itself is already visible: main.html's inline script unhides it
 * before the first paint, so the title is there while the solid is still
 * loading, rather than appearing on top of it a moment later.
 */
export function initTitleScreen() {
    // Leaving is a navigation, as with the pickers: a fresh page load builds the
    // new grid and disposes the old scene for free. Nothing has been played yet,
    // so there is nothing to confirm or lose.
    document.getElementById('titleStart').addEventListener('click', () => {
        window.location.search = `?grid=${DEFAULT_GRID}`;
    });
    document.getElementById('titleHowTo').addEventListener('click', () => {
        // Same destination, plus a request to open the instructions there. The
        // parameter is the only way to carry the intent across the reload.
        window.location.search = `?grid=${DEFAULT_GRID}&howto=1`;
    });
}

/**
 * Opens the How to Play section, if the player arrived by that button.
 *
 * Then drops ?howto from the URL, without navigating: it has been acted on, and
 * leaving it there would re-open the instructions on every later puzzle (the
 * pickers carry existing parameters forward) and would be a strange thing to
 * bookmark.
 *
 * @param {function} expandDrawer - opens the panel, which a phone starts
 *     collapsed; the instructions live inside it
 */
export function openHowToPlay(expandDrawer) {
    if (!wantsHowToPlay()) return;

    expandDrawer();
    const instructions = document.getElementById('howToPlay');
    if (instructions) instructions.open = true;

    const params = new URLSearchParams(window.location.search);
    params.delete('howto');
    const query = params.toString();
    history.replaceState(null, '',
        window.location.pathname + (query ? `?${query}` : ''));
}
