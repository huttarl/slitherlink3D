/**
 * The player's settings, kept across page loads.
 *
 * Changing grid or puzzle RELOADS the page (see puzzlePicker.js), so a setting
 * that lives only in a checkbox is lost every time the player moves on -- which
 * is what this exists to fix.
 *
 * localStorage rather than sessionStorage, deliberately: a preference is a fact
 * about the player, not about the visit. Someone who turns the tidying on
 * because the bookkeeping bores them will still find it boring tomorrow, and
 * someone who mutes a sound wants it to stay muted.
 *
 * Knows nothing of the DOM, THREE or GameState -- ui.js does the wiring, the
 * same arrangement PuzzleGrid's observers use. So this runs headless in the
 * unit tests, where there is no localStorage at all and every call simply
 * falls back to the defaults.
 */
import {SETTINGS_DEFAULTS} from './constants.js';
import {debug} from './debug.js';

/**
 * One key holding one object, rather than a key per setting: adding a setting
 * is then a new field, and a dropped one leaves only harmless junk behind.
 *
 * Namespaced because localStorage is scoped to the ORIGIN, not to the path, and
 * the app is served from a directory on a shared domain -- so every other page
 * on huttar.net reads and writes the same storage. A bare 'settings' key would
 * be inviting a collision with a neighbor.
 */
const STORAGE_KEY = 'slitherlink3D.settings';

/**
 * The browser's storage, or null where there isn't one.
 *
 * Merely TOUCHING localStorage throws in some configurations (site data
 * blocked, and historically Safari's private browsing), so even the lookup is
 * guarded. Absent under file://, where Chrome gives the page an opaque origin
 * -- which is worth knowing when testing, since docs/project-overview.md
 * offers opening main.html directly as an alternative to util/serve.py.
 *
 * @returns {?Storage}
 */
function storage() {
    try {
        return globalThis.localStorage ?? null;
    } catch (err) {
        debug(`settings: no localStorage available (${err})`);
        return null;
    }
}

/**
 * Whatever is actually stored, as a plain object; {} if there is nothing
 * usable. Not merged with the defaults -- see saveSetting for why that
 * distinction matters.
 *
 * @returns {Object}
 */
function readStored() {
    const store = storage();
    if (!store) return {};
    let text;
    try {
        text = store.getItem(STORAGE_KEY);
    } catch (err) {
        debug(`settings: could not read stored settings (${err})`);
        return {};
    }
    if (!text) return {};
    try {
        const stored = JSON.parse(text);
        // Anything but an object (an array, a bare number, null) is junk from
        // somewhere else, and spreading it would put nonsense in the settings.
        return (stored && typeof stored === 'object' && !Array.isArray(stored))
            ? stored : {};
    } catch (err) {
        debug(`settings: stored settings are not JSON (${err}); using defaults`);
        return {};
    }
}

/**
 * The settings to play by: the defaults, with any stored value laid over them.
 *
 * Storage outlives the code, so it can hold a setting that has since been
 * renamed or dropped, or one whose shape has changed. An entry is therefore
 * taken only if the key is still known AND the value is still the right type;
 * anything else is ignored rather than trusted, and the default stands.
 *
 * @returns {Object} a fresh object -- callers may keep and modify it
 */
export function loadSettings() {
    const settings = {...SETTINGS_DEFAULTS};
    for (const [key, value] of Object.entries(readStored())) {
        if (key in SETTINGS_DEFAULTS
                && typeof value === typeof SETTINGS_DEFAULTS[key]) {
            settings[key] = value;
        } else {
            debug(`settings: ignoring stored '${key}'`);
        }
    }
    return settings;
}

/**
 * Records one setting the player has changed.
 *
 * Only the keys the player has actually touched are written, which is why this
 * merges into what is STORED rather than into the loaded settings. Writing the
 * whole merged object would freeze today's defaults into every visitor's
 * storage, so changing a default later would reach only people who had never
 * been here before.
 *
 * A failed write costs nothing but the memory of it: the setting still applies
 * to the page in front of the player, it just won't be there next time.
 *
 * @param {string} key - must be one of SETTINGS_DEFAULTS
 * @param {*} value
 */
export function saveSetting(key, value) {
    if (!(key in SETTINGS_DEFAULTS)) {
        debug(`settings: refusing to store unknown setting '${key}'`);
        return;
    }
    const store = storage();
    if (!store) return;
    const stored = readStored();
    stored[key] = value;
    try {
        store.setItem(STORAGE_KEY, JSON.stringify(stored));
    } catch (err) {
        debug(`settings: could not store '${key}' (${err})`);
    }
}
