/**
 * Debug logging, off unless it's asked for.
 *
 * These traces (the solution checker's loop walk, the scene build, the grid's
 * edge bookkeeping) are what you want when something is wrong, and noise the
 * rest of the time: they fired on every Check, so a genuine console warning was
 * easy to miss among them, and the test runner's output was buried.
 *
 * Turn them on with `?debug=1` in the URL -- which survives puzzle navigation,
 * since that keeps the existing query parameters -- or, outside a browser (the
 * Node tests), with SLI_DEBUG=1 in the environment.
 */

/** Has debug output been asked for? Read once, at import time. */
function debugRequested() {
    // Browser: ?debug, ?debug=1, ?debug=anything. An explicit ?debug=0 is off,
    // so a URL can be left in place with the logging switched off.
    if (typeof window !== 'undefined' && window.location) {
        const value = new URLSearchParams(window.location.search).get('debug');
        if (value !== null) return value !== '0' && value !== 'false';
    }
    // Node: SLI_DEBUG=1 npm test
    if (typeof process !== 'undefined' && process.env && process.env.SLI_DEBUG) {
        return process.env.SLI_DEBUG !== '0';
    }
    return false;
}

let enabled = debugRequested();

/**
 * Logs like console.log, but only when debug output is enabled.
 *
 * Arguments are passed straight through, so `debug('centroid:', vector)` still
 * gets the browser's inspectable object rather than a stringified one.
 *
 * Mind that the arguments are BUILT whichever way the switch is set -- the gate
 * is inside this function, not around the call. So a message must be safe to
 * construct unconditionally (no dereferencing something that may be null), and
 * anything expensive to compute belongs behind isDebugEnabled(). It's also why
 * the traces in hot inner loops are left commented out rather than converted:
 * their cost would be paid on every frame or every edge, for nothing.
 */
export function debug(...args) {
    if (enabled) console.log(...args);
}

/** True when debug() will print. For skipping work done only to log it. */
export function isDebugEnabled() {
    return enabled;
}

/** Turns debug output on or off at runtime (for a console session, or a test
 *  that wants to capture the traces). */
export function setDebugEnabled(on) {
    enabled = !!on;
}
