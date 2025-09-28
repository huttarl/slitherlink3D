// Graph-based topology representation for polyhedra.
// Maintains relationships between vertices, edges, and faces.
// Assumes manifold, convex polyhedron.
// Allows for efficient traversal and query operations.
// We also keep here metadata for puzzles (such as clues and solutions)
// and the user's current guesses and markings.

export class Grid {
    constructor() {
        this.vertices = new Map();
        this.edges = new Map();
        this.faces = new Map();
        this.nextId = 0;
    }

    // Adds a vertex to the topology.
    // Metadata: none yet?
    addVertex(position, metadata = {}) {
        const id = this.nextId++;
        this.vertices.set(id, {
            position: position.clone(),
            edges: new Set(),
            faces: new Set(),
            metadata
        });
        return id;
    }

    // Creates an edge between two vertices
    // Metadata:
    //   userGuess: 0, 1, 2 (means unknown / filled in / ruled out)
    addEdge(v1Id, v2Id, metadata = {}) {
        const id = this.nextId++;
        let newEdge = {
            vertices: [v1Id, v2Id],
            faces: new Set(),
            metadata
        };
        // console.log("addEdge", `${id} ${newEdge.metadata}`);
        this.edges.set(id, newEdge);
        this.vertices.get(v1Id).edges.add(id);
        this.vertices.get(v2Id).edges.add(id);
        return id;
    }

    // Creates a face from a list of vertices
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


