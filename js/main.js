import {updateTextVisibility} from './clueRenderer.js';
import {createGameState} from "./scene.js";
import {setupUI} from "./ui.js";

async function main() {
    // Create the game state with all necessary objects
    const gameState = await createGameState();
    
    // Get references to scene manager for easier access
    const sceneManager = gameState.getSceneManager();
    sceneManager.setupStuff(sceneManager);

    setupUI(gameState);

    // Render loop.
    //
    // ORDER MATTERS: everything that moves the camera runs first, then the
    // clue digits are updated, then we render. The digits are oriented and
    // culled from the camera's current orientation, so computing them before
    // the camera moves leaves them a frame stale -- which shows up as the
    // digits shimmering against the faces they're painted on during a drag.
    // That was barely visible with orbit controls, which also update the camera
    // synchronously from their own pointer handler, but trackball controls do
    // all their rotation here in update(), so the lag was a full frame.
    function animate() {
        requestAnimationFrame(animate);

        // Advance the timer once per frame; consumers then read
        // getDelta()/getElapsed() (Timer separates advancing from reading,
        // unlike the old THREE.Clock).
        sceneManager.timer.update();
        const delta = sceneManager.timer.getDelta();

        // Spin the view while celebrating a solved puzzle (a no-op otherwise).
        sceneManager.updateCelebrationSpin(delta);

        // Animate the "Right side up" turn, if one is running. While it is, the
        // controls must stand down: their update() calls lookAt(), which would
        // overwrite the orientation being interpolated.
        sceneManager.updateLevelling(delta);
        if (!sceneManager.isLevelling) {
            // Required for damping/inertia in both control schemes. (Trackball
            // ignores the argument; orbit uses it.)
            sceneManager.controls.update(delta);
        }

        // Now that the camera is final for this frame, orient/cull the clues.
        updateTextVisibility(gameState);

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
