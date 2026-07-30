/**
 * Pure geometry math helpers: centroids, distances, normals, normalization.
 * No dependencies on Grid, scene-building, or the DOM (just THREE vector
 * types), so consumers like clueRenderer.js can import the math without
 * dragging in the polyhedron builder -- and the functions test headless
 * (see js/tests/geometryUtils.test.js).
 *
 * (Split out of geometry.js, which keeps the polyhedron/scene construction.)
 */
import * as THREE from './three/three.module.min.js';

/**
 * Find the center-ish of a polygon, by averaging its vertices.
 *
 * @param faceVertices an iterable of vertex objects
 * @returns {THREE.Vector3} the centroid
 */
export function findCentroid(faceVertices) {
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
export function findDistancePointToLine(p, v1, v2) {
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

/** Calculate face normal vector.
 *
 * @param { Vertex[] } faceVertices
 * @returns { THREE.Vector3 } unit normal vector.
 */
export function findFaceNormal(faceVertices) {
    const v1 = faceVertices[0].position;
    const v2 = faceVertices[1].position;
    const v3 = faceVertices[2].position;
    // Compute edge vectors by subtracting one vertex from another.
    const edge1 = new THREE.Vector3().subVectors(v2, v1);
    const edge2 = new THREE.Vector3().subVectors(v3, v1);
    // Then cross edge vectors to find perpendicular vector, and normalize length.
    return new THREE.Vector3().crossVectors(edge1, edge2).normalize();
}

/**
 * Normalize the vertices of a polyhedron so that they're centered about the origin,
 * and the maximum distance from the origin is 1.
 *
 * @param {THREE.Vector3[]} vertices - Array of vertex positions
 * @returns {void}
 */
export function normalizeVertices(vertices) {
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
