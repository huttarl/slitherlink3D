/**
 * Celebrating a solve: lights chasing round the solution loop, settling into a
 * shimmer.
 *
 * The point is that it celebrates WHAT THE PLAYER DID. They found the single
 * closed loop, so the loop is what goes on stage -- and a chase with no gap and
 * no beginning reads as the cycle they made, which no burst of confetti could.
 * See docs/celebration.md for the ideas this was chosen over.
 *
 * Three beats, all of them just colors and scales on edge meshes that already
 * exist, advanced once per frame from the render loop:
 *
 *   1. the edges NOT in the loop fade toward the ruled-out near-white, so the
 *      loop is briefly the only dark thing on the solid;
 *   2. bright heads a few edges apart chase round the loop, trailing a falloff,
 *      the edges swelling as each passes, the way a bulge runs along a hose when
 *      the pressure surges;
 *   3. they ease into a slow, low shimmer and the other edges come most of the
 *      way back, which marks the board as solved without demanding attention.
 *
 * Beats 2 and 3 are the SAME travelling wave, differing only in amplitude and
 * speed, so there is no seam between them: the phase is accumulated frame by
 * frame rather than recomputed from the elapsed time, and the amplitude eases
 * from one to the other.
 */
import * as THREE from './three/three.module.min.js';
import {CELEBRATION_COLORS, CELEBRATION_TIMING, EDGE_COLORS} from './constants.js';
import {playCelebrationTune} from './celebrationSound.js';
import {debug} from './debug.js';

/**
 * Everything the running celebration needs, or null when none is running.
 * One board per page load, so module state is right here for the same reason
 * clueRenderer keeps its material sets on the group.
 *
 * @type {?{loop: THREE.Mesh[], quieted: {mesh: THREE.Mesh, was: THREE.Color}[],
 *          heads: number, elapsed: number, phase: number, amplitude: number,
 *          dim: number}}
 */
let running = null;

/** Does the player's system ask for less motion? Read per call rather than
 *  cached: the setting can change while the page is open. */
function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * The solution loop's edge meshes, in the order the loop visits them.
 *
 * Order is the whole game here: an edge's position along the loop is what
 * decides when the light reaches it. The stored solution is a vertex cycle, so
 * consecutive pairs give the edges.
 *
 * @param {PuzzleGrid} puzzleGrid
 * @returns {THREE.Mesh[]} may be shorter than the loop if any mesh is missing
 */
function loopMeshesInOrder(puzzleGrid) {
    const loop = puzzleGrid.getCurrentPuzzle().solution;
    const meshes = [];
    for (let i = 0; i < loop.length; i++) {
        const edgeId = puzzleGrid.findEdgeByVertices(loop[i],
                                                    loop[(i + 1) % loop.length]);
        const mesh = (edgeId !== undefined && edgeId !== null)
            ? puzzleGrid.getEdgeMesh(edgeId) : null;
        if (mesh) meshes.push(mesh);
    }
    return meshes;
}

/**
 * Give a mesh its own colour object to animate.
 *
 * REQUIRED, not tidiness: applyEdgeState ASSIGNS the shared constants from
 * EDGE_COLORS to material.color, so after any state change many materials point
 * at one THREE.Color -- and at the constant itself. Mutating that would recolour
 * every edge in the same state and corrupt the palette for the rest of the page's
 * life. Returns what the colour was, so it can be restored.
 *
 * @param {THREE.Mesh} mesh
 * @returns {THREE.Color} a copy of the colour it had
 */
function takePrivateColor(mesh) {
    const was = mesh.material.color.clone();
    mesh.material.color = new THREE.Color().copy(was);
    return was;
}

/**
 * Starts the celebration, if motion is welcome.
 *
 * @param {GameState} gameState
 * @returns {boolean} true if it is animating, false if it declined -- in which
 *     case the caller should not wait before showing its dialog, since there is
 *     nothing to wait for
 */
export function startCelebration(gameState) {
    stopCelebration(gameState);     // never stack two runs
    if (prefersReducedMotion()) {
        debug('celebration: skipped, prefers-reduced-motion');
        return false;
    }

    const puzzleGrid = gameState.getPuzzleGrid();
    const loop = loopMeshesInOrder(puzzleGrid);
    if (loop.length === 0) return false;

    const inLoop = new Set(loop);
    const quieted = [];
    // getEdgeMesh, not edge.metadata.mesh: it reads the same edgeMeshMap that
    // clearEdgeHighlights walks when restoring, so the set we take private
    // colours from cannot differ from the set that gets them back.
    for (const edgeId of puzzleGrid.edges.keys()) {
        const mesh = puzzleGrid.getEdgeMesh(edgeId);
        if (mesh && !inLoop.has(mesh)) {
            quieted.push({mesh, was: takePrivateColor(mesh)});
        }
    }
    for (const mesh of loop) takePrivateColor(mesh);

    // Heads evenly spaced round the loop, about one every headSpacingEdges. It
    // has to divide the loop EXACTLY or the pattern would have a seam where it
    // met itself, so the count is rounded and the spacing follows from it rather
    // than the other way round -- which is why a 10-edge loop gets 3 heads
    // 3 1/3 edges apart rather than 3 heads and a gap.
    const heads = Math.max(1, Math.round(loop.length
                                         / CELEBRATION_TIMING.headSpacingEdges));

    running = {loop, quieted, heads, elapsed: 0, phase: 0, amplitude: 1, dim: 0};
    debug(`celebration: ${loop.length} loop edges, ${heads} heads, `
          + `${quieted.length} quieted`);
    playCelebrationTune();
    return true;
}

