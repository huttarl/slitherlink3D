import {updateTextVisibility} from './clueRenderer.js';
import {updateCelebration} from './celebration.js';
import {createGameState} from "./scene.js";
import {setupUI} from "./ui.js";
import {expandDrawer, initPanelLayout} from "./panelLayout.js";
import {initTitleScreen, openHowToPlay, titleScreenCameraDistance,
        wantsTitleScreen} from "./titleScreen.js";
import {CAMERA_DISTANCE, CAMERA_INTRO_FACTOR} from "./constants.js";

async function main() {
    // Get the panel into its right shape before anything slow: loading the grid
    // and puzzle takes long enough that a phone would otherwise sit there
    // showing the full panel, then snap to the strip once the board appeared.
    // (main.html's inline script has already set the collapsed class, before the
    // first paint; this moves the strip's buttons and wires the toggle.)
    initPanelLayout();

    // A cold launch is a title screen: the panel is already hidden and the
    // title already up (main.html's inline script did both before the first
    // paint), so this only has to wire the two buttons. Both of them navigate,
    // which is why there's no "leave the title screen" path to build.
    const titleScreen = wantsTitleScreen();
    if (titleScreen) initTitleScreen();

    // Create the game state with all necessary objects
    const gameState = await createGameState();

    // Get references to scene manager for easier access
    const sceneManager = gameState.getSceneManager();
    // The title screen sits closer in: its solid is there to be admired, not
    // played, and filling the frame keeps it from hiding behind the title box.
    sceneManager.setupStuff(titleScreen
        ? titleScreenCameraDistance(window.innerWidth / window.innerHeight)
        : CAMERA_DISTANCE);

    setupUI(gameState);

    // Arriving from the title screen's "How to Play": open the instructions.
    if (!titleScreen) openHowToPlay(expandDrawer);

    // Tumble from the moment the puzzle appears: it shows the player that the
    // solid turns, and which sides it has, before they've touched anything. The
    // first press on the board stops it (see onPointerDown in interaction.js),
    // so it costs nothing once they start playing.
    sceneManager.startTumble();

    // And close in on the board as it appears, so the solid arrives rather than
    // simply being there. Not on the title screen, which has its own framing:
    // already closer in, and chosen to fit the window. (Whether motion is welcome
    // at all is startIntroZoom's own business, as it is startTumble's.)
    if (!titleScreen) {
        sceneManager.startIntroZoom(CAMERA_DISTANCE * CAMERA_INTRO_FACTOR,
                                    CAMERA_DISTANCE);
    }

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

        // Animate the "Right side up" turn, if one is running. While it is, the
        // controls must stand down: their update() calls lookAt(), which would
        // overwrite the orientation being interpolated.
        sceneManager.updateLevelling(delta);
        if (!sceneManager.isLevelling) {
            // Required for damping/inertia in both control schemes. (Trackball
            // ignores the argument; orbit uses it.)
            sceneManager.controls.update(delta);
        }

        // Tumble the view, if something has asked for it (a no-op otherwise).
        // Solving a puzzle is one such caller; the tumble itself is general.
        //
        // AFTER the controls, deliberately: TrackballControls.update() ends by
        // recomputing the position from its own state and calling
        // lookAt(target), so anything that moved the camera earlier in the frame
        // is simply overwritten. It has no `enabled` check either -- that guard
        // is only in its event handlers -- so switching the controls off cannot
        // hold it back. Going last is what makes the tumble stick, and it still
        // leaves the controls' zoom in effect, since the tumble takes the
        // camera's current distance as given.
        sceneManager.updateTumble(delta);

        // The opening zoom, if one is running (a no-op otherwise). AFTER the
        // tumble for the same reason the tumble comes after the controls: the
        // tumble rebuilds the camera's position from its orientation at whatever
        // radius it finds, so a distance set before it would be discarded. It only
        // touches the distance, leaving the tumble's orientation alone.
        sceneManager.updateIntroZoom(delta);

        // The solve celebration, if one is running (a no-op otherwise). Before
        // the render and independent of the camera: it only recolours and
        // rescales edge meshes.
        updateCelebration(gameState, delta);

        // Now that the camera is final for this frame, orient/cull the clues
        // and move the headlight to where the camera ended up.
        updateTextVisibility(gameState);
        sceneManager.updateHeadlight();

        // Render the scene
        gameState.render();
    }
    // Start the clock HERE, immediately before the first frame, and not a moment
    // earlier. Timer measures each delta from the previous update() -- or, until
    // there has been one, from its last reset() -- so whatever gap it is left
    // straddling arrives as the first frame's delta. Everything above this line is
    // in that gap: two JSON fetches, the geometry, the edge cylinders, the clue
    // sprites. Loading is not elapsed animation time, and handing it to the render
    // loop as though it were made the opening zoom fail on slow devices while
    // working on fast ones -- a phone spent its whole 1.2s of zoom before painting
    // anything, so the board simply appeared at its resting distance. The tumble
    // never showed the bug: it has no end to arrive at early, so one big first step
    // only turned the solid a little further before carrying on.
    //
    // The solve time is unaffected. reset() does not zero the elapsed count, but
    // nothing has accumulated yet: elapsed only advances through the update() below,
    // and only while the tab is visible.
    sceneManager.timer.reset();

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
