import {createVertexLabels} from "./textRenderer.js";
import {applySolutionToGrid} from "./puzzleLoader.js";

/** Toggles debugging features on or off.
 * @param {boolean} debugEnabled - Whether to enable debugging features.
 * @param {Grid} grid - The grid data structure to use.
 * @param {THREE.Scene} scene - The Three.js scene to add debug elements to.
 * @param {Object} puzzleData - The puzzle data object.
 * @param {THREE.Group} vertexLabels - The group containing text vertex labels.
 * */
export function toggleDebugFeatures(debugEnabled, grid, scene, puzzleData, vertexLabels) {
    console.log('Debug mode:', debugEnabled ? 'ON' : 'OFF');

    if (debugEnabled) {
        // Highlight the solution.
        applySolutionToGrid(grid, puzzleData, 0);
        updateEdgeColors(grid, scene);

        // Display vertex labels.
        scene.add(vertexLabels);
    } else {
        // TODO: resetPuzzle(grid, scene); // set edge guesses back to "unknown"
        scene.remove(vertexLabels);
    }
}
