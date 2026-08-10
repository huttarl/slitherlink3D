/**
 * Celebrating a solve: the solution loop glows, then the two sides of it take
 * different colours.
 *
 * The point is that it celebrates WHAT THE PLAYER DID, which confetti could
 * never do. They drew a closed curve on a closed surface, and the thing about a
 * closed curve on a closed surface is that it cuts it in two -- so the loop
 * lights up, and then the two pieces it made colour themselves in. See
 * docs/celebration.md for the ideas this was chosen over, including a travelling
 * chase of lights that was built and then removed.
 *
 * Four beats, advanced once per frame from the render loop:
 *
 *   1. the loop takes up an emissive glow and thickens, while the other edges
 *      fade toward the ruled-out near-white and leave it alone on the solid;
 *   2. the two regions colour in, spreading from each one's deepest interior so
 *      the colours arrive at the loop last and meet along it;
 *   3. the tumble starts, which is what shows the regions carry on round the
 *      back -- a partition of a closed surface can't be seen from one side;
 *   4. the dialog, last, since it covers the middle of the board.
 *
 * Beats 3 and 4 are the caller's (see celebrateSolved in ui.js); this module
 * owns 1 and 2 and the resting state they settle into.
 */
import * as THREE from './three/three.module.min.js';
import {CELEBRATION_COLORS, CELEBRATION_TIMING, EDGE_COLORS,
        FACE_COLORS} from './constants.js';
import {partitionFacesByLoop} from './solutionChecker.js';
import {playCelebrationTune} from './celebrationSound.js';
import {debug} from './debug.js';

/**
 * Everything the running celebration needs, or null when none is running.
 * One board per page load, so module state is right here for the same reason
 * clueRenderer keeps its material sets on the group.
 *
 * @type {?{loop: THREE.Mesh[], quieted: {mesh: THREE.Mesh, was: THREE.Color}[],
 *          faces: {faceId: number, color: THREE.Color, at: number}[],
 *          elapsed: number}}
 */
let running = null;

/** Does the player's system ask for less motion? Read per call rather than
 *  cached: the setting can change while the page is open. */
function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * The solution loop's edge meshes.
 *
 * @param {PuzzleGrid} puzzleGrid
 * @returns {THREE.Mesh[]} may be shorter than the loop if any mesh is missing
 */
