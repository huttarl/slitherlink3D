/**
 * Celebrating a solve: a pulse of light that runs once round the solution loop
 * and settles into a shimmer.
 *
 * The point is that it celebrates WHAT THE PLAYER DID. They found the single
 * closed loop, so the loop is what goes on stage -- and a head of light that
 * travels it and returns to where it began is a visual proof of the win
 * condition, which no burst of confetti could be. See docs/celebration.md for
 * the ideas this was chosen over.
 *
 * Three beats, all of them just colors and scales on edge meshes that already
 * exist, advanced once per frame from the render loop:
 *
 *   1. the edges NOT in the loop fade down, so the answer emerges;
 *   2. one bright head travels the loop, trailing a falloff, the edges bulging
 *      slightly as it passes -- a cord pulled taut;
 *   3. it eases into a slow, low shimmer and the other edges come most of the
 *      way back, which marks the board as solved without demanding attention.
 *
 * Beats 2 and 3 are the SAME travelling wave, differing only in amplitude and
 * speed, so there is no seam between them: the phase is accumulated frame by
 * frame rather than recomputed from the elapsed time, and the amplitude eases
 * from one to the other.
 */
import * as THREE from './three/three.module.min.js';
import {CELEBRATION_COLORS, CELEBRATION_TIMING, EDGE_COLORS} from './constants.js';
import {debug} from './debug.js';

/**
 * Everything the running celebration needs, or null when none is running.
 * One board per page load, so module state is right here for the same reason
 * clueRenderer keeps its material sets on the group.
 *
 * @type {?{loop: THREE.Mesh[], quieted: {mesh: THREE.Mesh, was: THREE.Color}[],
 *          elapsed: number, phase: number, amplitude: number, dim: number}}
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

    running = {loop, quieted, elapsed: 0, phase: 0, amplitude: 1, dim: 0};
    debug(`celebration: ${loop.length} loop edges, ${quieted.length} quieted`);
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
 * How bright the light is at a point on the loop, given how far that point sits
 * BEHIND the travelling head.
 *
 * A raised cosine over the trail's length: 1 at the head, 0 at the tail, with
 * zero slope at both ends so the light has no visible edge. Anything further
 * behind than the trail is dark.
 *
 * @param {number} behind - distance behind the head, in loop fractions [0, 1)
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

    // The light waits for beat 1 to finish, runs the loop exactly once during
    // beat 2, then carries on at the shimmer's slower rate. Accumulating the
    // phase rather than deriving it from t is what makes the transition seamless.
    if (t >= timing.clearSeconds) {
        running.phase += (t <= pulseEnd)
            ? delta / timing.pulseSeconds
            : delta * timing.shimmerCyclesPerSecond;
        running.phase %= 1;
    }
    running.amplitude = 1 - settling * (1 - timing.shimmerAmplitude);

    const base = EDGE_COLORS.filledIn;
    const count = running.loop.length;
    for (let i = 0; i < count; i++) {
        const mesh = running.loop[i];
        // How far this edge is behind the head, wrapped into [0, 1).
        const behind = (running.phase - i / count + 1) % 1;
        const light = running.amplitude * trailBrightness(behind);
        mesh.material.color.copy(base).lerp(CELEBRATION_COLORS.pulse, light);
        // The bulge travels with the light. Cylinders are built along their own
        // Y, which lookAt then aims down the edge, so X and Z are the thickness
        // and Y must stay 1 or the edge would grow past its vertices.
        const thickness = 1 + (timing.thickenFactor - 1) * light;
        mesh.scale.set(thickness, 1, thickness);
    }
}
