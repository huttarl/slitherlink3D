/** Edge in a polyhedron.
 * @prop {number[]} vertexIDs - IDs of the two vertices that make up the edge
 * @prop {Set<number>} faceIDs - IDs of faces adjacent to the edge (filled in later)
 * @prop {Object} metadata - whatever metadata we need to store
 * @prop {number} metadata.userGuess - state of user guess for the edge (0=unknown, 1=filled in, 2=ruled out)
 * @prop {number} metadata.solutionState - solution for the edge (1=filled in, 2=ruled out)
 * @prop {THREE.Mesh} metadata.mesh - the geometry mesh used to display this edge (filled in later)
 */
export class Edge {
    constructor(vertexIDs, faceIDs, metadata = {}) {
        this.vertexIDs = vertexIDs;
        this.faceIDs = faceIDs;
        this.metadata = metadata;
        this.metadata.mesh = null;
    }
}
