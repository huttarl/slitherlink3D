import * as THREE from 'three';

/**
 * Creates text meshes that are "painted" onto polyhedron faces
 * @param {Grid} grid - The topology containing face data
 * @returns {THREE.Group} Group containing all text meshes
 */
export function createClueTexts(grid) {
    const textGroup = new THREE.Group();
    
    // Create a canvas for text rendering
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    // Unused? const context = canvas.getContext('2d');
    
    // Create materials for each digit (0-9)
    const materials = {};
    for (let i = 0; i <= 9; i++) {
        // Create a separate canvas for each digit
        // TODO sometime: make canvas size, font size (and line width?) depend on minimum face size?
        const digitCanvas = document.createElement('canvas');
        digitCanvas.width = 256;
        digitCanvas.height = 256;
        const digitContext = digitCanvas.getContext('2d');
        
        // Clear canvas with transparent background
        digitContext.clearRect(0, 0, 256, 256);
        
        // Set text properties
        digitContext.font = 'bold 240px Arial';
        digitContext.fillStyle = 'white';
        digitContext.strokeStyle = 'black';
        digitContext.lineWidth = 4;
        digitContext.textAlign = 'center';
        digitContext.textBaseline = 'middle';
        
        // Draw text with outline
        const x = 128;
        const y = 128;
        digitContext.strokeText(i.toString(), x, y);
        digitContext.fillText(i.toString(), x, y);
        
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
                textMesh.userData = { faceId, clue };
                textGroup.add(textMesh);
            }
        }
    }
    
    return textGroup;
}

// Calculate face normal vector.
function findFaceNormal(faceVertices) {
    const v1 = faceVertices[0].position;
    const v2 = faceVertices[1].position;
    const v3 = faceVertices[2].position;
    // Compute edge vectors by subtracting one vertex from another.
    const edge1 = new THREE.Vector3().subVectors(v2, v1);
    const edge2 = new THREE.Vector3().subVectors(v3, v1);
    // Then cross edge vectors to find perpendicular vector, and normalize length.
    return new THREE.Vector3().crossVectors(edge1, edge2).normalize();
}

/**
 * Creates a text mesh positioned and oriented on a specific face
 */
function createTextMeshForFace(faceId, face, grid, material) {
    const faceVertices = grid.getFaceVertices(faceId);
    if (faceVertices.length < 3) return null;
    
    // Calculate face center and normal
    const center = new THREE.Vector3();
    for (const vertex of faceVertices) {
        center.add(vertex.position);
    }
    center.divideScalar(faceVertices.length);

    const normal = findFaceNormal(faceVertices);

    // Create plane geometry for text
    const planeGeometry = new THREE.PlaneGeometry(0.4, 0.4);
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
    
    // Combine the two rotations
    textMesh.quaternion.premultiply(rotationQuaternion);
    
    return textMesh;
}

/**
 * Updates text visibility based on camera position
 * @param {THREE.Group} textGroup - Group containing text meshes
 * @param {THREE.Camera} camera - Camera for visibility calculation
 * @param {Grid} grid - Topology for face normal calculation
 */
export function updateTextVisibility(textGroup, camera, grid) {
    const cameraPosition = camera.position;
    
    for (const mesh of textGroup.children) {
        const faceId = mesh.userData.faceId;
        const face = grid.faces.get(faceId);
        
        if (face) {
            // Calculate face normal (approximate)
            const faceVertices = grid.getFaceVertices(faceId);
            if (faceVertices.length >= 3) {
                const normal = findFaceNormal(faceVertices);

                // Vector from face center to camera
                const toCamera = new THREE.Vector3().subVectors(cameraPosition, mesh.position).normalize();
                
                // Show text if face is facing camera (dot product > 0)
                mesh.visible = normal.dot(toCamera) > 0;
            }
        }
    }
}
