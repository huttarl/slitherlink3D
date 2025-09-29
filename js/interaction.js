import * as THREE from 'three';
import { DRAG_THRESHOLD_PIXELS, FACE_DEFAULT_COLOR, FACE_HIGHLIGHT_COLOR, EDGE_COLORS, EDGE_STATES } from './constants.js';

export function makeInteraction({ renderer, camera, scene, dodecahedron, geometry, grid, faceMap, faceVertexRanges, edgeMeshes, controls }) {
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let highlightedFace = null;
    let selectedEdge = null;

    // Drag detection to suppress click after orbiting
    let didDrag = false;

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
        // Was: edgeMesh.material.color = EDGE_COLORS[edge.metadata.state];

    }

    // Display info about selected edge, for debugging purposes
    // TODO: remove this debugging stuff, or make it hideable
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

    function handleEdgeClick(edgeMesh, shiftKey) {
        const reverseDirection = shiftKey;
        cycleEdgeState(edgeMesh, reverseDirection);
        showEdgeInfo(edgeMesh, reverseDirection);
        selectedEdge = edgeMesh.userData.edgeId;
    }

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
                    <strong>Adjacent Faces:</strong> ${adjacentFaces.length}
                </div>
            `;
        } else {
            infoDiv.innerHTML = '';
        }
    }

    function onMouseClick(event) {
        // Suppress click if a drag occurred just before mouseup
        // console.log('onMouseClick: didDrag = ', didDrag);
        if (didDrag) {
            didDrag = false;
            return;
        }
        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
        raycaster.setFromCamera(mouse, camera);
        const edgeIntersects = raycaster.intersectObjects(edgeMeshes);
        if (edgeIntersects.length > 0) {
            handleEdgeClick(edgeIntersects[0].object, event.shiftKey);
            return;
        }
        const faceIntersects = raycaster.intersectObject(dodecahedron);
        if (faceIntersects.length > 0) {
            const faceIndex = faceIntersects[0].faceIndex * 3;
            const faceId = faceMap.get(faceIndex);
            if (faceId !== undefined) {
                handleFaceClick(faceId);
            }
        }
    }

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

    window.addEventListener('click', onMouseClick);
    window.addEventListener('resize', onWindowResize);
    controls.addEventListener('start', onControlsStart);
    controls.addEventListener('change', onControlsChange);

    return { dispose: () => {
        window.removeEventListener('click', onMouseClick);
        window.removeEventListener('resize', onWindowResize);
        controls.removeEventListener('start', onControlsStart);
        controls.removeEventListener('change', onControlsChange);
    }};
}


