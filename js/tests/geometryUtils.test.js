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
    normalizeVertices,
} from '../geometryUtils.js';

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
