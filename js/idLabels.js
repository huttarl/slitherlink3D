/**
 * Debugging ID labels: sprite-based labels showing vertex/edge/face IDs,
 * floating just outside the polyhedron. Toggled by the "Show IDs" checkbox.
 *
 * (Split out of the former textRenderer.js, whose other half -- gameplay
 * clue digits painted onto faces -- now lives in clueRenderer.js.)
 */
import * as THREE from './three/three.module.min.js';

/**
 * Creates ID labels for vertices, edges, or faces.
 * @param {GameState} gameState - contains vertex data
 * @param {Map<any, any>} items - Iterable of items to label
 * @param {function(item: any): THREE.Vector3} getLabelPosition - Function to get the position for an item
 * @param {string} [shape] - Optional shape to use for the label (default 'rect'; also 'circle' or ...)
 * @param {object} [color] - Optional color to use for the label (default {r:255, g:100, b:100, a:1})
 * @returns {THREE.Group} Group containing all label sprites
 *
 * Based on https://stemkoski.github.io/Three.js/Labeled-Geometry.html
 */
export function createIdLabels(gameState, items, getLabelPosition,
                               shape = 'rect', color= {r:255, g:100, b:100, a:1}) {
    const labelGroup = new THREE.Group();
    const thinSpace = String.fromCharCode(0x2009);
    // Cache the number format for performance.
    const numberFormat = Intl.NumberFormat(gameState.numberLocale);
    for (const [itemId, item] of items) {
        const s = numberFormat.format(itemId);
        const label = makeTextSprite(thinSpace + s + thinSpace,
            // TODO: switch makeTextSprite() from boolean circular to shape parameter
            { shape: shape, backgroundColor: color });
        // Position the label a little further from the origin than the item.
        // We rely on the fact that the vertex positions are already normalized.
        label.position.copy(getLabelPosition(item)).multiplyScalar(1.15);
        labelGroup.add(label);
    }
    return labelGroup;
}

/**
 * Create labels for vertices.
 * @param {GameState} gameState - contains vertex data
 * @returns {THREE.Group} Group containing all label sprites
 *
 * Based on https://stemkoski.github.io/Three.js/Labeled-Geometry.html
 * */
export function createVertexLabels(gameState) {
    const grid = gameState.getPuzzleGrid();
    return createIdLabels(gameState, gameState.getPuzzleGrid().vertices, (vertex) => vertex.position,
        'circle', {r:100, g:255, b:100, a:1});
}

/**
 *  Create labels for edges.
 * @param {GameState} gameState - contains edge data
 * @returns {THREE.Group} Group containing all label sprites
 *
 * Based on https://stemkoski.github.io/Three.js/Labeled-Geometry.html
 * */
export function createEdgeLabels(gameState) {
    const grid = gameState.getPuzzleGrid();
    const getEdgeCenter = function (edge) {
        const vertices = gameState.getPuzzleGrid().vertices;
        const v1p = vertices.get(edge.vertexIDs[0]).position;
        const v2p = vertices.get(edge.vertexIDs[1]).position;
        // Average the two vertex positions.
        return v1p.clone().add(v2p).multiplyScalar(0.5);
    }
    return createIdLabels(gameState, gameState.getPuzzleGrid().edges, getEdgeCenter,
        'rect', {r: 255, g: 100, b: 100, a: 1});
}

/**
 *  Create labels for faces.
 * @param {GameState} gameState - contains face data
 * @returns {THREE.Group} Group containing all label sprites
 *
 * Based on https://stemkoski.github.io/Three.js/Labeled-Geometry.html
 * */
export function createFaceLabels(gameState) {
    const grid = gameState.getPuzzleGrid();
    const getFaceCenter = function (edge) {
        // TODO implement this!
        // const vertices = gameState.getPuzzleGrid().vertices;
        // const v1p = vertices.get(edge.vertexIDs[0]).position;
        // const v2p = vertices.get(edge.vertexIDs[1]).position;
        // // Average the two vertex positions.
        // return v1p.clone().add(v2p).multiplyScalar(0.5);
        return new THREE.Vector3();
    }
    return createIdLabels(gameState, gameState.getPuzzleGrid().faces, getFaceCenter,
        'diamond', {r: 255, g: 255, b: 100, a: 1});
}