function loopMeshes(puzzleGrid) {
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
 * Works out when each face takes its colour, and which colour.
 *
 * The schedule falls straight out of the flood fill that finds the regions: a
 * face's `distance` is how many faces it sits from the loop, so colouring in
 * DESCENDING distance sends a front inward-out -- starting at each region's
 * deepest interior and reaching the boundary last. Both regions' fronts arrive
 * at the loop together, and the last thing the player sees is the two colours
 * meeting along the curve they drew.
 *
 * The smaller region gets the warm colour, since warm advances and cool recedes:
 * the minority side pops instead of hiding.
 *
 * @param {PuzzleGrid} puzzleGrid
 * @returns {{faceId: number, color: THREE.Color, at: number}[]} `at` is a
 *     fraction of beat 2, 0..1
 */
function faceSchedule(puzzleGrid) {
    const {regions, distance} = partitionFacesByLoop(
        puzzleGrid, puzzleGrid.getCurrentPuzzle().solution);

    // Warm to the smaller region. Sorting by size also makes the assignment
    // deterministic, so the same puzzle always celebrates the same way.
    const ordered = [...regions].sort((a, b) => a.length - b.length);
    const colorFor = new Map();
    ordered.forEach((members, index) => {
        const color = (index === 0) ? CELEBRATION_COLORS.partitionWarm
                                    : CELEBRATION_COLORS.partitionCool;
        for (const faceId of members) colorFor.set(faceId, color);
    });

    // Deepest face first. Max over ALL faces, not per region, so the two fronts
    // share one clock and reach the loop at the same moment -- a lopsided pair of
    // regions would otherwise finish at different times.
    const deepest = Math.max(...distance.values(), 0);
    const schedule = [];
    for (const [faceId, howFar] of distance) {
        schedule.push({
            faceId,
            color: colorFor.get(faceId) || CELEBRATION_COLORS.partitionCool,
            at: deepest === 0 ? 0 : (deepest - howFar) / deepest,
        });
    }
    return schedule;
}

/**
 * Starts the celebration, if motion is welcome.
 *
 * @param {GameState} gameState
 * @returns {boolean} true if it is animating, false if it declined -- in which
 *     case the caller should not wait before its own beats, since there is
 *     nothing to wait for
 */
export function startCelebration(gameState) {
    stopCelebration(gameState);     // never stack two runs
    if (prefersReducedMotion()) {
        debug('celebration: skipped, prefers-reduced-motion');
        return false;
    }

    const puzzleGrid = gameState.getPuzzleGrid();
    const loop = loopMeshes(puzzleGrid);
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
    for (const mesh of loop) {
        takePrivateColor(mesh);
        // Emissive is per-material and starts black, so this needs no saving --
        // stopCelebration just puts it back to black.
        mesh.material.emissive = new THREE.Color().copy(CELEBRATION_COLORS.glow);
        mesh.material.emissiveIntensity = 0;
    }

    running = {loop, quieted, faces: faceSchedule(puzzleGrid), elapsed: 0,
               painted: false};
    debug(`celebration: ${loop.length} loop edges, ${quieted.length} quieted, `
          + `${running.faces.length} faces to colour`);
    playCelebrationTune();
    return true;
}

/** Restores the ordinary edge and face colours. Safe to call when nothing is
 *  running. */
export function stopCelebration(gameState) {
    if (!running) return;
    for (const mesh of running.loop) {
        mesh.scale.set(1, 1, 1);
        mesh.material.emissiveIntensity = 0;
        mesh.material.emissive = new THREE.Color(0x000000);
    }
    const puzzleGrid = gameState.getPuzzleGrid();
    for (const {faceId} of running.faces) {
        paintFace(gameState, faceId, FACE_COLORS.default);
    }
    // clearEdgeHighlights reassigns the shared EDGE_COLORS constants, which also
    // puts back the sharing that takePrivateColor broke.
    puzzleGrid.clearEdgeHighlights();
    running = null;
}

/**
 * Tints one face, through the polyhedron's vertex colours -- the same route
 * interaction.js uses for its debug highlight, since the whole solid is one
 * BufferGeometry and a face is a known run of vertices within it.
 *
 * @param {GameState} gameState
 * @param {number} faceId
 * @param {THREE.Color} color
 */
function paintFace(gameState, faceId, color) {
    const colors = gameState.sceneManager.geometry.attributes.color;
    const range = gameState.getPuzzleGrid().faceVertexRanges.get(faceId);
    if (!range) return;
    for (let i = 0; i < range.count; i++) {
        colors.setXYZ(range.start + i, color.r, color.g, color.b);
    }
    colors.needsUpdate = true;
}

/** Scratch colour for the per-face fade, reused rather than allocated per face
 *  per frame. */
const _faceTint = new THREE.Color();

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

    // Beat 1: the other edges fade back, once and for good.
    const clearing = Math.min(1, t / timing.clearSeconds);
    const dim = clearing * timing.settleDimFraction;
    for (const {mesh, was} of running.quieted) {
        mesh.material.color.copy(was).lerp(CELEBRATION_COLORS.quiet, dim);
    }

    // The loop's glow: a floor it rises to over beat 1, plus a breath that every
    // edge shares. Sharing it is the point -- brightness that varies ALONG the
    // loop reads as motion, and motion along a path this jagged reads as
    // twinkling rather than travel.
    const breath = 0.5 + 0.5 * Math.sin(
        2 * Math.PI * timing.shimmerCyclesPerSecond * t);
    const intensity = clearing * (timing.glowBase
                                  + timing.shimmerAmplitude * breath);
    const thickness = 1 + (timing.thickenFactor - 1) * clearing;
    for (const mesh of running.loop) {
        mesh.material.emissiveIntensity = intensity;
        // Cylinders are built along their own Y, which lookAt then aims down the
        // edge, so X and Z are the thickness and Y must stay 1 or the edge would
        // grow past its vertices.
        mesh.scale.set(thickness, 1, thickness);
    }

    // Beat 2: the partition spreads. Each face has its own moment in the beat and
    // its own short fade, so the front is a soft edge rather than a row of faces
    // popping on together.
    const spread = (t - timing.partitionStartSeconds) / timing.partitionSeconds;
    if (spread < 0 || running.painted) return;
    const fadeFraction = timing.faceFadeSeconds / timing.partitionSeconds;
    for (const {faceId, color, at} of running.faces) {
        const how = Math.max(0, Math.min(1, (spread - at) / fadeFraction));
        if (how <= 0) continue;
        paintFace(gameState, faceId,
                  _faceTint.copy(FACE_COLORS.default).lerp(color, how));
    }
    // The last face finishes a fade after the last one starts. Once it has, the
    // colours are final: stop touching them, or every remaining frame of the
    // shimmer would re-upload the whole solid's colour attribute for nothing.
    if (spread >= 1 + fadeFraction) running.painted = true;
}
