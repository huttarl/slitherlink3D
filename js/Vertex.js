/** Vertex in a polyhedron.
 * @prop {THREE.Vector3} position - 3D coordinate of vertex
 * @prop {Set<number>} edgeIDs - IDs of edges incident to vertex
 * @prop {Set<number>} faceIDs - IDs of faces incident to vertex
 * @prop {Object} metadata - additional properties...
 */
export class Vertex {
    constructor(position, edgeIDs = new Set(), faceIDs = new Set(), metadata = {}) {
        this.position = position.clone();
        this.edgeIDs = edgeIDs;
        this.faceIDs = faceIDs;
        this.metadata = metadata;
    }
}
