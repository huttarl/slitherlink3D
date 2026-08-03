/**
 * Handles user interaction with the 3D Slitherlink puzzle, including face highlighting
 * and edge state toggling.
 * @module interaction
 */

import * as THREE from './three/three.module.min.js';
import { DRAG_THRESHOLD_PIXELS, FACE_DEFAULT_COLOR, FACE_HIGHLIGHT_COLOR, EDGE_STATES,
         LONG_PRESS_MS, PICK_DEPTH_TOLERANCE } from './constants.js';

/**
 * Creates and configures interaction handlers for the 3D Slitherlink puzzle.
 * Can accept either the new GameState architecture or legacy parameters.
 * 
 * @param {Object|GameState} gameState - a GameState instance
 * @returns {{dispose: Function}} An object with a dispose method to clean up event listeners
 */
export function makeInteraction(gameState) {
    const sceneManager = gameState.getSceneManager();
    const puzzleGrid = gameState.getPuzzleGrid();

    let edgeMeshes = puzzleGrid.getAllEdgeMeshes();

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let highlightedFace = null;
    let selectedEdge = null;

    // To distinguish a click from a drag, we track how far the pointer moves
    // while the button is held: more than DRAG_THRESHOLD_PIXELS means the
    // user was rotating the camera, not picking an edge.
    //
    // We deliberately do NOT use OrbitControls' 'start'/'change' events for
    // this, as an earlier version did. Their event objects carry nothing but
    // the event type, and with damping enabled 'change' keeps firing for many
    // frames after the pointer stops (update() decays the rotation delta
    // geometrically and dispatches 'change' until the camera moves less than
    // 1e-6 per frame). A click landing during that settling tail therefore
    // looked like a drag and was silently swallowed. Pixel distance also has
    // the advantage of being independent of frame rate, zoom level, and
    // dampingFactor.
    let pointerDownX = 0, pointerDownY = 0;
    // Farthest the pointer has strayed from its starting point in this gesture.
    let maxPointerMovement = 0;

    // Long press: the touch equivalent of shift+click, which a phone can't do.
    // The pending timer, and whether it fired and already handled this gesture
    // (so the click that follows the release doesn't cycle the edge again).
    let longPressTimer = null;
    let longPressHandled = false;

    /** Updates the visual highlight state of a face.
     *
     * @private
     * @param {number} faceId - ID of the face to update
     * @param {boolean} highlight - Whether to highlight the face
     */
    function updateFaceColor(faceId, highlight) {
        const face = puzzleGrid.faces.get(faceId);
        const colors = sceneManager.geometry.attributes.color;
        const range = puzzleGrid.faceVertexRanges.get(faceId);
        const color = highlight ? FACE_HIGHLIGHT_COLOR : FACE_DEFAULT_COLOR;
        for (let i = 0; i < range.count; i++) {
            colors.setXYZ(range.start + i, color.r, color.g, color.b);
        }
        colors.needsUpdate = true;
        face.metadata.isHighlighted = highlight;
    }

    /** Cycles through possible edge states (unknown, filled, ruled out).
     *
     * @private
     * @param {THREE.Mesh} edgeMesh - The edge mesh to update
     * @param {boolean} [reverse=false] - If true, cycle in reverse order
     */
    function cycleEdgeState(edgeMesh, reverse = false) {
        const edgeId = edgeMesh.userData.edgeId;
        const edge = puzzleGrid.edges.get(edgeId);
        // Stepping backward by 1 == stepping forward by (length - 1),
        // and avoids a negative operand to %.
        const step = reverse ? EDGE_STATES.length - 1 : 1;
        const newState = (edge.metadata.userGuess + step) % EDGE_STATES.length;
        // console.log(`cycleEdgeState: userGuess = ${newState}`);
        // setEdgeState updates the mesh color and records the move for undo.
        puzzleGrid.setEdgeState(edgeId, newState);

        // Check whether new guess has resulted a need to give feedback.
        puzzleGrid.checkUserSolution(false, edgeMesh, edge);
    }

    /** Displays debug information about a clicked edge.
     *
     * @private
     * @param {THREE.Mesh} edgeMesh - The clicked edge mesh
     * @param {boolean} reverseDirection - Whether the edge was clicked in reverse direction
     * TODO make this debugging stuff hideable.
     */
    function showEdgeInfo(edgeMesh, reverseDirection) {
        const edgeId = edgeMesh.userData.edgeId;
        const edge = puzzleGrid.edges.get(edgeId);
        const infoDiv = document.getElementById('selection-info');
        const edgeColor = EDGE_STATES[edge.metadata.userGuess];
        const colorBox = `<span class="color-indicator" style="background-color: ${edgeColor};"></span>`;
        const direction = reverseDirection ? ' (reverse)' : '';
        infoDiv.innerHTML = `
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.3);">
                <strong>Edge clicked${direction}</strong><br>
                <strong>New state:</strong> ${edgeColor} ${colorBox}<br>
                <strong>Connects faces:</strong> ${edge.faceIDs.size}
            </div>
        `;
    }

    /** Handles click events on edges.
     * @private
     * @param {THREE.Mesh} edgeMesh - The clicked edge mesh
     * @param {boolean} shiftKey - Whether shift was held during the click
     */
    function handleEdgeClick(edgeMesh, shiftKey) {
        const reverseDirection = shiftKey;
        cycleEdgeState(edgeMesh, reverseDirection);
        showEdgeInfo(edgeMesh, reverseDirection);
        selectedEdge = edgeMesh.userData.edgeId;
    }

    /** Handles click events on faces.
     * @private
     * @param {number} faceId - ID of the clicked face
     */
    function handleFaceClick(faceId) {
        if (highlightedFace !== null && highlightedFace !== faceId) {
            updateFaceColor(highlightedFace, false);
        }
        const face = puzzleGrid.faces.get(faceId);
        const newHighlight = !face.metadata.isHighlighted;
        updateFaceColor(faceId, newHighlight);
        highlightedFace = newHighlight ? faceId : null;
        const infoDiv = document.getElementById('selection-info');
        if (newHighlight) {
            const adjacentFaces = puzzleGrid.getAdjacentFaces(faceId);
            infoDiv.innerHTML = `
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.3);">
                    <strong>Selected Face:</strong> #${face.metadata.index}<br>
                    <strong>Vertices:</strong> ${face.vertexIDs.length}<br>
                    <strong>Adjacent Faces:</strong> ${adjacentFaces.size}
                </div>
            `;
        } else {
            infoDiv.innerHTML = '';
        }
    }

    /** Picks whatever is under the given screen position and acts on it.
     *
     * Shared by tapping/clicking and by the long press, which differ only in
     * which way an edge's state should cycle.
     *
     * @private
     * @param {number} clientX
     * @param {number} clientY
     * @param {boolean} reverseDirection - Cycle an edge's state backwards.
     * @returns {boolean} Whether an edge was hit.
     */
    function pickAt(clientX, clientY, reverseDirection) {
        mouse.x = (clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(clientY / window.innerHeight) * 2 + 1;
        raycaster.setFromCamera(mouse, sceneManager.camera);

        // Where the ray meets the solid, which is opaque: anything beyond this
        // is hidden from the player and must not be clickable.
        //
        // This is what stops a click that misses a near edge from carrying on
        // through the solid and toggling an edge on the FAR side -- a mark the
        // player never asked for and can't even see, which is easy to do
        // because the near edges are thin and the misses are silent. The edge
        // meshes and the face mesh are separate objects, so raycasting the
        // edges alone never gave the faces a chance to block the ray: the far
        // edge wasn't winning a race, it was the only runner.
        //
        // The face mesh is DoubleSide, so this hit is the near surface.
        const faceIntersects = raycaster.intersectObject(sceneManager.polyhedronMesh);
        const surfaceDistance = faceIntersects.length > 0
            ? faceIntersects[0].distance : Infinity;

        // Nearest edge that isn't behind the surface. Hits come back sorted by
        // distance, so the first one that passes is the nearest such edge.
        const edgeHit = raycaster.intersectObjects(edgeMeshes).find(
            hit => hit.distance <= surfaceDistance + PICK_DEPTH_TOLERANCE);
        if (edgeHit) {
            handleEdgeClick(edgeHit.object, reverseDirection);
            return true;
        }

        // No edge under the pointer: treat it as a click on the face behind it.
        if (faceIntersects.length > 0) {
            const faceIndex = faceIntersects[0].faceIndex * 3;
            const faceId = puzzleGrid.faceMap.get(faceIndex);
            if (faceId !== undefined) {
                handleFaceClick(faceId);
            }
        }
        return false;
    }

    /**
     * Handles mouse click events on the canvas
     * @private
     * @param {MouseEvent} event - The mouse event
     */
    function onMouseClick(event) {
        // Only clicks on the 3D canvas pick things in the scene. Without this
        // guard, clicking a button or checkbox in the info panel would also
        // raycast, and could toggle an edge that happens to lie behind the
        // panel (visible when zoomed in).
        if (event.target !== sceneManager.renderer.domElement) return;

        // A long press already acted on this gesture; releasing still fires a
        // click, which would cycle the same edge a second time.
        if (longPressHandled) {
            longPressHandled = false;
            return;
        }

        // Suppress the click if the pointer moved far enough during this
        // gesture to count as a drag (i.e. a camera rotation).
        if (maxPointerMovement > DRAG_THRESHOLD_PIXELS) return;

        pickAt(event.clientX, event.clientY, event.shiftKey);
    }

    /**
     * Handles window resize events to update the camera aspect ratio and renderer size.
     * @private
     */
    function onWindowResize() {
        sceneManager.camera.aspect = window.innerWidth / window.innerHeight;
        sceneManager.camera.updateProjectionMatrix();
        sceneManager.renderer.setSize(window.innerWidth, window.innerHeight);
    }

    /** Cancels any pending long press. Safe to call when none is pending.
     * @private
     */
    function cancelLongPress() {
        if (longPressTimer !== null) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }

    /** Starts tracking a pointer gesture (mouse, touch, or pen).
     * @private
     * @param {PointerEvent} event
     */
    function onPointerDown(event) {
        pointerDownX = event.clientX;
        pointerDownY = event.clientY;
        maxPointerMovement = 0;
        cancelLongPress();

        // Long press is the touch stand-in for shift+click, so it's offered to
        // fingers and pens but NOT to a mouse: a mouse has a shift key, and
        // arming it there would turn any deliberately slow click into a reverse
        // cycle.
        if (event.pointerType === 'mouse') return;
        if (event.target !== sceneManager.renderer.domElement) return;

        const startX = event.clientX;
        const startY = event.clientY;
        longPressTimer = setTimeout(() => {
            longPressTimer = null;
            // Holding still is a long press; wandering off is a camera drag,
            // and onPointerMove will already have cancelled us in that case.
            if (maxPointerMovement > DRAG_THRESHOLD_PIXELS) return;
            // Act now rather than on release, so the edge changes under the
            // finger while it's still down -- that IS the feedback that the
            // long press registered.
            if (pickAt(startX, startY, true)) {
                longPressHandled = true;
            }
        }, LONG_PRESS_MS);
    }

    /** Ends a pointer gesture, dropping any long press that hasn't fired yet.
     * @private
     */
    function onPointerUp() {
        cancelLongPress();
    }

    /** Tracks how far the pointer strays from where the gesture began.
     * We keep the maximum rather than just comparing the final position, so
     * that dragging away and back to the starting pixel still counts as a drag.
     * @private
     * @param {PointerEvent} event
     */
    function onPointerMove(event) {
        // Ignore plain hovering: event.buttons is 0 when no button is held
        // (and 1 while a finger is in contact, for touch).
        if (event.buttons === 0) return;
        const movement = Math.hypot(event.clientX - pointerDownX,
                                    event.clientY - pointerDownY);
        maxPointerMovement = Math.max(maxPointerMovement, movement);
        // Straying this far means the finger is rotating the camera, not
        // holding an edge, so a long press is no longer on the cards.
        if (maxPointerMovement > DRAG_THRESHOLD_PIXELS) {
            cancelLongPress();
        }
    }

    /** Suppresses the context menu on the canvas.
     *
     * On Android a long press on the canvas otherwise raises the browser's own
     * menu (and can start a text selection), which lands on top of the puzzle
     * and swallows the release. Only the canvas is affected; the info panel's
     * links and text keep their normal menu.
     *
     * @private
     * @param {Event} event
     */
    function onContextMenu(event) {
        if (event.target === sceneManager.renderer.domElement) {
            event.preventDefault();
        }
    }

    // Set up event listeners
    window.addEventListener('click', onMouseClick);
    window.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    // A gesture the browser takes over (scroll, zoom, an incoming call) ends
    // with pointercancel rather than pointerup, and would otherwise leave the
    // long-press timer armed to fire at whatever is under those coordinates.
    window.addEventListener('pointercancel', onPointerUp);
    window.addEventListener('contextmenu', onContextMenu);
    window.addEventListener('resize', onWindowResize);

    // Return cleanup function
    return {
        // Remove all event listeners when the interaction handler is no longer needed.
        dispose: () => {
            cancelLongPress();
            window.removeEventListener('click', onMouseClick);
            window.removeEventListener('pointerdown', onPointerDown);
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', onPointerUp);
            window.removeEventListener('pointercancel', onPointerUp);
            window.removeEventListener('contextmenu', onContextMenu);
            window.removeEventListener('resize', onWindowResize);
        }
    };
}
