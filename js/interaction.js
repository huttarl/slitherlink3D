/**
 * Handles user interaction with the 3D Slitherlink puzzle, including face highlighting
 * and edge state toggling.
 * @module interaction
 */

import * as THREE from 'three';
import { DRAG_THRESHOLD_PIXELS, FACE_DEFAULT_COLOR, FACE_HIGHLIGHT_COLOR, EDGE_COLORS, EDGE_STATES } from './constants.js';

/**
 * Creates and configures interaction handlers for the 3D Slitherlink puzzle.
 * @param {Object} params - Configuration parameters
 * @param {THREE.WebGLRenderer} params.renderer - The WebGL renderer
 * @param {THREE.PerspectiveCamera} params.camera - The camera used for rendering
 * @param {THREE.Scene} params.scene - The main scene containing all 3D objects
 * @param {THREE.Mesh} params.polyhedronMesh - The main puzzle mesh
 * @param {THREE.BufferGeometry} params.geometry - The geometry of the puzzle
 * @param {Grid} params.grid - The grid data structure containing puzzle state
 * @param {Map} params.faceMap - Mapping of geometry index buffer vertex indices to face IDs, for picking
 * @param {Map} params.faceVertexRanges - Mapping of face IDs to vertex ranges in the geometry index buffer, for changing color
 * @param {THREE.Mesh[]} params.edgeMeshes - Array of meshes representing edges
 * @param {THREE.OrbitControls} params.controls - Camera controls for the scene
 * @returns {{dispose: Function}} An object with a dispose method to clean up event listeners
 */
export function makeInteraction({ renderer, camera, scene, polyhedronMesh, geometry, grid, faceMap, faceVertexRanges, edgeMeshes, controls }) {
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let highlightedFace = null;
    let selectedEdge = null;

    // Track if user is dragging, to distinguish from clicks.
    let didDrag = false;

    /**
     * Updates the visual highlight state of a face
     * @private
     * @param {number} faceId - ID of the face to update
     * @param {boolean} highlight - Whether to highlight the face
     */
    function updateFaceColor(faceId, highlight) {
        const face = grid.faces.get(faceId);
        const colors = geometry.attributes.color;
        const range = faceVertexRanges.get(faceId);
        const color = highlight ? FACE_HIGHLIGHT_COLOR : FACE_DEFAULT_COLOR;
        for (let i = 0; i < range.count; i++) {
            colors.setXYZ(range.start + i, color.r, color.g, color.b);
        }
        colors.needsUpdate = true;
        face.metadata.isHighlighted = highlight;
    }

    /**
     * Cycles through possible edge states (unknown, filled, ruled out)
     * @private
     * @param {THREE.Mesh} edgeMesh - The edge mesh to update
     * @param {boolean} [reverse=false] - If true, cycle in reverse order
     */
    function cycleEdgeState(edgeMesh, reverse = false) {
        const edgeId = edgeMesh.userData.edgeId;
        const edge = grid.edges.get(edgeId);
        if (reverse) {
            edge.metadata.userGuess = (edge.metadata.userGuess - 1 + EDGE_STATES.length) % EDGE_STATES.length;
        } else {
            edge.metadata.userGuess = (edge.metadata.userGuess + 1) % EDGE_STATES.length;
        }
        console.log(`cycleEdgeState: userGuess = ${edge.metadata.userGuess}`);
        const stateName = EDGE_STATES[edge.metadata.userGuess];
        edgeMesh.material.color = EDGE_COLORS[stateName];
    }

    /**
     * Displays debug information about a clicked edge
     * @private
     * @param {THREE.Mesh} edgeMesh - The clicked edge mesh
     * @param {boolean} reverseDirection - Whether the edge was clicked in reverse direction
     * TODO make this debugging stuff hideable.
     */
    function showEdgeInfo(edgeMesh, reverseDirection) {
        const edgeId = edgeMesh.userData.edgeId;
        const edge = grid.edges.get(edgeId);
        const infoDiv = document.getElementById('selection-info');
        const edgeColor = EDGE_STATES[edge.metadata.userGuess];
        const colorBox = `<span class="color-indicator" style="background-color: ${edgeColor};"></span>`;
        const direction = reverseDirection ? ' (reverse)' : '';
        infoDiv.innerHTML = `
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.3);">
                <strong>Edge clicked${direction}</strong><br>
                <strong>New state:</strong> ${edgeColor} ${colorBox}<br>
                <strong>Connects faces:</strong> ${edge.faces.size}
            </div>
        `;
    }

    /**
     * Handles click events on edges
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

    /**
     * Handles click events on faces
     * @private
     * @param {number} faceId - ID of the clicked face
     */
    function handleFaceClick(faceId) {
        if (highlightedFace !== null && highlightedFace !== faceId) {
            updateFaceColor(highlightedFace, false);
        }
        const face = grid.faces.get(faceId);
        const newHighlight = !face.metadata.isHighlighted;
        updateFaceColor(faceId, newHighlight);
        highlightedFace = newHighlight ? faceId : null;
        const infoDiv = document.getElementById('selection-info');
        if (newHighlight) {
            const adjacentFaces = grid.getAdjacentFaces(faceId);
            infoDiv.innerHTML = `
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.3);">
                    <strong>Selected Face:</strong> #${face.metadata.index}<br>
                    <strong>Vertices:</strong> ${face.vertices.length}<br>
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
        // Suppress click if a drag occurred just before mouseup
        if (didDrag) {
            didDrag = false;
            return;
        }
        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
        raycaster.setFromCamera(mouse, camera);
        
        // Check for edge clicks first.
        const edgeIntersects = raycaster.intersectObjects(edgeMeshes);
        if (edgeIntersects.length > 0) {
            handleEdgeClick(edgeIntersects[0].object, event.shiftKey);
            return;
        }
        
        // Check for face clicks if no edge was clicked.
        const faceIntersects = raycaster.intersectObject(polyhedronMesh);
        if (faceIntersects.length > 0) {
            const faceIndex = faceIntersects[0].faceIndex * 3;
            const faceId = faceMap.get(faceIndex);
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
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }

    // Use OrbitControls events to detect dragging
    function onControlsStart() {
        didDrag = false;
    }

    function onControlsChange() {
        didDrag = true;
    }

    // Set up event listeners
    window.addEventListener('click', onMouseClick);
    window.addEventListener('resize', onWindowResize);
    controls.addEventListener('start', onControlsStart);
    controls.addEventListener('change', onControlsChange);

    // Return cleanup function
    return {
        // Remove all event listeners when the interaction handler is no longer needed.
        dispose: () => {
            window.removeEventListener('click', onMouseClick);
            window.removeEventListener('resize', onWindowResize);
            controls.removeEventListener('start', onControlsStart);
            controls.removeEventListener('change', onControlsChange);
        }
    };
}
