/** Vertex in a polyhedron.
 * @prop {THREE.Vector3} position - 3D coordinate of vertex
 * TODO rename edges to edgeIds and faces to faceIds
 * @prop {Set<number>} edges - IDs of edges incident to vertex
 * @prop {Set<number>} faces - IDs of faces incident to vertex
 * @prop {Object} metadata - additional properties...
 */
class Vertex {
    constructor(position, metadata = {}) {
        this.position = position.clone();
        this.edges = new Set();
        this.faces = new Set();
        this.metadata = metadata;
    }
}
