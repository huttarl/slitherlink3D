/** Graph-based topology and geometry representation for polyhedron.
 * Maintains relationships between vertices, edges, and faces.
 *
 * @prop vertices - a map of vertex IDs to Vertex objects
 * @prop edges - a map of edge IDs to Edge objects
 * @prop faces - a map of face IDs to Face objects
 * @prop nextId - the next available ID for a new vertex, edge, or face
 */
export class Grid {
    constructor() {
        this.vertices = new Map();
        this.edges = new Map();
        this.faces = new Map();
        this.nextId = 0;
    }

    /** Adds a vertex to the grid.
     * @see Vertex
     * @param {Three.Vector3} position - 3D coordinate of vertex
     * @param {Object} metadata - nothing yet?
     * @returns {number} - ID of new vertex
     */
    addVertex(position, metadata = {}) {
        const id = this.nextId++;
        // TODO: Use a Vertex class
        this.vertices.set(id, {
            position: position.clone(),
            edges: new Set(),
            faces: new Set(),
            metadata
        });
        return id;
    }

    /** Creates and adds an edge between two vertices to the grid.
     *
     * @param {number} v1Id - ID of first vertex
     * @param {number} v2Id - ID of second vertex
     * @param {Object} metadata
     * @param {number} metadata.userGuess - state of user guess for the edge (0=unknown, 1=filled in, 2=ruled out)
     * @returns {number} - ID of new edge
     * TODO: refactor this into an Edge class
     */
    addEdge(v1Id, v2Id, metadata = {}) {
        const id = this.nextId++;
        let newEdge = {
            // TODO: rename to vertexIds
            vertices: [v1Id, v2Id],
            // Faces will be populated in addFace, so edges must be added first.
            // TODO: rename to faceIds
            faces: new Set(),
            metadata
        };
        // console.log("addEdge", `${id} ${newEdge.metadata}`);
        // Add id of this edge to grid's collection of edges.
        this.edges.set(id, newEdge);
        // Add id of this edge to each vertex's collection of edges.
        this.vertices.get(v1Id).edges.add(id);
        this.vertices.get(v2Id).edges.add(id);
        return id;
    }

    /** Adds a face to the grid.
     *
     * @param vertexIds {List?} - IDs of vertices that make up the face
     * @param metadata {Object} - includes a puzzle clue
     * @returns {number} - ID of new face
     * TODO: refactor this into a Face class
     */
    addFace(vertexIds, metadata = {}) {
        const id = this.nextId++;
        const edgeIds = [];

        for (let i = 0; i < vertexIds.length; i++) {
            const v1 = vertexIds[i];
            const v2 = vertexIds[(i + 1) % vertexIds.length];

            let edgeId = null;
            for (const [eId, edge] of this.edges) {
                if ((edge.vertices[0] === v1 && edge.vertices[1] === v2) ||
                    (edge.vertices[0] === v2 && edge.vertices[1] === v1)) {
                    edgeId = eId;
                    break;
                }
            }
            if (!edgeId) {
                edgeId = this.addEdge(v1, v2);
            }
            edgeIds.push(edgeId);
            this.edges.get(edgeId).faces.add(id);
        }

        this.faces.set(id, {
            vertices: vertexIds,
            edges: edgeIds,
            metadata
        });
        for (const vId of vertexIds) {
            this.vertices.get(vId).faces.add(id);
        }
        return id;
    }

    // Gets all vertex objects for a given face as a list, without IDs.
    getFaceVertices(faceId) {
        const face = this.faces.get(faceId);
        // The face only stores vertex IDs, but the vertex data is stored in the Grid.
        return face ? face.vertices.map(vId => this.vertices.get(vId)) : [];
    }

    // Finds all faces that share an edge with the given face
    getAdjacentFaces(faceId) {
        const face = this.faces.get(faceId);
        if (!face) return [];
        const adjacent = new Set();
        for (const edgeId of face.edges) {
            const edge = this.edges.get(edgeId);
            for (const fId of edge.faces) {
                if (fId !== faceId) adjacent.add(fId);
            }
        }
        return Array.from(adjacent);
    }
}


