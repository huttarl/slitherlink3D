import * as THREE from 'three';
import { Grid } from './Grid.js';
import { EDGE_RADIUS, EDGE_COLORS, FACE_DEFAULT_COLOR, FACE_HIGHLIGHT_COLOR, EDGE_STATES } from './constants.js';

/** Create geometry and topology of a dodecahedron.
 *
 * @returns {{geometry: THREE.BufferGeometry, grid: Grid,
 *      faceMap: Map<any, any>, faceVertexRanges: Map<any, any>}}
 */
export function createDodecahedron() {
    const phi = (1 + Math.sqrt(5)) / 2;
    const a = 1;
    const b = 1 / phi;
    const c = 2 - phi; // reserved if needed later

    const vertices = [
        new THREE.Vector3(a, a, a),
        new THREE.Vector3(a, a, -a),
        new THREE.Vector3(a, -a, a),
        new THREE.Vector3(a, -a, -a),
        new THREE.Vector3(-a, a, a),
        new THREE.Vector3(-a, a, -a),
        new THREE.Vector3(-a, -a, a),
        new THREE.Vector3(-a, -a, -a),
        new THREE.Vector3(0, b, phi),
        new THREE.Vector3(0, b, -phi),
        new THREE.Vector3(0, -b, phi),
        new THREE.Vector3(0, -b, -phi),
        new THREE.Vector3(b, phi, 0),
        new THREE.Vector3(b, -phi, 0),
        new THREE.Vector3(-b, phi, 0),
        new THREE.Vector3(-b, -phi, 0),
        new THREE.Vector3(phi, 0, b),
        new THREE.Vector3(phi, 0, -b),
        new THREE.Vector3(-phi, 0, b),
        new THREE.Vector3(-phi, 0, -b)
    ];

    const faceIndices = [
        [0, 8, 10, 2, 16],
        [0, 16, 17, 1, 12],
        [0, 12, 14, 4, 8],
        [1, 17, 3, 11, 9],
        [1, 9, 5, 14, 12],
        [2, 10, 6, 15, 13],
        [2, 13, 3, 17, 16],
        [3, 13, 15, 7, 11],
        [4, 14, 5, 19, 18],
        [4, 18, 6, 10, 8],
        [5, 9, 11, 7, 19],
        [6, 18, 19, 7, 15]
    ];

    return createPolyhedron(vertices, faceIndices);
}

/**
 * Creates a 3D polyhedron geometry with associated grid topology.
 *
 * @param {THREE.Vector3[]} vertices - Array of vertex positions for the polyhedron
 * @param {number[][]} faces - Array of face definitions, where each face is an array of vertex indices
 * @returns {Object} An object containing:
 *   - geometry {THREE.BufferGeometry}: The Three.js geometry of the polyhedron
 *   - grid {Grid}: The grid topology containing vertices, edges, and faces
 *   - faceMap {Map<number, number>}: Maps geometry vertex indices to grid face IDs for picking
 *   - faceVertexRanges {Map<number, {start: number, count: number}>}: Maps face IDs to vertex index ranges in the geometry
 *
 * Note: Vertex and face IDs in the Grid correspond to their array indices in the input arrays
 *
 * @description
 * This function creates a polyhedron by:
 * 1. Creating a grid with the specified vertices
 * 2. Adding faces to the grid using the provided vertex indices
 * 3. Setting up face metadata including colors and clues
 * 4. Creating a Three.js BufferGeometry with proper vertex positions and face indices
 * 5. Setting up data structures for face picking and coloring
 */
