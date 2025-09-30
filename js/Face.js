import {FACE_DEFAULT_COLOR, FACE_HIGHLIGHT_COLOR} from "./constants";

/** Face in a polyhedron.
 * // TODO rename vertices to vertexIds and edges to edgeIds
 * @prop {number[]} vertices - IDs of vertices that make up the face
 * @prop {number[]} edges - IDs of edges that make up the face
 * @prop {Object} metadata - additional properties
 * @prop {THREE.Color} metadata.originalColor - original color of the face
 * @prop {THREE.Color} metadata.highlightColor - color of the face when highlighted
 * @prop {boolean} metadata.isHighlighted - whether the face is highlighted
 * @prop {number} metadata.index - index of the face (not the same as its faceId)
 * @prop {number} metadata.clue - puzzle clue indicating how many walls should be filled in
 * @prop {number} metadata.minGuess - minimum number of walls filled in implied by user guesses
 * @prop {number} metadata.maxGuess - maximum number of walls filled in implied by user guesses
 */
class Face {
    constructor(vertices, edges, metadata = {}) {
        this.vertices = vertices;
        this.edges = edges;
        this.metadata = metadata;
    }
}
