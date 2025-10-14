import { createVertexLabels } from "./textRenderer.js";
import { highlightSolution } from "./puzzleLoader.js";

/** Toggles debugging features on or off using the new GameState architecture.
 * @param {boolean} debugEnabled - Whether to enable debugging features.
 * @param {GameState} gameState - The game state containing all necessary data.
 */
export function toggleDebugFeatures(debugEnabled, gameState) {
    console.log('Debug mode:', debugEnabled ? 'ON' : 'OFF');

    // Use the GameState's built-in debug toggle functionality
    gameState.toggleDebugMode(debugEnabled);
}

/** Legacy function for backward compatibility.
 * Toggles debugging features using the old parameter approach.
 * 
 * @deprecated Use toggleDebugFeatures(debugEnabled, gameState) instead
 * @param {boolean} debugEnabled - Whether to enable debugging features.
 * @param {Grid} grid - The grid data structure to use.
 * @param {THREE.Scene} scene - The Three.js scene to add debug elements to.
 * @param {Object} puzzleData - The puzzle data object.
 * @param {THREE.Group} vertexLabels - The group containing text vertex labels.
 * @param {THREE.Mesh[]} edgeMeshes - Array of edge meshes for coloring.
 */
export function toggleDebugFeaturesLegacy(debugEnabled, grid, scene, puzzleData, vertexLabels, edgeMeshes) {
    console.log('Debug mode (legacy):', debugEnabled ? 'ON' : 'OFF');

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
