import * as THREE from 'three';

/** Create labels for vertices.
 * @param {Grid} grid - The grid containing vertex data
 * @returns {THREE.Group} Group containing all label sprites
 * */
export function createVertexLabels(grid) {
    // Thanks to https://stemkoski.github.io/Three.js/Labeled-Geometry.html
    const labelGroup = new THREE.Group();
    for (const [vertexId, vertex] of grid.vertices) {
        var label = makeTextSprite( " " + vertexId + " ",
            { fontsize: 32, backgroundColor: {r:255, g:100, b:100, a:1} } );
        label.position.copy(vertex.position).multiplyScalar(1.1);
        labelGroup.add(label);
    }
    return labelGroup;
}

/**
 * Creates a sprite with the given message and parameters.
 * @param {string} message - The text to render onto the sprite
 * @param {object} parameters - An object containing optional parameters for the sprite
 * @param {string} [parameters.fontface=Arial] - The font face to use for the sprite
 * @param {number} [parameters.fontsize=18] - The font size to use for the sprite
 * @param {number} [parameters.borderThickness=4] - The thickness of the border around the sprite
 * @param {object} [parameters.borderColor={r:0, g:0, b:0, a:1.0}] - The color of the border around the sprite
 * @param {object} [parameters.backgroundColor={r:255, g:255, b:255, a:1.0}] - The background color of the sprite
 * @returns {THREE.Sprite} The sprite created with the given message and parameters
 */
function makeTextSprite(message, parameters)
{
    // Thanks to https://stemkoski.github.io/Three.js/Labeled-Geometry.html
    if ( parameters === undefined ) parameters = {};

    var fontface = parameters.hasOwnProperty("fontface") ?
        parameters["fontface"] : "Arial";

    var fontsize = parameters.hasOwnProperty("fontsize") ?
        parameters["fontsize"] : 18;

    var borderThickness = parameters.hasOwnProperty("borderThickness") ?
        parameters["borderThickness"] : 4;

    var borderColor = parameters.hasOwnProperty("borderColor") ?
        parameters["borderColor"] : { r:0, g:0, b:0, a:1.0 };

    var backgroundColor = parameters.hasOwnProperty("backgroundColor") ?
        parameters["backgroundColor"] : { r:255, g:255, b:255, a:1.0 };

    // No longer supported in THREE.js:
    // var useScreenCoordinates = parameters.hasOwnProperty("useScreenCoordinates") ?
    //     parameters["useScreenCoordinates"] : false;
    // var spriteAlignment = parameters.hasOwnProperty("spriteAlignment") ?
    //     parameters["spriteAlignment"] : THREE.SpriteAlignment.topLeft;

    // create canvas, resize later.
    var canvas = document.createElement('canvas');
    var context = canvas.getContext('2d');
    context.font = "Bold " + fontsize + "px " + fontface;

    // get size data (height depends only on font size)
    var metrics = context.measureText( message );
    var textWidth = metrics.width;

    // calculate correct dimensions of canvas and resize
    var imageWidth = textWidth + borderThickness * 2;
    var imageHeight = fontsize * 1.44 + borderThickness * 2;
    canvas.width = imageWidth;
    canvas.height = imageHeight;
    // new canvas, new context.
    context = canvas.getContext('2d');
    context.font = "Bold " + fontsize + "px " + fontface;

    // background color
    context.fillStyle   = "rgba(" + backgroundColor.r + "," + backgroundColor.g + ","
        + backgroundColor.b + "," + backgroundColor.a + ")";
    // border color
    context.strokeStyle = "rgba(" + borderColor.r + "," + borderColor.g + ","
        + borderColor.b + "," + borderColor.a + ")";

    context.lineWidth = borderThickness;
    roundRect(context, borderThickness/2, borderThickness/2, textWidth + borderThickness, fontsize * 1.4 + borderThickness, 6);
    // 1.4 is extra height factor for text below baseline: g,j,p,q.

    // text color
    context.fillStyle = "rgba(0, 0, 0, 1.0)";

    context.fillText( message, borderThickness, fontsize + borderThickness );

    // canvas contents will be used for a texture
    var texture = new THREE.Texture(canvas)
    texture.needsUpdate = true;

    var spriteMaterial = new THREE.SpriteMaterial({
        map: texture
        // , useScreenCoordinates: useScreenCoordinates // no longer exists
        // , alignment: spriteAlignment // no longer exists
        });
    var sprite = new THREE.Sprite( spriteMaterial );
    // Was: sprite.scale.set(imageWidth, imageHeight, 1.0);
    sprite.scale.set(0.15, 0.15, 1.0);
    sprite.width = imageWidth;
    sprite.height = imageHeight;
    return sprite;
}

/** Draw a rounded rectangle.
 *
 * @param ctx - context in which to draw
 * @param x, y - lower? left corner of rectangle
 * @param w, h - width and height of rectangle
 * @param r - radius of rounded corners
 */
function roundRect(ctx, x, y, w, h, r)
{
    ctx.beginPath();
    ctx.moveTo(x+r, y);
    ctx.lineTo(x+w-r, y);
    ctx.quadraticCurveTo(x+w, y, x+w, y+r);
    ctx.lineTo(x+w, y+h-r);
    ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
    ctx.lineTo(x+r, y+h);
    ctx.quadraticCurveTo(x, y+h, x, y+h-r);
    ctx.lineTo(x, y+r);
    ctx.quadraticCurveTo(x, y, x+r, y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
}

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
        digitContext.fillStyle = 'black'; // was 'white'
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

/** Calculate face normal vector.
 *
 * @param { Vertex[] } faceVertices
 * @returns { THREE.Vector3 } unit normal vector.
 */
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
            const faceVertices = grid.getFaceVertices(face);
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
