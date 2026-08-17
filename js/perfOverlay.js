/**
 * A small on-screen frame-timing readout, for checking performance on a device
 * where DevTools isn't practical -- which in practice means a phone.
 *
 * Turn it on with `?perf` in the URL (`?perf=0` explicitly off), the same switch
 * style as debug.js. Off by default and off cheaply: every entry point returns
 * immediately, so a player never pays for this.
 *
 * WHY AN OVERLAY rather than a trace. Profiling the desktop was easy and told us
 * nothing -- two Chrome traces of a drag came back at a flat 60fps with the main
 * thread 84% idle. Catching a phone needs either a USB cable and remote debugging,
 * or this. This also survives the thing a trace can't do: play normally for
 * minutes and glance down when it feels wrong.
 *
 * WHAT IT SEPARATES, and this is the point of it:
 *
 *   fps / worst   the interval between frames -- what the player actually sees.
 *   work          time from the top of animate() to the return of render(), so
 *                 all our JS plus the draw calls we issue.
 *
 * A long interval with SMALL work is not our JS: it's the GPU, the compositor,
 * or the device throttling. A long interval with LARGE work is ours to fix.
 * Without the split, every slow frame looks the same and points nowhere.
 *
 *   calls/tris    what we ask the GPU for per frame, from renderer.info. Each
 *                 edge cylinder and vertex sphere is its own mesh with its own
 *                 material, so this climbs steeply with grid size (the truncated
 *                 icosahedron's 182-face cousin comes to ~630 objects).
 *   buffer        the drawing buffer in real pixels, and the device pixel ratio.
 *                 The one most likely to bite a phone and the easiest to miss:
 *                 setPixelRatio(devicePixelRatio) at DPR 3 renders NINE times the
 *                 pixels of DPR 1, and a phone GPU has nowhere near nine times
 *                 the fill rate of a laptop's.
 */

/** Has the readout been asked for? Read once, at import time. */
function perfRequested() {
    if (typeof window === 'undefined' || !window.location) return false;
    const value = new URLSearchParams(window.location.search).get('perf');
    return value !== null && value !== '0' && value !== 'false';
}

const enabled = perfRequested();

// How often the readout is rewritten. Touching the DOM every frame would put
// this tool into its own measurement; once a second is enough to read anyway.
const REPORT_MS = 1000;

// A frame this long is a visible hitch: two intervals at 60Hz. Counted over each
// reporting window, because ONE bad frame a second is the complaint that a mean
// frame rate hides completely -- 59 good frames and a 100ms stall still average
// out near 60fps.
const HITCH_MS = 33;

let readout = null;
let frameStart = 0;
let previousStart = 0;

// Accumulated over the current reporting window.
let frames = 0;
let workTotal = 0;
let worstWork = 0;
let worstInterval = 0;
let hitches = 0;
let windowStart = 0;

/** Builds the readout element on first use. Top right: #info has the top left,
 *  .debugging the bottom right, and #checkToast the bottom strip.
 *
 *  position: fixed, not absolute -- see the note on #checkToast in main.html. On
 *  a phone 100vh is the LARGE viewport, so anything anchored inside
 *  #canvas-container can land off screen. pointer-events: none so it can never
 *  swallow a tap meant for the board underneath it. */
function makeReadout() {
    const element = document.createElement('div');
    element.id = 'perfReadout';
    element.style.cssText = [
        'position: fixed',
        'top: max(10px, env(safe-area-inset-top, 0px))',
        'right: 10px',
        'z-index: 1002',
        'pointer-events: none',
        'background: rgba(0, 0, 0, 0.75)',
        'color: #8f8',
        'font: 12px/1.45 ui-monospace, Menlo, Consolas, monospace',
        'white-space: pre',
        'padding: 6px 9px',
        'border-radius: 6px',
    ].join(';');
    document.body.appendChild(element);
    return element;
}

/** Call at the top of the render loop, before anything else in the frame. */
export function perfFrameStart() {
    if (!enabled) return;
    frameStart = performance.now();
    if (previousStart > 0) {
        const interval = frameStart - previousStart;
        if (interval > worstInterval) worstInterval = interval;
        if (interval > HITCH_MS) hitches++;
    }
    previousStart = frameStart;
}

/**
 * Call at the end of the render loop, immediately after render().
 *
 * After, specifically: renderer.info counts the frame just drawn and three.js
 * clears it at the start of the next render, so this is the one moment those
 * numbers are readable.
 *
 * @param {THREE.WebGLRenderer} renderer
 */
export function perfFrameEnd(renderer) {
    if (!enabled) return;
    const work = performance.now() - frameStart;
    workTotal += work;
    if (work > worstWork) worstWork = work;
    frames++;

    if (windowStart === 0) windowStart = frameStart;
    const elapsed = frameStart - windowStart;
    if (elapsed < REPORT_MS) return;

    if (readout === null) readout = makeReadout();
    const info = renderer ? renderer.info.render : {calls: 0, triangles: 0};
    // The canvas backing store IS the drawing buffer, already in device pixels,
    // so this needs no THREE import -- and notably not renderer.getSize(target),
    // which calls target.set() and so demands a real Vector2.
    const canvas = renderer ? renderer.domElement : null;

    readout.textContent = [
        `${(1000 * frames / elapsed).toFixed(1)} fps   worst ${worstInterval.toFixed(1)} ms`,
        `hitches >${HITCH_MS}ms: ${hitches}`,
        `work ${(workTotal / frames).toFixed(2)} avg / ${worstWork.toFixed(1)} worst ms`,
        `${info.calls} calls  ${(info.triangles / 1000).toFixed(0)}k tris`,
        canvas ? `buffer ${canvas.width}x${canvas.height}`
               + ` @${renderer.getPixelRatio()}x` : '',
    ].filter(Boolean).join('\n');

    (frames = 0, workTotal = 0, worstWork = 0, worstInterval = 0, hitches = 0);
    windowStart = frameStart;
}

/** Whether the readout is running, for anything that wants to know. */
export function isPerfEnabled() {
    return enabled;
}
