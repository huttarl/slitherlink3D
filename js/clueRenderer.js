/**
 * Gameplay clue rendering: digit textures "painted" onto polyhedron faces,
 * sized to fit each face, plus per-frame visibility culling of clues on
 * faces that point away from the camera.
 *
 * (Split out of the former textRenderer.js, whose other half -- sprite-based
 * debugging ID labels -- now lives in idLabels.js.)
 */
import * as THREE from './three/three.module.min.js';
import { findCentroid, findFaceMinRadius, findFaceNormal,
         findFaceRise } from './geometryUtils.js';
import { CLUE_COLORS, CLUE_LIFT } from './constants.js';
import { isClueSatisfied } from './solutionChecker.js';

// The largest clue any face could carry, so a full set of digit textures can be
// built up front: a clue counts a face's edges, and the biggest face in data/ is
// a decagon.
const MAX_CLUE = 12;

/**
 * One material per digit 0..MAX_CLUE, all drawn in the given color.
 *
 * Every face showing the same digit in the same state SHARES one material, so
 * these must never be recolored in place -- updateClueColors switches a mesh
 * between the two sets instead. Hence two sets, built once, rather than one set
 * whose color is tweaked per face.
 *
 * LIT, not unlit. The digits have to stay darker than the face they are painted
 * on, and that only holds if they are shaded by the same lights: the faces are
 * Phong-shaded, so one turned away from the headlight renders its near-white as
 * a middling gray -- and an UNLIT gray digit on it would come out LIGHTER than
 * its own face, exactly inverting the intended "quieter than black". Lambert
 * rather than Phong so the digit is diffuse only: a specular highlight would
 * lighten it, and a glint on a black digit is the one thing that could make a
 * clue harder to read than it already is. The digit plane sits parallel to its
 * face and a thousandth of a unit off it, so it shares the face's normal and
 * therefore its shading almost exactly. (A thousandth off a FLAT face; a bowed one
 * needs more, or it cuts through its own digit -- see createTextMeshForFace.)
 *
 * @param {THREE.Color} color - fill and outline color for the digits
 * @param {Intl.NumberFormat} numberFormat - localized digits
 * @returns {Object<number, THREE.Material>} keyed by clue value
 */
function makeDigitMaterials(color, numberFormat) {
    const materials = {};
    // The canvas takes a CSS color, so this is where a THREE.Color leaves the
    // 3D world (see CLUE_COLORS).
    const cssColor = color.getStyle();
    for (let i = 0; i <= MAX_CLUE; i++) {
        // A separate canvas per number, since each becomes its own texture.
        // TODO sometime: make canvas size, font size (and line width?) depend on minimum face size?
        const digitCanvas = document.createElement('canvas');
        digitCanvas.width = 256;
        digitCanvas.height = 256;
        const digitContext = digitCanvas.getContext('2d');

        // Clear canvas with transparent background
        digitContext.clearRect(0, 0, 256, 256);

        // Set text properties. Outline in the same color as the fill: outlining
        // a gray digit in black would put the black back and undo the graying.
        digitContext.font = 'bold 240px Arial';
        digitContext.fillStyle = cssColor; // was 'white'
        digitContext.strokeStyle = cssColor;
        digitContext.lineWidth = 4;
        digitContext.textAlign = 'center';
        digitContext.textBaseline = 'middle';

        // Draw text with outline
        const x = 128;
        const y = 128;
        const s = numberFormat.format(i);
        digitContext.strokeText(s, x, y);
        digitContext.fillText(s, x, y);

        // Create texture and material.
        //
        // colorSpace matters here and is easy to miss: a CanvasTexture defaults
        // to no color space, which means its bytes are taken as LINEAR, and the
        // renderer's sRGB output then brightens every midtone. 50% gray came out
        // near 73% -- which is why the first gray digits looked almost white.
        // Pure black and pure white are the two values the mistake doesn't
        // touch, so it went unnoticed while the digits were only ever black.
        const texture = new THREE.CanvasTexture(digitCanvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.needsUpdate = true;
        materials[i] = new THREE.MeshLambertMaterial({
            map: texture,
            transparent: true,
            alphaTest: 0.1
        });
    }
    return materials;
}

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

    // Both color sets are built now, even though a fresh board uses the gray one
    // only for its 0 clues: they're needed the moment the player fills an edge,
    // and building a texture set mid-play would stutter.
    const materials = {
        unsatisfied: makeDigitMaterials(CLUE_COLORS.unsatisfied, numberFormat),
        satisfied: makeDigitMaterials(CLUE_COLORS.satisfied, numberFormat),
    };
    // Kept on the group so updateClueColors can find them without module state,
    // which would otherwise be shared across every board of the page's lifetime.
    textGroup.userData.materials = materials;

    // Create text meshes for each face with a clue
    for (const [faceId, face] of grid.faces) {
        const clue = face.metadata.clue;
        if (clue >= 0) {
            const textMesh = createTextMeshForFace(faceId, face, grid,
                                                   materials.unsatisfied[clue]);
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
 * Recolors every clue digit: gray where the clue is satisfied, black where it
 * isn't. Call after any change to the player's edge guesses.
 *
 * Cheap enough to do wholesale rather than tracking which faces a change could
 * have affected: it is a few edge lookups per clue, on boards of at most 120
 * faces, and only on a board change rather than per frame.
 *
 * @param {GameState} gameState - holds the grid and the clue text group
 */
export function updateClueColors(gameState) {
    const clueTexts = gameState.sceneManager.clueTexts;
    // Nothing to recolor before the clue digits are built, or on a grid whose
    // puzzle has no clues at all.
    if (!clueTexts) return;

    const grid = gameState.getPuzzleGrid();
    const materials = clueTexts.userData.materials;
    for (const mesh of clueTexts.children) {
        const face = grid.faces.get(mesh.userData.faceId);
        if (!face) continue;
        const set = isClueSatisfied(grid, face) ? materials.satisfied
                                               : materials.unsatisfied;
        mesh.material = set[mesh.userData.clue];
    }
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
    const reach = findFaceMinRadius(grid, face);
    const size = Math.SQRT2 * reach;
    const planeGeometry = new THREE.PlaneGeometry(size, size);
    const textMesh = new THREE.Mesh(planeGeometry, material);

    // Lift the digit clear of the surface: past whatever the face's own curvature
    // raises above its mean plane under the digit, and then CLUE_LIFT further to
    // settle the z-fighting where the two are coincident. A flat face gives a rise
    // of 0 and so behaves exactly as before.
    //
    // Without the rise, a bowed face cuts its own digit in half -- see findFaceRise.
    // The digit's own half-diagonal is `reach`, so that is how far out the surface
    // has to be cleared, and no further; clearing the whole face would float the
    // digit above its corners for nothing.
    textMesh.position.copy(center);
    textMesh.position.addScaledVector(
        normal, findFaceRise(faceVertices, normal, reach) + CLUE_LIFT);

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
