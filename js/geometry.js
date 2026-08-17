/**
 * Polyhedron construction: loads grid JSON and builds the THREE geometry,
 * Grid topology, and picking/coloring cross-references, plus the edge
 * cylinder meshes.
 *
 * Pure vector-math helpers (centroids, distances, normals, normalization)
 * live in geometryUtils.js.
 *
 * (The old hardcoded createCube()/createDodecahedron() builders were
 * removed July 2026: superseded by data/cube.json and data/D.json, and no
 * longer called anywhere. They remain in git history if ever needed.)
 */
import * as THREE from './three/three.module.min.js';
import { Grid } from './Grid.js';
import { EDGE_RADIUS, EDGE_COLORS, FACE_COLORS,
         EDGE_STATES } from './constants.js';
import { findCentroid, freezeTransform, normalizeVertices,
         radiusScale } from './geometryUtils.js';

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
            originalColor: FACE_COLORS.default,
            highlightColor: FACE_COLORS.highlight,
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
        // console.log(`minRadius(${faceId}): `, findFaceMinRadius(grid, face));  // (now in geometryUtils.js)
        // TODO maybe: output a ratio of minRadius to max face radius, or polyhedron average radius, or ...?
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    return {geometry, grid, faceMap, faceVertexRanges};
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
    // no-cache: revalidate rather than trusting a cached copy, since grid
    // files get regenerated during development (see the note in ui.js).
    const response = await fetch(filePath, {cache: 'no-cache'});
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
 * Also builds the invisible line segments that picking aims at, which give
 * click tolerance for free; see makeEdgePickLines.
 *
 * @param {Grid} grid - The grid containing edge data
 * @returns {{edgeMeshes: THREE.Mesh[], pickLines: THREE.LineSegments,
 *     pickEdgeIds: number[]}} the meshes that display the edges, the invisible
 *     lines picking uses, and the edge id of each of its segments
 */
export function createEdgeGeometry(grid) {
    const edgeMeshes = [];
    const pickPositions = [];
    const pickEdgeIds = [];
    // One radius for the whole grid, scaled to how long its edges are: the same
    // absolute thickness that looks right on a tetrahedron is a fat tube on a
    // 182-face solid. See radiusScale. NOT applied to the pick tolerance below,
    // which stays absolute -- a thinner edge should be no harder to hit.
    const edgeRadius = EDGE_RADIUS * radiusScale(grid);
    for (const [edgeId, edge] of grid.edges) {
        const v1 = grid.vertices.get(edge.vertexIDs[0]);
        const v2 = grid.vertices.get(edge.vertexIDs[1]);
        const direction = new THREE.Vector3().subVectors(v2.position, v1.position);
        const length = direction.length();
        const center = new THREE.Vector3().addVectors(v1.position, v2.position).multiplyScalar(0.5);
        const geometry = new THREE.CylinderGeometry(edgeRadius, edgeRadius, length, 8);
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
        // Placed for good; see freezeTransform. The celebration's swell is the
        // one thing that moves an edge afterwards, and it updates its own matrix.
        freezeTransform(mesh);
        mesh.userData = { edgeId, grid };
        edgeMeshes.push(mesh);
        // And a link from edge to mesh, for coloring.
        edge.metadata.mesh = mesh;

        // Two endpoints per edge, in the order the ids were walked, so a
        // segment's index identifies its edge. See makeEdgePickLines.
        pickPositions.push(v1.position.x, v1.position.y, v1.position.z,
                           v2.position.x, v2.position.y, v2.position.z);
        pickEdgeIds.push(edgeId);
    }
    return {edgeMeshes, ...makeEdgePickLines(pickPositions, pickEdgeIds)};
}

/**
 * The invisible Points object that vertex picking aims at, and the vertex id of
 * each point.
 *
 * The same trick as makeEdgePickLines, for the same reason and with the same payoff:
 * Raycaster gives a Points object a tolerance for free via params.Points.threshold,
 * treating each point as a sphere of that radius. Aiming at the DRAWN vertex spheres
 * instead would mean exact triangle intersection against a ball whose radius is
 * VERTEX_RADIUS scaled down on the crowded grids -- a target of a few pixels, when
 * the whole reason for picking a vertex is that it should be an easy one.
 *
 * One object for every vertex, rather than one per vertex, and invisible: invisible
 * objects are still raycast, only rendering skips them.
 *
 * @param {Grid} grid
 * @returns {{pickPoints: THREE.Points, pickVertexIds: number[]}}
 */
export function makeVertexPickPoints(grid) {
    const positions = [];
    const pickVertexIds = [];
    for (const [vertexId, vertex] of grid.vertices) {
        positions.push(vertex.position.x, vertex.position.y, vertex.position.z);
        pickVertexIds.push(vertexId);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position',
        new THREE.Float32BufferAttribute(positions, 3));
    const pickPoints = new THREE.Points(geometry, new THREE.PointsMaterial());
    pickPoints.visible = false;
    freezeTransform(pickPoints);
    return {pickPoints, pickVertexIds};
}

/**
 * Builds the invisible LineSegments that picking actually aims at.
 *
 * Picking wants tolerance -- the drawn cylinders are thin, and a click that
 * lands just beside one should still count -- and Raycaster gives that for free
 * on Line objects via params.Line.threshold, which treats each segment as a
 * capsule of that radius. Meshes have no such parameter (their raycast is exact
 * triangle intersection), so the alternative would be a second, wider cylinder
 * per edge: measured 3.7x slower to pick against (69us vs 19us on the truncated
 * icosahedron), one object per edge instead of one in total, and a tolerance
 * baked into geometry rather than adjustable at will.
 *
 * The result is invisible. Invisible objects are still raycast -- only rendering
 * skips them -- which is what makes this work.
 *
 * @param {number[]} positions - endpoint coordinates, 6 per edge
 * @param {number[]} pickEdgeIds - edge id per segment, in the same order
 * @returns {{pickLines: THREE.LineSegments, pickEdgeIds: number[]}}
 */
function makeEdgePickLines(positions, pickEdgeIds) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position',
        new THREE.Float32BufferAttribute(positions, 3));
    const pickLines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial());
    pickLines.visible = false;
    // Never rendered, but the raycaster reads its world matrix, and it sits at
    // the origin forever. (Invisible is not the same as absent: see the note
    // above about why picking works at all.)
    freezeTransform(pickLines);
    return {pickLines, pickEdgeIds};
}
