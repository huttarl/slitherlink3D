/**
 * Gameplay clue rendering: digit textures "painted" onto polyhedron faces,
 * sized to fit each face, plus per-frame visibility culling of clues on
 * faces that point away from the camera.
 *
 * (Split out of the former textRenderer.js, whose other half -- sprite-based
 * debugging ID labels -- now lives in idLabels.js.)
 */
import * as THREE from './three/three.module.min.js';
import { findCentroid, findFaceMinRadius, findFaceNormal } from './geometryUtils.js';

/**
 * Creates text meshes that are "painted" onto polyhedron faces
 * @param {GameState} gameState - The topology containing face data
 * @returns {THREE.Group} Group containing all text meshes
 */
export function createClueTexts(gameState) {
    const grid = gameState.getPuzzleGrid();
    const textGroup = new THREE.Group();

    // Cache the number format for performance.
    const numberFormat = Intl.NumberFormat(gameState.numberLocale);

    // Create a canvas for text rendering
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;

    // Create materials for numbers 0-12
    const maxClue = 12
    const materials = {};

    for (let i = 0; i <= maxClue; i++) {
        // Create a separate canvas for each number
        // TODO sometime: make canvas size, font size (and line width?) depend on minimum face size?
        const digitCanvas = document.createElement('canvas');
        digitCanvas.width = 256;
        digitCanvas.height = 256;
        const digitContext = digitCanvas.getContext('2d');

        // Clear canvas with transparent background
        digitContext.clearRect(0, 0, 256, 256);

        // Set text properties
        digitContext.font = 'bold 240px Arial';
        digitContext.fillStyle = 'black'; // was 'white'
        digitContext.strokeStyle = 'black';
        digitContext.lineWidth = 4;
        digitContext.textAlign = 'center';
        digitContext.textBaseline = 'middle';

        // Draw text with outline
        const x = 128;
        const y = 128;
        const s = numberFormat.format(i);
        digitContext.strokeText(s, x, y);
        digitContext.fillText(s, x, y);

        // Create texture and material
        const texture = new THREE.CanvasTexture(digitCanvas);
        texture.needsUpdate = true;
        materials[i] = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            alphaTest: 0.1
        });
    }

    // Create text meshes for each face with a clue
    for (const [faceId, face] of grid.faces) {
        const clue = face.metadata.clue;
        if (clue >= 0) {
            const textMesh = createTextMeshForFace(faceId, face, grid, materials[clue]);
            if (textMesh) {
                // Add to, rather than replace, the userData that
                // createTextMeshForFace already filled in (the face normal).
                textMesh.userData.faceId = faceId;
                textMesh.userData.clue = clue;
                textGroup.add(textMesh);
            }
        }
    }

    return textGroup;
}

/**
 * Creates a text mesh positioned and oriented on a specific face
 *
 * @param {number} faceId - ID of the face to create text for
 * @param {Face} face - The face to create text for
 * @param {Grid} grid - The topology containing face data
 * @param {THREE.Material} material - The material to use for the text mesh
 * @returns {THREE.Mesh | null} The created text mesh, or null on failure.
 */
