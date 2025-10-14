import { updateTextVisibility } from './textRenderer.js';
import { CAMERA_MIN_ZOOM, CAMERA_MAX_ZOOM } from './constants.js';
import { makeInteraction } from './interaction.js';
import { createGameState } from "./scene.js";

async function main() {
    // Create the game state with all necessary objects
    const gameState = await createGameState();
    
    // Get references to scene manager and puzzle grid for easier access
    const sceneManager = gameState.getSceneManager();
    const puzzleGrid = gameState.getPuzzleGrid();

    // Set up camera
    const cameraDistance = 6;
    const camera = sceneManager.setupCamera(
        window.innerWidth / window.innerHeight, 
        cameraDistance
    );

    // Set up renderer
    const renderer = sceneManager.setupRenderer(
        document.getElementById('canvas-container'),
        window.innerWidth,
        window.innerHeight
    );

    // Set up controls
    const controls = sceneManager.setupControls({
        minDistance: CAMERA_MIN_ZOOM,
        maxDistance: CAMERA_MAX_ZOOM
    });

    // Set up interaction - pass GameState directly
    const _interaction = makeInteraction(gameState);
    gameState.setInteraction(_interaction);

    // Wire up debugging toggle
    const debugToggle = document.getElementById('debugToggle');
    debugToggle.addEventListener('change', (e) => {
        // old: toggleDebugFeatures(e.target.checked, gameState);
        gameState.toggleDebugMode(e.target.checked);
    });

    // Render loop
    function animate() {
        requestAnimationFrame(animate);

        // Update text visibility based on camera position
        const textData = gameState.getTextVisibilityData();
        updateTextVisibility(textData.clueTexts, textData.camera, textData.grid);

        // Render the scene
        gameState.render();
    }
    animate();

    // Handle window resize
    window.addEventListener('resize', () => {
        gameState.onWindowResize();
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        gameState.dispose();
    });
}

main();
