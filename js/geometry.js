import * as THREE from 'three';
import { Grid } from './Grid.js';
import { EDGE_RADIUS, EDGE_COLORS, FACE_DEFAULT_COLOR, FACE_HIGHLIGHT_COLOR, EDGE_STATES } from './constants.js';

/** Create geometry and topology of a dodecahedron.
 *
 * @returns {{geometry: THREE.BufferGeometry, grid: Grid, faceMap: Map<any, any>, faceVertexRanges: Map<any, any>,
 *      vertices: THREE.Vector3[]}}
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

function createPolyhedron(vertices, faceIndices) {
    const grid = new Grid();
    const vertexIds = vertices.map(v => grid.addVertex(v));

    const faceIds = faceIndices.map((face, i) =>
        grid.addFace(face.map(idx => vertexIds[idx]), {
            originalColor: FACE_DEFAULT_COLOR,
            highlightColor: FACE_HIGHLIGHT_COLOR,
            isHighlighted: false,
            index: i,
            clue: Math.floor(Math.random() * 11) - 1 // Random value from -1 to 9
        })
    );

    for (const [edgeId, edge] of grid.edges) {
        // edge.metadata.state = 'gray'; // delete
        // console.log("createDod", edge.metadata);
        edge.metadata.userGuess = 0;
    }

    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const colors = [];
    const indices = [];
    let vertexIndex = 0;

    const faceMap = new Map();
    const faceVertexRanges = new Map();

    for (const [faceId, face] of grid.faces) {
        const faceVertices = grid.getFaceVertices(faceId);
        const centerVertex = findCentroid(faceVertices);
        faceVertexRanges.set(faceId, {start: vertexIndex, count: faceVertices.length + 1});
        const startIdx = vertexIndex;
        positions.push(centerVertex.x, centerVertex.y, centerVertex.z);
        colors.push(0.27, 0.53, 1.0);
        vertexIndex++;
        for (const vertex of faceVertices) {
            positions.push(vertex.position.x, vertex.position.y, vertex.position.z);
            colors.push(0.27, 0.53, 1.0);
            vertexIndex++;
        }
        for (let i = 0; i < faceVertices.length; i++) {
            const next = (i + 1) % faceVertices.length;
            indices.push(startIdx, startIdx + i + 1, startIdx + next + 1);
            for (let j = 0; j < 3; j++) {
                faceMap.set(indices.length - 3 + j, faceId);
            }
        }
        console.log(`minRadius(${faceId}): `, findFaceMinRadius(grid, faceId));
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    return {geometry, grid: grid, faceMap, faceVertexRanges, vertices};
}

/** Create geometry and topology of a cube.
 *
 * @returns {{geometry: THREE.BufferGeometry, grid: Grid, faceMap: Map<any, any>, faceVertexRanges: Map<any, any>,
 *      vertices: THREE.Vector3[]}}
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

export function createEdgeGeometry(grid) {
    const edgeMeshes = [];
    const edgeMap = new Map();
    for (const [edgeId, edge] of grid.edges) {
        const v1 = grid.vertices.get(edge.vertices[0]);
        const v2 = grid.vertices.get(edge.vertices[1]);
        const direction = new THREE.Vector3().subVectors(v2.position, v1.position);
        const length = direction.length();
        const center = new THREE.Vector3().addVectors(v1.position, v2.position).multiplyScalar(0.5);
        const geometry = new THREE.CylinderGeometry(EDGE_RADIUS, EDGE_RADIUS, length, 8);
        const material = new THREE.MeshPhongMaterial({ color: EDGE_COLORS.unknown, shininess: 100 });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.copy(center);
        mesh.lookAt(v2.position);
        mesh.rotateX(Math.PI / 2);
        mesh.userData = { edgeId, grid };
        edgeMeshes.push(mesh);
        edgeMap.set(mesh, edgeId);
    }
    return { edgeMeshes, edgeMap };
}

export function findFaceMinRadius(grid, faceId) {
    const vertices = grid.getFaceVertices(faceId);
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

/** Find the center-ish of a polygon, by averaging its vertices.
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

/** Find the shortest distance from a point to a line.
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
