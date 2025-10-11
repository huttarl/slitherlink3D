/** Face in a polyhedron.
 * // TODO rename vertices to vertexIds and edges to edgeIds
 * @prop {number[]} vertexIDs - IDs of vertices that make up the face
 * @prop {number[]} edgeIDs - IDs of edges that make up the face
 * @prop {Object} metadata - additional properties
 * @prop {THREE.Color} metadata.originalColor - original color of the face
 * @prop {THREE.Color} metadata.highlightColor - color of the face when highlighted
 * @prop {boolean} metadata.isHighlighted - whether the face is highlighted
 * // TODO do we use metadata.index? do we need it? do we populate it?
 * @prop {number} metadata.index - index of the face (not the same as its faceId)
 * @prop {number} metadata.clue - puzzle clue indicating how many walls should be filled in
 * @prop {number} metadata.minGuess - minimum number of walls filled in implied by user guesses
 * @prop {number} metadata.maxGuess - maximum number of walls filled in implied by user guesses
 */
export class Face {
    constructor(vertexIDs, edgeIDs, metadata = {}) {
        this.vertexIDs = vertexIDs;
        this.edgeIDs = edgeIDs;
        this.metadata = metadata;
    }
}
