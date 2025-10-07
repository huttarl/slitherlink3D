/** Graph-based topology and geometry representation for polyhedron.
 * Maintains relationships between vertices, edges, and faces.
 * 
 * @class Grid
 * @property {Map<number, Vertex>} vertices - Map of vertex IDs to Vertex objects
 * @property {Map<number, Edge>} edges - Map of edge IDs to Edge objects
 * @property {Map<number, Face>} faces - Map of face IDs to Face objects
 * @property {number} nextId - The next available ID for a new vertex, edge, or face
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
     * @param {Object} metadata - Additional metadata for the vertex (none yet?)
     * @param {number} id - ID for the vertex
     */
    addVertex(position, metadata = {}, id) {
        // TODO maybe: Use a Vertex class?
        this.vertices.set(id, {
            position: position.clone(),
            edges: new Set(),
            faces: new Set(),
            metadata
        });
    }

    /** Creates and adds an edge between two vertices to the grid.
     *
     * @param {number} v1Id - ID of first vertex
     * @param {number} v2Id - ID of second vertex
     * @param {Object} metadata - Additional metadata for the edge
     * @param {number} metadata.userGuess - State of user guess for the edge (0=unknown, 1=filled in, 2=ruled out)
     * @returns {number} - ID of new edge
     * TODO: refactor this to use Edge object
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
     * @param {number[]} vertexIds - IDs of vertices that make up the face
     * @param {Object} metadata - Additional metadata for the face
     * @param {number} id - ID for the face
     * TODO maybe: refactor this to use a Face class
     */
    addFace(vertexIds, metadata = {}, id) {
        const edgeIds = [];

        for (let i = 0; i < vertexIds.length; i++) {
            const v1 = vertexIds[i];
            const v2 = vertexIds[(i + 1) % vertexIds.length];

            let edgeId = -1;
            for (const [eId, edge] of this.edges) {
                if ((edge.vertices[0] === v1 && edge.vertices[1] === v2) ||
                    (edge.vertices[0] === v2 && edge.vertices[1] === v1)) {
                    edgeId = eId;
                    // console.log(`Face ${id}: Found existing edge ${eId} for vertices ${v1}-${v2}`);
                    break;
                }
            }
            if (edgeId < 0) {
                edgeId = this.addEdge(v1, v2);
                // console.log(`Face ${id}: Created new edge ${edgeId} for vertices ${v1}-${v2}`);
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
    }

    /** Gets all vertices (objects) that form a face.
     * @param {Face} face - The face object
     * @returns {Vertex[]} Array of Vertex objects that form the face
     */
    getFaceVertices(face) {
        // const face = this.faces.get(faceId); // No longer needed.
        // The face only stores vertex IDs, but the vertex data is stored in the Grid.
        return face ? face.vertices.map(vId => this.vertices.get(vId)) : [];
    }

    /** Gets all faces that share an edge with the specified face.
     * @param {number} faceId - The ID of the face to find adjacent faces for
     * @returns {Set<number>} Set of adjacent Face IDs
     */
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
        return adjacent;
    }
}
