/**
 * Unit tests for geometryUtils.js -- the pure vector-math helpers.
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import * as THREE from '../three/three.module.min.js';
import {
    findCentroid,
    findDistancePointToLine,
    findFaceMinRadius,
    findFaceNormal,
    medianEdgeLength,
    normalizeVertices,
    pickTolerances,
    radiusScale,
} from '../geometryUtils.js';
import { COARSE_POINTER_RADIUS_FACTOR, PICK_RADIUS, RADIUS_LENGTH_EXPONENT,
         RADIUS_REFERENCE_EDGE } from '../constants.js';
import { makeCubeGrid } from './helpers.js';

// radiusScale asks what the player is pointing with (see js/pointer.js), so it
// needs a window even here. A mouse by default, which is what the rest of this file
// was written against; the coarse-pointer tests flip it and put it back. Read per
// call, so no import has to be deferred for this.
let coarsePointer = false;
globalThis.window = {matchMedia: () => ({matches: coarsePointer})};

/** Runs `body` as though the player were using a finger. */
function withFinger(body) {
    coarsePointer = true;
    try {
        return body();
    } finally {
        coarsePointer = false;
    }
}

/** Wrap raw [x,y,z] triples as vertex-like objects with .position. */
function asVertices(coords) {
    return coords.map(([x, y, z]) => ({ position: new THREE.Vector3(x, y, z) }));
}

const EPSILON = 1e-12;

describe('findCentroid', () => {
    test('centroid of a unit square', () => {
        const verts = asVertices([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]);
        const c = findCentroid(verts);
        assert.ok(c.distanceTo(new THREE.Vector3(0.5, 0.5, 0)) < EPSILON);
    });
});

describe('findDistancePointToLine', () => {
    test('perpendicular distance from a point to the x-axis', () => {
        const d = findDistancePointToLine(
            new THREE.Vector3(5, 3, 0),      // point (x doesn't matter for an infinite line)
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(1, 0, 0));
        assert.ok(Math.abs(d - 3) < EPSILON);
    });

    test('distance is zero for a point on the line', () => {
        const d = findDistancePointToLine(
            new THREE.Vector3(7, 0, 0),
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(1, 0, 0));
        assert.ok(d < EPSILON);
    });
});

describe('findFaceMinRadius', () => {
    test('inscribed-circle radius of a unit square face is 0.5', () => {
        const verts = asVertices([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]);
        // findFaceMinRadius only needs getFaceVertices from the grid.
        const stubGrid = { getFaceVertices: () => verts };
        const r = findFaceMinRadius(stubGrid, {});
        assert.ok(Math.abs(r - 0.5) < EPSILON);
    });

    test('elongated rectangle: limited by the nearer (long) sides', () => {
        const verts = asVertices([[0, 0, 0], [4, 0, 0], [4, 1, 0], [0, 1, 0]]);
        const stubGrid = { getFaceVertices: () => verts };
        const r = findFaceMinRadius(stubGrid, {});
        assert.ok(Math.abs(r - 0.5) < EPSILON); // half the short dimension
    });
});

describe('findFaceNormal', () => {
    test('CCW square in the xy-plane has normal +z', () => {
        const verts = asVertices([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]);
        const n = findFaceNormal(verts);
        assert.ok(n.distanceTo(new THREE.Vector3(0, 0, 1)) < EPSILON);
    });

    test('reversed winding flips the normal', () => {
        const verts = asVertices([[0, 1, 0], [1, 1, 0], [1, 0, 0], [0, 0, 0]]);
        const n = findFaceNormal(verts);
        assert.ok(n.distanceTo(new THREE.Vector3(0, 0, -1)) < EPSILON);
    });
});

describe('normalizeVertices', () => {
    test('centers vertices on the origin and scales max distance to 1', () => {
        const vertices = [
            new THREE.Vector3(2, 0, 0),
            new THREE.Vector3(6, 0, 0),
            new THREE.Vector3(4, 2, 0),
            new THREE.Vector3(4, -2, 0),
        ];
        normalizeVertices(vertices); // modifies in place
        // New centroid should be the origin...
        const centroid = vertices.reduce((sum, v) => sum.add(v), new THREE.Vector3())
            .divideScalar(vertices.length);
        assert.ok(centroid.length() < EPSILON);
        // ...and the farthest vertex should be at distance exactly 1.
        const maxDist = Math.max(...vertices.map(v => v.length()));
        assert.ok(Math.abs(maxDist - 1) < EPSILON);
    });
});

/** The test cube has corners at 0..1, so every edge is 1 long; scaling its
 *  vertices scales its edges by the same factor. (helpers.js gives vertices a
 *  minimal {x, y, z} position rather than a THREE.Vector3, so this scales the
 *  components by hand.) */
function cubeWithEdgeLength(length) {
    const grid = makeCubeGrid();
    for (const vertex of grid.vertices.values()) {
        vertex.position.x *= length;
        vertex.position.y *= length;
        vertex.position.z *= length;
    }
    return grid;
}