/** Restores the ordinary edge colours and thicknesses. Safe to call when
 *  nothing is running. */
export function stopCelebration(gameState) {
    if (!running) return;
    for (const mesh of running.loop) mesh.scale.set(1, 1, 1);
    // clearEdgeHighlights reassigns the shared EDGE_COLORS constants, which also
    // puts back the sharing that takePrivateColor broke.
    gameState.getPuzzleGrid().clearEdgeHighlights();
    running = null;
}

/**
 * How bright the light is at a point, given how far it sits BEHIND the head in
 * front of it -- measured in that head's own span, not in the whole loop, so one
 * function serves however many heads are chasing.
 *
 * A raised cosine over the trail's length: 1 at the head, 0 at the tail, with
 * zero slope at both ends so the light has no visible edge. Anything further
 * behind than the trail is dark.
 *
 * @param {number} behind - distance behind the head, in head spans [0, 1)
 * @returns {number} 0..1
 */
function trailBrightness(behind) {
    const trail = CELEBRATION_TIMING.trailFraction;
    if (behind >= trail) return 0;
    return 0.5 * (1 + Math.cos(Math.PI * behind / trail));
}

/**
 * Advances the celebration by one frame. A no-op when none is running, so the
 * render loop can call it unconditionally.
 *
 * @param {GameState} gameState
 * @param {number} delta - seconds since the last frame
 */
export function updateCelebration(gameState, delta) {
    if (!running) return;
    const timing = CELEBRATION_TIMING;
    running.elapsed += delta;
    const t = running.elapsed;

    // Beat 1 fades the other edges down; from beat 3 they come most of the way
    // back, so the solid reads normally again while the loop keeps shimmering.
    const clearing = Math.min(1, t / timing.clearSeconds);
    const pulseEnd = timing.clearSeconds + timing.pulseSeconds;
    const settling = t <= pulseEnd ? 0
        : Math.min(1, (t - pulseEnd) / timing.settleSeconds);
    running.dim = clearing * (1 - settling * (1 - timing.settleDimFraction));
    for (const {mesh, was} of running.quieted) {
        mesh.material.color.copy(was).lerp(CELEBRATION_COLORS.quiet, running.dim);
    }

    const base = EDGE_COLORS.filledIn;
    const count = running.loop.length;

    // The lights wait for beat 1 to finish, chase at the pulse's rate through
    // beat 2, then carry on at the shimmer's slower one.
    //
    // Phase counts CIRCUITS of the loop, but both rates are given in EDGES per
    // second, so dividing by the edge count is what keeps the apparent speed the
    // same on a 3-edge loop and a 131-edge one. Accumulating the phase rather than
    // deriving it from t is what makes the change of rate seamless.
    if (t >= timing.clearSeconds) {
        const edgesPerSecond = (t <= pulseEnd)
            ? timing.pulseEdgesPerSecond
            : timing.shimmerEdgesPerSecond;
        running.phase = (running.phase + delta * edgesPerSecond / count) % 1;
    }
    running.amplitude = 1 - settling * (1 - timing.shimmerAmplitude);

    for (let i = 0; i < count; i++) {
        const mesh = running.loop[i];
        // Where this edge sits behind the nearest head. Scaling the way round the
        // loop by the number of heads collapses the several evenly-spaced heads
        // into the one-head problem, since the pattern repeats every 1/heads of a
        // circuit -- so trailFraction is a fraction of ONE head's span.
        const roundTheLoop = (running.phase - i / count + 1) % 1;
        const behind = (roundTheLoop * running.heads) % 1;
        const light = running.amplitude * trailBrightness(behind);
        mesh.material.color.copy(base).lerp(CELEBRATION_COLORS.pulse, light);
        // The bulge travels with the light. Cylinders are built along their own
        // Y, which lookAt then aims down the edge, so X and Z are the thickness
        // and Y must stay 1 or the edge would grow past its vertices.
        const thickness = 1 + (timing.thickenFactor - 1) * light;
        mesh.scale.set(thickness, 1, thickness);
    }
}
