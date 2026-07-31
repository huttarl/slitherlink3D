/**
 * Handles user interaction with the 3D Slitherlink puzzle, including face highlighting
 * and edge state toggling.
 * @module interaction
 */

import * as THREE from './three/three.module.min.js';
import { DRAG_THRESHOLD_PIXELS, FACE_DEFAULT_COLOR, FACE_HIGHLIGHT_COLOR, EDGE_STATES } from './constants.js';

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

        // Suppress the click if the pointer moved far enough during this
        // gesture to count as a drag (i.e. a camera rotation).
        if (maxPointerMovement > DRAG_THRESHOLD_PIXELS) return;

        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
        raycaster.setFromCamera(mouse, sceneManager.camera);
        
        // Check for edge clicks first.
        const edgeIntersects = raycaster.intersectObjects(edgeMeshes);
        if (edgeIntersects.length > 0) {
            handleEdgeClick(edgeIntersects[0].object, event.shiftKey);
            return;
        }
        
        // Check for face clicks if no edge was clicked.
        const faceIntersects = raycaster.intersectObject(sceneManager.polyhedronMesh);
        if (faceIntersects.length > 0) {
            const faceIndex = faceIntersects[0].faceIndex * 3;
            const faceId = puzzleGrid.faceMap.get(faceIndex);
            if (faceId !== undefined) {
                handleFaceClick(faceId);
            }
        }
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

    /** Starts tracking a pointer gesture (mouse, touch, or pen).
     * @private
     * @param {PointerEvent} event
     */
    function onPointerDown(event) {
        pointerDownX = event.clientX;
        pointerDownY = event.clientY;
        maxPointerMovement = 0;
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
    }

    // Set up event listeners
    window.addEventListener('click', onMouseClick);
    window.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('resize', onWindowResize);

    // Return cleanup function
    return {
        // Remove all event listeners when the interaction handler is no longer needed.
        dispose: () => {
            window.removeEventListener('click', onMouseClick);
            window.removeEventListener('pointerdown', onPointerDown);
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('resize', onWindowResize);
        }
    };
}