function createTextMeshForFace(faceId, face, grid, material) {
    const faceVertices = grid.getFaceVertices(face);
    if (faceVertices.length < 3) return null;

    // Calculate face center and normal
    const center = findCentroid(faceVertices);
    const normal = findFaceNormal(faceVertices);

    // Create plane geometry for text, sized to the face: a square of side
    // s fits in a circle of radius r when s = r*sqrt(2), and the digit
    // glyph fills only ~70% of its canvas, so this keeps the digit inside
    // the face's inscribed circle (and thus off the edges) even on small faces.
    const size = Math.SQRT2 * findFaceMinRadius(grid, face);
    const planeGeometry = new THREE.PlaneGeometry(size, size);
    const textMesh = new THREE.Mesh(planeGeometry, material);

    // Position the mesh slightly above the face center
    textMesh.position.copy(center);
    textMesh.position.addScaledVector(normal, 0.001); // Slightly offset to avoid z-fighting

    // Orient the mesh to be parallel to the face
    // First, create a quaternion that aligns the plane's normal (0,0,1) with the face normal
    const planeNormal = new THREE.Vector3(0, 0, 1); // Plane's default normal (pointing toward camera)
    const faceNormal = normal.clone();

    // Create quaternion to align plane normal with face normal
    const quaternion = new THREE.Quaternion();
    quaternion.setFromUnitVectors(planeNormal, faceNormal);
    textMesh.quaternion.copy(quaternion);

    // Now rotate around the face normal to keep text "right-side-up" relative to world
    // Find the direction on the face that's closest to world up
    const worldUp = new THREE.Vector3(0, 1, 0);
    const faceUp = new THREE.Vector3().copy(worldUp);
    faceUp.projectOnPlane(faceNormal).normalize();

    // If the projection is too small (face is nearly horizontal), use world right instead
    if (faceUp.length() < 0.1) {
        const worldRight = new THREE.Vector3(1, 0, 0);
        faceUp.copy(worldRight).projectOnPlane(faceNormal).normalize();
    }

    // After the first rotation, the text's "up" direction (0,1,0) is now pointing
    // in some direction on the face. We need to find what direction that is.
    const textUpAfterFirstRotation = new THREE.Vector3(0, 1, 0);
    textUpAfterFirstRotation.applyQuaternion(quaternion);

    // Project this onto the face plane to get the actual direction
    textUpAfterFirstRotation.projectOnPlane(faceNormal).normalize();

    // Calculate the angle between the desired face up and the current text up
    const dot = faceUp.dot(textUpAfterFirstRotation);
    const cross = new THREE.Vector3().crossVectors(textUpAfterFirstRotation, faceUp);
    const rotationAngle = Math.atan2(cross.dot(faceNormal), dot);

    // Apply rotation around the face normal
    const rotationQuaternion = new THREE.Quaternion();
    rotationQuaternion.setFromAxisAngle(faceNormal, rotationAngle);

    // Combine the two rotations. (This initial roll is superseded every frame
    // by updateTextVisibility, which rolls the digit to suit the camera; it's
    // kept so a mesh is sensibly oriented the moment it's created.)
    textMesh.quaternion.premultiply(rotationQuaternion);

    // Cache the face normal for updateTextVisibility: it needs one per clue
    // per frame, and a face's normal never changes.
    textMesh.userData.normal = normal;

    return textMesh;
}

// Scratch objects reused by updateTextVisibility. It runs once per clue per
// frame, so allocating these inside the loop would be pure garbage.
const _cameraUp = new THREE.Vector3();
const _toCamera = new THREE.Vector3();
const _digitUp = new THREE.Vector3();
const _digitRight = new THREE.Vector3();
const _digitBasis = new THREE.Matrix4();

/**
 * Per-frame update of the clue digits: hides those on faces turned away from
 * the camera, and rolls the visible ones within their own face plane so they
 * read right-side-up from wherever the camera is now.
 *
 * Rolling here rather than once at creation keeps the digits legible however
 * the polyhedron is turned. Orienting them to world up (as creation does)
 * only works near the equator: on a face that is nearly horizontal, world up
 * barely projects into the face plane at all, so those digits end up rotated
 * more or less arbitrarily.
 *
 * Cost: this only writes each mesh's quaternion. No geometry, material or
 * texture is created or modified, and THREE recomputes every object's world
 * matrix each frame regardless, so the work is a little vector math per
 * visible clue -- less than the previous version, which recomputed every
 * face's normal from its vertices on every frame.
 *
 * @param {GameState} gameState - contains needed state
 */
export function updateTextVisibility(gameState) {
    const clueTexts = gameState.sceneManager.clueTexts;
    const camera = gameState.sceneManager.camera;

    // The camera's world Y axis is what actually appears "up" on screen.
    // (camera.up is only the hint handed to lookAt, and some control schemes
    // rewrite it, so read the resulting orientation instead.)
    _cameraUp.setFromMatrixColumn(camera.matrixWorld, 1);

    for (const mesh of clueTexts.children) {
        // Cached at creation; faces never move.
        const normal = mesh.userData.normal;
        if (!normal) continue;

        // Show the clue only while its face is turned toward the camera.
        // (No need to normalize: only the sign of the dot product matters.)
        _toCamera.subVectors(camera.position, mesh.position);
        mesh.visible = normal.dot(_toCamera) > 0;
        if (!mesh.visible) continue;

        // The digit's up direction is screen-up flattened into the face plane.
        _digitUp.copy(_cameraUp).projectOnPlane(normal);
        // Degenerate only when screen-up is perpendicular to the face plane,
        // which means the face is edge-on and about to be culled anyway. Keep
        // the previous roll instead of snapping to an arbitrary direction.
        if (_digitUp.lengthSq() < 1e-8) continue;
        _digitUp.normalize();

        // A PlaneGeometry faces +Z with +Y up, so the basis columns are
        // (X, Y, Z) = (up x normal, up, normal) -- right-handed, so the digit
        // is rotated, never mirrored.
        _digitRight.crossVectors(_digitUp, normal);
        _digitBasis.makeBasis(_digitRight, _digitUp, normal);
        mesh.quaternion.setFromRotationMatrix(_digitBasis);
    }
}
