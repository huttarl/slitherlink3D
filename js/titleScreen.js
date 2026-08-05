/**
 * The title screen: the app's name over an impressive solid, tumbling.
 *
 * A cold launch -- main.html with no ?grid= or ?puzzle= -- is a title screen
 * rather than a puzzle. It loads one of the larger solids at random (with its
 * clues on), views it from closer in than a board, hides the main panel, and
 * shows a centred box with Start and How to Play. Both buttons take the player to
 * DEFAULT_GRID, which is the tetrahedron: showy for the title, simple for the
 * first puzzle.
 *
 * Any URL that names a grid or puzzle skips all this, so shared and bookmarked
 * links go straight to the board -- and so does everything the test suite loads.
 *
 * The rule for "is this a title screen?" is duplicated in main.html's inline
 * pre-paint script, which has to hide the panel before the first frame and can't
 * wait for a module to load. It's one line in both places; keep them in step.
 */
import {CAMERA_DISTANCE, CAMERA_FOV_DEGREES, DEFAULT_GRID, TITLE_SCREEN_FALLBACK_GRID,
        TITLE_SCREEN_FILL, TITLE_SCREEN_MIN_FACES} from "./constants.js";
import {loadCatalogue, playableGrids} from "./catalogue.js";

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
 * The solids allowed on the title screen: the playable ones big enough to look
 * impressive (see TITLE_SCREEN_MIN_FACES).
 *
 * @param {Object} catalogue - the parsed data/grids.json
 * @returns {Array<Object>} catalogue entries, in catalogue order
 */
export function titleScreenCandidates(catalogue) {
    return playableGrids(catalogue)
        .filter(grid => grid.faces >= TITLE_SCREEN_MIN_FACES);
}

/**
 * Picks the title screen's solid: one of the candidates, at random, so arriving
 * at the app shows a different polyhedron each time -- a hint, before anything is
 * explained, that there are many of these to play on.
 *
 * @param {Object} catalogue - the parsed data/grids.json
 * @param {function} [random] - source of randomness, injectable for tests
 * @returns {string} a data/ filename stem
 */
export function chooseTitleScreenGrid(catalogue, random = Math.random) {
    const candidates = titleScreenCandidates(catalogue);
    if (candidates.length === 0) return TITLE_SCREEN_FALLBACK_GRID;
    return candidates[Math.floor(random() * candidates.length)].file;
}

/**
 * How far back the camera sits on the title screen: closer in than on a board,
 * so the solid fills the frame rather than floating small behind the title box.
 *
 * Aspect-aware, because a fixed distance can't suit both shapes of screen. The
 * camera's field of view is vertical, so on a tall phone the horizontal view is
 * the narrow one, and a solid that looks comfortable on a desktop overflows into
 * a single face. This works back from the distance at which the circumsphere
 * exactly fills the narrower of the two fields of view, then backs off far enough
 * that the solid spans TITLE_SCREEN_FILL of it instead.
 *
 * Never farther than CAMERA_DISTANCE: on a narrow screen the arithmetic asks to
 * pull BACK from a board's framing (a phone at distance 6 already crops the
 * solid a little), and zooming out on the title screen isn't what was wanted.
 * The upshot is a big solid on a desktop and no change on a phone.
 *
 * @param {number} aspectRatio - viewport width / height
 * @returns {number} camera distance, in the same units as CAMERA_DISTANCE
 */
export function titleScreenCameraDistance(aspectRatio) {
    const halfFov = (CAMERA_FOV_DEGREES / 2) * Math.PI / 180;
    // The narrower half-angle: vertical on a wide window, horizontal on a tall
    // one. (Horizontal half-angle = atan(tan(vertical) * aspect).)
    const halfAngle = Math.atan(Math.tan(halfFov) * Math.min(1, aspectRatio));
    // Distance at which a sphere of radius 1 -- our solids' circumradius, near
    // enough -- exactly fills that angle. Solids are normalized to it.
    const fittingDistance = 1 / Math.sin(halfAngle);
    return Math.min(CAMERA_DISTANCE, fittingDistance / TITLE_SCREEN_FILL);
}

/**
 * The pick, made once per page load. Cached because two callers ask -- the scene
 * loads the grid, the pickers label it -- and they must not disagree about which
 * solid is on screen.
 */
let titleScreenGrid = null;

async function pickTitleScreenGrid() {
    if (titleScreenGrid === null) {
        try {
            titleScreenGrid = chooseTitleScreenGrid(await loadCatalogue());
        } catch (problem) {
            // The catalogue is how we know what solids exist and how big they
            // are. Without it there's no pick to make, but a title screen with
            // no solid on it would be worse than a predictable one.
            console.warn(`Couldn't choose a title screen solid ` +
                         `(${problem.message}); using ${TITLE_SCREEN_FALLBACK_GRID}.`);
            titleScreenGrid = TITLE_SCREEN_FALLBACK_GRID;
        }
    }
    return titleScreenGrid;
}

/**
 * Which grid to load, title screen or not. The single answer for everything
 * that needs to know: createGameState builds it, and the pickers label it.
 *
 * Async because the title screen's solid is chosen from the catalogue, which has
 * to be fetched. Both callers are already async, and the catalogue fetch is
 * shared (loadCatalogue caches it), so this costs no extra request.
 *
 * @param {string|URLSearchParams} [search]
 * @returns {Promise<string>} a data/ filename stem
 */
export async function gridIdFromUrl(search = window.location.search) {
    const params = typeof search === 'string' ? new URLSearchParams(search) : search;
    if (wantsTitleScreen(params)) return pickTitleScreenGrid();
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