describe('medianEdgeLength', () => {
    test('measures the edges of a grid', () => {
        assert.ok(Math.abs(medianEdgeLength(cubeWithEdgeLength(1)) - 1) < 1e-9);
        assert.ok(Math.abs(medianEdgeLength(cubeWithEdgeLength(0.4)) - 0.4) < 1e-9);
    });

    test('an outlier does not move it, which is why it is the median', () => {
        // randD's edges run 0.136 to 0.877; a mean would be dragged by the ends,
        // and the radius should follow how long the edges GENERALLY are.
        const grid = cubeWithEdgeLength(1);
        const stretched = grid.vertices.get(6).position;   // wrecks 3 edges
        stretched.x *= 20; stretched.y *= 20; stretched.z *= 20;
        assert.ok(Math.abs(medianEdgeLength(grid) - 1) < 1e-9);
    });

    test('0 for a grid with no edges, so radiusScale can spot it', () => {
        const grid = makeCubeGrid();
        grid.edges.clear();
        assert.strictEqual(medianEdgeLength(grid), 0);
    });
});

describe('radiusScale', () => {
    test('full radius at the reference edge length, and never more', () => {
        const at = cubeWithEdgeLength(RADIUS_REFERENCE_EDGE);
        assert.ok(Math.abs(radiusScale(at) - 1) < 1e-9);
        // Clamped, so a grid with longer edges than anything in data/ can't
        // exceed the radius the constants call a maximum.
        assert.strictEqual(radiusScale(cubeWithEdgeLength(5)), 1);
    });

    test('shrinks with edge length, but SUB-proportionally', () => {
        // The whole point: halving the edges must thin them by much less than
        // half, or small-faced solids get hairlines.
        const big = radiusScale(cubeWithEdgeLength(1.0));
        const small = radiusScale(cubeWithEdgeLength(0.5));
        assert.ok(small < big, 'shorter edges should be thinner');
        assert.ok(small > big * 0.5,
            `halving the length must not halve the radius: ${small} vs ${big}`);
        // Derived from the exponent rather than hard-coded, so tuning it doesn't
        // put a false failure here -- the PROPERTY above is what matters.
        assert.ok(Math.abs(big / small - Math.pow(2, RADIUS_LENGTH_EXPONENT))
                  < 1e-9);
    });

    test('etI is thinned to about two thirds, the cube barely at all', () => {
        // The two ends of data/, as measured on rendered edge lengths. This is
        // the behaviour the exponent was chosen for; it guards the choice, so
        // expect it to fail if the exponent is retuned -- and read the numbers
        // before updating it.
        assert.ok(Math.abs(radiusScale(cubeWithEdgeLength(0.256)) - 0.63) < 0.01);
        assert.ok(Math.abs(radiusScale(cubeWithEdgeLength(1.155)) - 0.92) < 0.01);
    });

    test('the pick tolerance follows the radius, not its own scale', () => {
        // The relationship the constants document: the click target is twice the
        // drawn tube, whatever size that tube ends up. A fixed tolerance made
        // dense grids pick unpredictably.
        const grid = cubeWithEdgeLength(0.256);
        const {pickRadius, pickDepthTolerance} = pickTolerances(grid);
        assert.ok(Math.abs(pickRadius
                           - PICK_RADIUS * radiusScale(grid)) < 1e-12);
        assert.strictEqual(pickDepthTolerance, pickRadius * 2);
        // And it really is smaller than the old fixed value on such a grid.
        assert.ok(pickRadius < PICK_RADIUS);
    });

    test('a grid with no edges keeps the full radius rather than vanishing', () => {
        const grid = makeCubeGrid();
        grid.edges.clear();
        assert.strictEqual(radiusScale(grid), 1);
    });
});

describe('radiusScale for a finger', () => {
    test('everything is drawn thicker, by the same factor on every grid', () => {
        // Uniform, so a phone sees the same relative thicknesses between grids
        // that a desktop does -- the touch factor answers who is playing, and the
        // exponent answers which grid this is, and neither disturbs the other.
        for (const length of [0.256, 1.155, RADIUS_REFERENCE_EDGE]) {
            const grid = cubeWithEdgeLength(length);
            const mouse = radiusScale(grid);
            const finger = withFinger(() => radiusScale(grid));
            assert.ok(Math.abs(finger - mouse * COARSE_POINTER_RADIUS_FACTOR) < 1e-12,
                `edge ${length}: ${finger} is not ${COARSE_POINTER_RADIUS_FACTOR}x `
                + `${mouse}`);
            assert.ok(finger > mouse, 'a finger needs a bigger target, not smaller');
        }
    });

    test('the clamp still bites, so a long-edged grid gains nothing extra', () => {
        // The factor multiplies the clamped result rather than being clamped with
        // it: the ceiling is on how much a grid may have, not on what a finger
        // gets. Were the order reversed, the reference-length grid and every
        // longer one would be left at 1 and a phone would see no change at all on
        // the sparsest solids.
        const capped = withFinger(() => radiusScale(cubeWithEdgeLength(5)));
        assert.strictEqual(capped, COARSE_POINTER_RADIUS_FACTOR);
    });

    test('the pick target follows, staying twice the drawn tube', () => {
        // The promise the constants make, kept without pickTolerances having to
        // know about pointers: it goes through radiusScale like the radii do.
        const grid = cubeWithEdgeLength(0.256);
        const mouse = pickTolerances(grid);
        const finger = withFinger(() => pickTolerances(grid));
        assert.ok(Math.abs(finger.pickRadius
                           - mouse.pickRadius * COARSE_POINTER_RADIUS_FACTOR) < 1e-12);
        assert.strictEqual(finger.pickDepthTolerance, finger.pickRadius * 2);
        assert.ok(Math.abs(finger.pickRadius
                           - PICK_RADIUS * withFinger(() => radiusScale(grid)))
                  < 1e-12);
    });
});
