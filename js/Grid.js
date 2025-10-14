import {Face} from "./Face.js";
import {Vertex} from "./Vertex.js";
import {Edge} from "./Edge.js";

/** Graph-based topology and geometry representation for polyhedron.
 * Maintains relationships between vertices, edges, and faces.
 * 
 * @class Grid
 * @property {Map<number, Vertex>} vertices - Map of vertex IDs to Vertex objects
 * @property {Map<number, Edge>} edges - Map of edge IDs to Edge objects
 * @property {Map<number, Face>} faces - Map of face IDs to Face objects
 * @property {Map<number, number>} vertexPairToEdge - Map from vertex pair hash to edge ID for fast lookup
 * @property {number} nextId - The next available ID for a new object
 */
export class Grid {
    constructor() {
        this.vertices = new Map();
        this.edges = new Map();
        this.faces = new Map();
        this.vertexPairToEdge = new Map();
        this.nextId = 0;
    }

    /** Adds a vertex to the grid.
     * @see Vertex
     * @param {Three.Vector3} position - 3D coordinate of vertex
     * @param {Object} metadata - Additional metadata for the vertex (none yet?)
     * @param {number} id - ID for the vertex
     */
    addVertex(position, metadata = {}, id) {
        let vertex = new Vertex(position.clone(), new Set(), new Set(), metadata);
        this.vertices.set(id, vertex);
    }

    /**
     * Creates a hash key from two vertex IDs for fast edge lookup.
     * Always uses the smaller ID first to ensure consistent ordering.
     * 
     * @param {number} v1Id - First vertex ID
     * @param {number} v2Id - Second vertex ID
     * @returns {number} Hash key combining both vertex IDs
     * @private
     */
    _hashVertexPair(v1Id, v2Id) {
        // Ensure consistent ordering (smaller ID first)
        const [small, large] = v1Id < v2Id ? [v1Id, v2Id] : [v2Id, v1Id];
        // Combine into single integer: (small << 16) | large
        // This works for vertex IDs up to 65535 (2^16 - 1)
        return (small << 16) | large;
    }

    /**
     * Finds an edge given two vertex IDs using fast hash map lookup.
     * 
     * @param {number} v1Id - First vertex ID
     * @param {number} v2Id - Second vertex ID
     * @returns {number|null} Edge ID if found, null otherwise
     */
    findEdgeByVertices(v1Id, v2Id) {
        const hash = this._hashVertexPair(v1Id, v2Id);
        let result = this.vertexPairToEdge.get(hash);
        return result ?? null;
    }

    /** Creates and adds an edge between two vertices to the grid.
     *
     * @param {number} v1Id - ID of first vertex
     * @param {number} v2Id - ID of second vertex
     * @param {Object} metadata - Additional metadata for the edge
     * @param {number} metadata.userGuess - State of user guess for the edge (0=unknown, 1=filled in, 2=ruled out)
     * @returns {number} - ID of new edge
     */
    addEdge(v1Id, v2Id, metadata = {}) {
        const id = this.nextId++;
        let newEdge = new Edge([v1Id, v2Id],
            // Faces will be populated in addFace, so edges must be added first without faces.
            new Set(), metadata);
        
        // Add id of this edge to grid's collection of edges.
        this.edges.set(id, newEdge);
        
        // Add to hash map for fast lookup
        const hash = this._hashVertexPair(v1Id, v2Id);
        // console.log(`Adding map from ${v1Id},${v2Id} = ${hash} to edge ${id}`);
        this.vertexPairToEdge.set(hash, id);

        // Add id of this edge to each vertex's collection of edges.
        this.vertices.get(v1Id).edgeIDs.add(id);
        this.vertices.get(v2Id).edgeIDs.add(id);
        
        return id;
    }

    /** Adds a face to the grid.
     *
     * @param {number[]} vertexIDs - IDs of vertices that make up the face
     * @param {Object} metadata - Additional metadata for the face
     * @param {number} id - ID for the face
     */
    addFace(vertexIDs, metadata = {}, id) {
        const edgeIDs = [];

        for (let i = 0; i < vertexIDs.length; i++) {
            const v1Id = vertexIDs[i];
            const v2Id = vertexIDs[(i + 1) % vertexIDs.length];

            // Use fast hash map lookup instead of iterating through all edges
            let edgeId = this.findEdgeByVertices(v1Id, v2Id);
            
            if (edgeId === null) {
                edgeId = this.addEdge(v1Id, v2Id);
                // console.log(`Face ${id}: Created new edge ${edgeId} for vertices ${v1}-${v2}`);
            }
            
            edgeIDs.push(edgeId);
            this.edges.get(edgeId).faceIDs.add(id);
        }

        this.faces.set(id, new Face(vertexIDs, edgeIDs, metadata));
        for (const vId of vertexIDs) {
            this.vertices.get(vId).faceIDs.add(id);
        }
    }

    /**
     * Sets up cross-references between grid elements and THREE.js objects
     * @param {Map} faceMap - Mapping of geometry face index to face ID
     * @param {Map} faceVertexRanges - Mapping of face ID to vertex ranges
     * @param {THREE.Mesh[]} edgeMeshes - Array of edge meshes
     */
    setupCrossReferences(faceMap, faceVertexRanges, edgeMeshes) {
        this.faceMap = faceMap;
        this.faceVertexRanges = faceVertexRanges;

        // Map edge IDs to their corresponding meshes
        this.edgeMeshMap.clear();
        edgeMeshes.forEach(mesh => {
            const edgeId = mesh.userData.edgeId;
            if (edgeId !== undefined) {
                this.edgeMeshMap.set(edgeId, mesh);
            }
        });
    }

    /**
     * Gets the THREE.js mesh for a specific edge
     * @param {number} edgeId - The edge ID
     * @returns {THREE.Mesh|null} The edge mesh or null if not found
     */
    getEdgeMesh(edgeId) {
        return this.edgeMeshMap.get(edgeId) || null;
    }

    /**
     * Gets all edge meshes
     * @returns {THREE.Mesh[]} Array of all edge meshes
     */
    getAllEdgeMeshes() {
        return Array.from(this.edgeMeshMap.values());
    }

    /** Gets all vertices (objects) that form a face.
     * @param {Face} face - The face object
     * @returns {Vertex[]} Array of Vertex objects that form the face
     */
    getFaceVertices(face) {
        // const face = this.faces.get(faceId); // No longer needed.
        // The face only stores vertex IDs, but the vertex data is stored in the Grid.
        return face ? face.vertexIDs.map(vId => this.vertices.get(vId)) : [];
    }

    /** Gets all faces that share an edge with the specified face.
     * @param {number} faceId - The ID of the face to find adjacent faces for
     * @returns {Set<number>} Set of adjacent Face IDs
     */
    getAdjacentFaces(faceId) {
        const face = this.faces.get(faceId);
        const adjacent = new Set();
        if (!face) return adjacent; // empty set
        for (const edgeId of face.edgeIDs) {
            const edge = this.edges.get(edgeId);
            for (const fId of edge.faceIDs) {
                if (fId !== faceId) adjacent.add(fId);
            }
        }
        return adjacent;
    }
}
