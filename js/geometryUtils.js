/**
 * Pure geometry math helpers: centroids, distances, normals, normalization.
 * No dependencies on Grid or scene-building, so consumers like clueRenderer.js can
 * import the math without dragging in the polyhedron builder.
 *
 * One exception to the DOM-freedom this module otherwise keeps: radiusScale (and
 * so pickTolerances) asks whether the player is using a finger, because it is the
 * single multiplier every radius goes through and that is where the answer has to
 * be applied. The tests supply a window stub; everything else here still runs on
 * nothing but THREE's vector types (see js/tests/geometryUtils.test.js).
 *
 * (Split out of geometry.js, which keeps the polyhedron/scene construction.)
 */
import * as THREE from './three/three.module.min.js';
import {COARSE_POINTER_RADIUS_FACTOR, PICK_RADIUS, RADIUS_LENGTH_EXPONENT,
        RADIUS_REFERENCE_EDGE} from './constants.js';
import {debug} from './debug.js';
import {hasCoarsePointer} from './pointer.js';

/**
 * The median rendered edge length of a grid.
 *
 * RENDERED, so call this only after normalizeVertices: the stored files are not
 * all at circumradius 1 (the cube's are at +/-1, giving an edge of 2 on disk and
 * 1.155 on screen), and the number wanted here is the one the player sees.
 *
 * Median rather than mean or extremes: several solids have a few edges far off
 * the rest -- randD's run 0.136 to 0.877 -- and the median is what represents how
 * big the solid's edges GENERALLY are without one outlier dragging it.
 *
 * Reads x/y/z rather than calling Vector3 methods, so any position-like object
 * works. The distance between two points needs no class, and not requiring one
 * keeps this usable from the tests' lightweight vertex stubs.
 *
 * @param {Grid} grid - with normalized vertex positions
 * @returns {number} 0 for a grid with no edges
 */
export function medianEdgeLength(grid) {
    const lengths = [];
    for (const edge of grid.edges.values()) {
        const a = grid.vertices.get(edge.vertexIDs[0]);
        const b = grid.vertices.get(edge.vertexIDs[1]);
        if (a && b) {
            lengths.push(Math.hypot(a.position.x - b.position.x,
                                    a.position.y - b.position.y,
                                    a.position.z - b.position.z));
        }
    }
    if (lengths.length === 0) return 0;
    lengths.sort((x, y) => x - y);
    const middle = lengths.length >> 1;
    return (lengths.length % 2 === 1) ? lengths[middle]
        : (lengths[middle - 1] + lengths[middle]) / 2;
}

/**
 * How much to shrink the edge and vertex radii on this grid, 0..1.
 *
 * The problem: every solid is drawn to the same size, so a 182-face grid has
 * edges a seventh the length of a tetrahedron's (0.23 against 1.63 across
 * data/) while both were drawn with the same radius -- which reads as
 * grotesquely fat tubes on the big solids.
 *
 * A power law rather than proportionality, because proportionality would draw
 * those edges as hairlines. RADIUS_LENGTH_EXPONENT is a dial between the two: 0
 * is a constant radius, 1 is fully proportional, and a third of the way along
 * takes etI's radius to 54% while leaving the cube's at 89%. Note the radius
 * shrinks SUB-proportionally, so short edges keep relatively more thickness --
 * but its rate does not slow near zero, which the exponent being under 1 makes
 * tempting to assume. No floor is needed: over data/ the smallest result is
 * 0.016, which is already a reasonable minimum.
 *
 * ONE SCALE PER GRID, from the median, deliberately -- not per edge. Within one
 * solid the edges can differ by a factor of six (randD again), and drawing those
 * at visibly different thicknesses looks like a mistake rather than a response
 * to scale.
 *
 * A finger then gets everything half again as thick, applied AFTER the clamp so
 * the two decisions stay separable: the clamp is about which grid this is, and the
 * factor is about who is playing. See COARSE_POINTER_RADIUS_FACTOR.
 *
 * Being the one multiplier both radii and the pick tolerance go through is the
 * reason the touch factor belongs here rather than at the three call sites: it is
 * what keeps the click target at twice the drawn tube without anyone having to
 * remember to multiply.
 *
 * @param {Grid} grid - with normalized vertex positions
 * @returns {number} a multiplier for EDGE_RADIUS and VERTEX_RADIUS, never above 1
 *     for a mouse -- so the constants stay the maximum they have always been --
 *     and never above COARSE_POINTER_RADIUS_FACTOR for a finger
 */
export function radiusScale(grid) {
    const pointerFactor = hasCoarsePointer() ? COARSE_POINTER_RADIUS_FACTOR : 1;
    const median = medianEdgeLength(grid);
    if (median <= 0) return pointerFactor;
    return Math.min(1, Math.pow(median / RADIUS_REFERENCE_EDGE,
                                RADIUS_LENGTH_EXPONENT)) * pointerFactor;
}

/**
 * How much slack picking gets on this grid, in world units.
 *
 * On the SAME scale as the drawn radius, so the click target stays the documented
 * multiple of the tube the player can see. A fixed tolerance was tried first, on
 * the reasoning that a thinner edge should be no harder to hit, and it went wrong
 * on the dense solids: 0.06 of slack is a fifth of the way along one of etI's
 * 0.256 edges, so it was wider than the gaps it had to tell apart and picks near a
 * vertex resolved unpredictably.
 *
 * Note this does not make the tolerance a constant FRACTION of an edge -- the
 * radius shrinks sub-proportionally, so relative slack still grows on denser
 * grids. It only ties the slack to what the edges look like, which is what makes
 * it predictable. Capping it as a share of the median edge length is the stronger
 * move, if the dense grids still misbehave.
 *
 * @param {Grid} grid - with normalized vertex positions
 * @returns {{pickRadius: number, pickDepthTolerance: number}}
 */
export function pickTolerances(grid) {
    const pickRadius = PICK_RADIUS * radiusScale(grid);
    // Depth slack follows the radius because it exists to absorb it: a tolerant
    // pick reports the depth where the ray passes closest to the edge's centre
    // line, which can fall a little beyond the face beside it, and how far beyond
    // is proportional to how much slack was allowed.
    return {pickRadius, pickDepthTolerance: pickRadius * 2};
}

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
    debug("polyhedron centroid: ", center);
    // Move each vertex so that the average is at the origin, and compute max distance from origin.
    const maxDistance = vertices.reduce((max, v) => {
        v.sub(center); // modify vector in-place
        // Find max distance from origin.
        const length = v.length();
        return length > max ? length : max;
    }, 0);
    debug("max distance to vertex: ", maxDistance);
    if (maxDistance > 0) {
        // Scale all vertices so that the max distance is 1.
        vertices.forEach(v => v.divideScalar(maxDistance));
    } else {
        console.error("Vertices are all lumped together! This polyhedron won't work well.");
    }
}