function createPolyhedron(vertices, faces) {
    const grid = new Grid();

    normalizeVertices(vertices);

    // Use vertex array indices as their IDs in the Grid
    vertices.forEach((v, index) => grid.addVertex(v, {}, index));

    faces.forEach((face, i) => {
        if (face.length < 3) {
            throw new Error(`Face ${i}: must have at least 3 vertices, got ${face.length}`);
        }

        grid.addFace(face, {
            originalColor: FACE_DEFAULT_COLOR,
            highlightColor: FACE_HIGHLIGHT_COLOR,
            isHighlighted: false,
            // Use index of face in loaded array of faces as that face's ID in the Grid.
            index: i,
            clue: -1 // No clue by default, will be set by puzzle data
        }, i)
    });

    for (const [_edgeId, edge] of grid.edges) {
        // console.log("createPolyh", edge.metadata);
        edge.metadata.userGuess = 0;
    }

    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const colors = [];
    const indices = [];
    let vertexIndex = 0;

    /** @type {Map<number, number>} - map from geometry index buffer vertex indices, to grid face IDs; for picking. */
    const faceMap = new Map();
    /** @type {Map<number, {start: number, count: number}>} - map from grid face IDs,
     * to ranges of vertex indices in the geometry index buffer. For changing the color of a face. */
    const faceVertexRanges = new Map();

    for (const [faceId, face] of grid.faces) {
        const faceVertices = grid.getFaceVertices(face);
        const centerVertex = findCentroid(faceVertices);
        faceVertexRanges.set(faceId, {start: vertexIndex, count: faceVertices.length + 1});
        const startIdx = vertexIndex;
        positions.push(centerVertex.x, centerVertex.y, centerVertex.z);
        // TODO: can we use face.metadata.originalColor here? or at least not hard-code the numbers?
        // Make center a little brighter than the outer rim of the face?
        colors.push(0.98, 0.98, 0.98);
        vertexIndex++;
        for (const vertex of faceVertices) {
            positions.push(vertex.position.x, vertex.position.y, vertex.position.z);
            // TODO: can we use face.metadata.originalColor here?
            colors.push(0.93, 0.93, 0.93);
            vertexIndex++;
        }
        for (let i = 0; i < faceVertices.length; i++) {
            const next = (i + 1) % faceVertices.length;
            indices.push(startIdx, startIdx + i + 1, startIdx + next + 1);
            for (let j = 0; j < 3; j++) {
                faceMap.set(indices.length - 3 + j, faceId);
            }
        }
        // console.log(`minRadius(${faceId}): `, findFaceMinRadius(grid, face));
        // TODO maybe: output a ratio of minRadius to max face radius, or polyhedron average radius, or ...?
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    return {geometry, grid: grid, faceMap, faceVertexRanges};
}

/** Create geometry and topology of a cube.
 *
 * @returns {{geometry: THREE.BufferGeometry, grid: Grid, faceMap: Map<any, any>, faceVertexRanges: Map<any, any>}}
 */
export function createCube() {
    const a = 1;

    const vertices = [
        new THREE.Vector3(a, a, a),
        new THREE.Vector3(a, a, -a),
        new THREE.Vector3(a, -a, a),
        new THREE.Vector3(a, -a, -a),
        new THREE.Vector3(-a, a, a),
        new THREE.Vector3(-a, a, -a),
        new THREE.Vector3(-a, -a, a),
        new THREE.Vector3(-a, -a, -a),
    ];

    const faceIndices = [
        [0, 2, 3, 1],
        [0, 1, 5, 4],
        [0, 4, 6, 2],
        [1, 3, 7, 5],
        [2, 6, 7, 3],
        [4, 5, 7, 6],
    ];

    return createPolyhedron(vertices, faceIndices);
}

/**
 * Loads a polyhedron from a JSON file and creates its geometry and topology.
 *
 * @param {string} filePath - Path to the JSON file (e.g., 'data/T.json')
 * @returns {Promise<{geometry: THREE.BufferGeometry, grid: Grid, faceMap: Map<any, any>,
 *     faceVertexRanges: Map<any, any>, gridId: string, gridName: string, categories: string[],
 *     recipe: string|undefined}>}
 * @throws {Error} If the file cannot be loaded or contains invalid data
 *
 * Note: Grid vertex and face IDs correspond to their array indices in the JSON file
 */
export async function loadPolyhedronFromJSON(filePath) {
    const response = await fetch(filePath);
    if (!response.ok) {
        throw new Error(`Failed to load polyhedron from ${filePath}: ${response.statusText}`);
    }

    const data = await response.json();

    // Validate required fields per json-format.md specification
    if (!data.gridId || typeof data.gridId !== 'string') {
        throw new Error('Invalid or missing gridId');
    }
    if (!data.gridName || typeof data.gridName !== 'string') {
        throw new Error('Invalid or missing gridName');
    }
    if (!data.vertices || !Array.isArray(data.vertices) || data.vertices.length < 4) {
        throw new Error('Invalid or missing vertices array (minimum 4 required)');
    }
    if (!data.faces || !Array.isArray(data.faces) || data.faces.length < 4) {
        throw new Error('Invalid or missing faces array (minimum 4 required)');
    }

    // Convert vertex coordinate arrays [x, y, z] to THREE.Vector3 objects
    const vertices = data.vertices.map(([x, y, z]) => new THREE.Vector3(x, y, z));

    // Use faces directly from JSON
    const faces = data.faces;

    // Call createPolyhedron to build geometry and grid topology
    const polyhedron = createPolyhedron(vertices, faces);

    // Add metadata from JSON to the result
    return {
        ...polyhedron,
        gridId: data.gridId,
        gridName: data.gridName,
        categories: data.categories || [],
        recipe: data.recipe
    };
}

/**
 * Creates THREE.js geometry for cylinders representing edges of a given grid.
 *
 * @param {Grid} grid - The grid containing edge data
 * @returns { edgeMeshes: THREE.Mesh[], edgeMap: Map<THREE.Mesh, number> }
 */
export function createEdgeGeometry(grid) {
    const edgeMeshes = [];
    const edgeMap = new Map();
    for (const [edgeId, edge] of grid.edges) {
        const v1 = grid.vertices.get(edge.vertexIDs[0]);
        const v2 = grid.vertices.get(edge.vertexIDs[1]);
        const direction = new THREE.Vector3().subVectors(v2.position, v1.position);
        const length = direction.length();
        const center = new THREE.Vector3().addVectors(v1.position, v2.position).multiplyScalar(0.5);
        const geometry = new THREE.CylinderGeometry(EDGE_RADIUS, EDGE_RADIUS, length, 8);
        // if (edgeId === 0) {
        //     console.log(`Edge 0 details: vertices [${edge.vertices[0]}, ${edge.vertices[1]}], v1=`, v1.position, `v2=`, v2.position, `length=${length}`);
        // }
        // console.log(`createEdgeGeometry: edge ${edgeId}, userGuess=${edge.metadata.userGuess}, state=${EDGE_STATES[edge.metadata.userGuess]}, color=`, EDGE_COLORS[EDGE_STATES[edge.metadata.userGuess]]);
        const material = new THREE.MeshPhongMaterial({ color: EDGE_COLORS[EDGE_STATES[edge.metadata.userGuess]],
            shininess: 100 });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.copy(center);
        mesh.lookAt(v2.position);
        mesh.rotateX(Math.PI / 2);
        mesh.userData = { edgeId, grid };
        edgeMeshes.push(mesh);
        // Set up a mapping from the mesh to the edgeId, for picking.
        edgeMap.set(mesh, edgeId);
        // And a link from edge to mesh, for coloring.
        edge.metadata.mesh = mesh;
    }
    return { edgeMeshes, edgeMap };
}

/**
 * Finds the minimum "radius" of a face.
 * This approximates the radius of an inscribed circle. We will use this to estimate what size text label will
 * fit on the face. We compute it by taking the minimum distance from the centroid of the face, to each vertex.
 *
 * @param {Grid} grid - The grid containing topology data
 * @param {Face} face - The face object
 * @returns {number} The minimum radius of the face
 */
export function findFaceMinRadius(grid, face) {
    const vertices = grid.getFaceVertices(face);
    const nVertices = vertices.length;
    const centerVertex = findCentroid(vertices);
    let minDistance = -1;
    // console.log("fFMR: ", nVertices);
    // For each vertex v1 and its following neighbor v2
    for (let v1 = 0; v1 < nVertices; v1++) {
        let v2 = (v1 + 1) % nVertices;
        // Find the shortest distance from centerVertex to the line from v1 to v2.
        let closestDistance = findDistancePointToLine(centerVertex, vertices[v1].position, vertices[v2].position);
        // console.log("  closestDistance: ", closestDistance);
        if (minDistance < 0 || minDistance > closestDistance) minDistance = closestDistance;
    }
    return minDistance;
}

/**
 * Find the center-ish of a polygon, by averaging its vertices.
 *
 * @param faceVertices an iterable of vertex objects
 * @returns {THREE.Vector3} the centroid
 */
function findCentroid(faceVertices) {
    let centerVertex = new THREE.Vector3();
    for (const vertex of faceVertices) {
        centerVertex.add(vertex.position);
    }
    centerVertex.divideScalar(faceVertices.length);
    return centerVertex;
}

/**
 * Find the shortest distance from a point to a line.
 *
 * @param {THREE.Vector3} p - the point
 * @param {THREE.Vector3} v1 - one point on the line
 * @param {THREE.Vector3} v2 - another point on the line
 * @returns {Float} - the perpendicular distance
 */
function findDistancePointToLine(p, v1, v2) {
    // Following the variable names at https://en.wikipedia.org/wiki/Distance_from_a_point_to_a_line#Vector_formulation
    // dist = ||(a - p) - ((a - p) ⋅ n) n||
    // console.log("findDistancePointToLine", p, v1, v2);
    const a = v1
    let n = new THREE.Vector3().subVectors(v2, v1).normalize();
    let aMinusP = new THREE.Vector3().subVectors(a, p);
    const b = n.multiplyScalar(aMinusP.dot(n)); // This changes n, but it's ok because we won't use n again.
    return aMinusP.sub(b).length();
}

/**
 * Normalize the vertices of a polyhedron so that they're centered about the origin,
 * and the maximum distance from the origin is 1.
 *
 * @param {THREE.Vector3[]} vertices - Array of vertex positions
 * @returns {void}
 */
function normalizeVertices(vertices) {
    // Add up all the vertex vectors.
    const totalPosition = vertices.reduce(
        (sum, v) => sum.add(v),
        new THREE.Vector3()
    );
    // Find the average position.
    const center = totalPosition.divideScalar(vertices.length); // destructively modify totalPosition
    console.debug("polyhedron centroid: ", center);
    // Move each vertex so that the average is at the origin, and compute max distance from origin.
    const maxDistance = vertices.reduce((max, v) => {
        v.sub(center); // modify vector in-place
        // Find max distance from origin.
        const length = v.length();
        return length > max ? length : max;
    }, 0);
    console.debug("max distance to vertex: ", maxDistance);
    if (maxDistance > 0) {
        // Scale all vertices so that the max distance is 1.
        vertices.forEach(v => v.divideScalar(maxDistance));
    } else {
        console.error("Vertices are all lumped together! This polyhedron won't work well.");
    }
}
