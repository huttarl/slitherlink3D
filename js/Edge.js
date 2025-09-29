/** Edge in a polyhedron.
 * @prop {number[]} vertices - IDs of the two vertices that make up the edge
 * @prop {number[]} faces - IDs of faces adjacent to the edge (may be filled in later)
 * @prop {Object} metadata - whatever metadata we need to store
 * @prop {number} metadata.userGuess - state of user guess for the edge (0=unknown, 1=filled in, 2=ruled out)
 * @prop {number} metadata.solutionState - solution for the edge (1=filled in, 2=ruled out)
 */
class Edge {
    constructor(vertices, faces, metadata = {}) {
        // TODO: rename to vertexIds and faceIds
        this.vertices = vertices;
        this.faces = faces;
        this.metadata = metadata;
    }
}
