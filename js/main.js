import {updateTextVisibility} from './textRenderer.js';
import {createGameState} from "./scene.js";
import {setupUI} from "./ui.js";

async function main() {
    // Create the game state with all necessary objects
    const gameState = await createGameState();
    
    // Get references to scene manager for easier access
    const sceneManager = gameState.getSceneManager();
    sceneManager.setupStuff(sceneManager);

    setupUI(gameState);

    // Render loop
    function animate() {
        requestAnimationFrame(animate);

        // Update text visibility based on camera position
        updateTextVisibility(gameState);

        // OrbitControls update is required if autorotating.
        sceneManager.controls.update(sceneManager.clock.getDelta());

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
