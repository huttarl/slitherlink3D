import {updateTextVisibility} from './textRenderer.js';
import {CAMERA_MAX_ZOOM, CAMERA_MIN_ZOOM} from './constants.js';
import {makeInteraction} from './interaction.js';
import {createGameState} from "./scene.js";

async function main() {
    // Create the game state with all necessary objects
    const gameState = await createGameState();
    
    // Get references to scene manager for easier access
    const sceneManager = gameState.getSceneManager();

    // Set up camera
    const cameraDistance = 6;
    sceneManager.setupCamera(
        window.innerWidth / window.innerHeight, 
        cameraDistance
    );

    // Set up renderer
    sceneManager.setupRenderer(
        document.getElementById('canvas-container'),
        window.innerWidth,
        window.innerHeight
    );

    // Set up controls
    sceneManager.setupControls({
        minDistance: CAMERA_MIN_ZOOM,
        maxDistance: CAMERA_MAX_ZOOM
    });

    // Set up interaction - pass GameState directly
    gameState.setInteraction(makeInteraction(gameState));

    // Wire up labels toggle
    const showIDsToggle = document.getElementById('showIDs');
    showIDsToggle.addEventListener('change', (e) => {
        gameState.toggleShowIDs(e.target.checked);
    });
    // Wire up solution display toggle
    const showSolutionToggle = document.getElementById('showSolution');
    showSolutionToggle.addEventListener('change', (e) => {
        gameState.toggleShowSolution(e.target.checked);
    });


    // Wire up debugging toggle
    const checkSolutionButton = document.getElementById('checkSolution');
    checkSolutionButton.addEventListener('click', () => {
        gameState.getPuzzleGrid().checkUserSolution(true);
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