/**
 * Creates a sprite with the given message and parameters.
 * @param {string} message - The text to render onto the sprite
 * @param {object} parameters - An object containing optional parameters for the sprite
 * @param {string} [parameters.fontface=Arial] - The font face to use for the sprite
 * @param {number} [parameters.fontsize=32] - The font size to use for the sprite
 * @param {number} [parameters.borderThickness=4] - The thickness of the border around the sprite
 * @param {object} [parameters.borderColor={r:0, g:0, b:0, a:1.0}] - The color of the border around the sprite
 * @param {string} [parameters.shape='rect'] - What shape to use for the sprite
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
        parameters["fontsize"] : 32;

    var borderThickness = parameters.hasOwnProperty("borderThickness") ?
        parameters["borderThickness"] : 4;

    var borderColor = parameters.hasOwnProperty("borderColor") ?
        parameters["borderColor"] : { r:0, g:0, b:0, a:1.0 };

    var backgroundColor = parameters.hasOwnProperty("backgroundColor") ?
        parameters["backgroundColor"] : { r:255, g:255, b:255, a:1.0 };

    var shape = parameters.hasOwnProperty("shape") ?
        parameters["shape"] : 'rect';

    // create canvas, resize later.
    var canvas = document.createElement('canvas');
    var context = canvas.getContext('2d');
    context.font = "Bold " + fontsize + "px " + fontface;

    // Get size data (height depends only on font size).
    const metrics = context.measureText(message);
    const textWidth = metrics.width;

    // Calculate needed dimensions of canvas and resize.
    const imageWidth = textWidth + borderThickness * 2;
    const imageHeight = fontsize * 1.44 + borderThickness * 2;
    canvas.width = imageWidth;
    canvas.height = imageHeight;
    // new canvas, new context.
    context = canvas.getContext('2d');
    context.font = "Bold " + fontsize + "px " + fontface;

    // TODO maybe: simplify how color param is passed in and used
    // background color
    context.fillStyle   = "rgba(" + backgroundColor.r + "," + backgroundColor.g + ","
        + backgroundColor.b + "," + backgroundColor.a + ")";
    // border color
    context.strokeStyle = "rgba(" + borderColor.r + "," + borderColor.g + ","
        + borderColor.b + "," + borderColor.a + ")";

    context.lineWidth = borderThickness;
    // Extra height factor = 1.4 for descenders. We have only digits, with no descenders.
    // But 1.0, the bottom margin of the digits is too small.
    const extraHeightFactor = 1.3;
    let w = textWidth + borderThickness;
    let h = fontsize * extraHeightFactor + borderThickness;
    switch (shape) {
        case 'rect':
            roundRect(context, borderThickness / 2, borderThickness / 2, w, h, 6);
            break;
        case 'circle':
            const r = Math.max(w, h) / 2 - 2;
            context.arc(canvas.width / 2, canvas.height / 2, r, 0, 2 * Math.PI);
            context.fill();
            context.stroke();
            break;
        case 'diamond':
            // TODO: implement diamond shape
        default:
            console.error(`Unimplemented shape: ${shape}`);
    }

    // text color
    context.fillStyle = "rgba(0, 0, 0, 1.0)";

    context.fillText( message, borderThickness, fontsize + borderThickness );

    // canvas contents will be used for a texture
    const texture = new THREE.Texture(canvas);
    texture.needsUpdate = true;

    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture
        // , useScreenCoordinates: useScreenCoordinates // no longer exists
        // , alignment: spriteAlignment // no longer exists
    });
    const sprite = new THREE.Sprite(spriteMaterial);
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
 * Note that as of 2023, there is a built-in roundRect() function in Canvas.
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
