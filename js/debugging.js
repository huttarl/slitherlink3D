import {createVertexLabels} from "./textRenderer.js";
import {highlightSolution} from "./puzzleLoader.js";

/** Toggles debugging features on or off.
 * @param {boolean} debugEnabled - Whether to enable debugging features.
 * @param {Grid} grid - The grid data structure to use.
 * @param {THREE.Scene} scene - The Three.js scene to add debug elements to.
 * @param {Object} puzzleData - The puzzle data object.
 * @param {THREE.Group} vertexLabels - The group containing text vertex labels.
 * @param {THREE.Mesh[]} edgeMeshes - Array of edge meshes for coloring.
 * */
export function toggleDebugFeatures(debugEnabled, grid, scene, puzzleData, vertexLabels, edgeMeshes) {
    console.log('Debug mode:', debugEnabled ? 'ON' : 'OFF');

    if (debugEnabled) {
        // Highlight the solution.
        highlightSolution(grid, puzzleData, 0, edgeMeshes);

        // Display vertex labels.
        scene.add(vertexLabels);
    } else {
        // TODO: resetPuzzle(grid, scene); // set edge guesses back to "unknown"
        scene.remove(vertexLabels);
    }
}
