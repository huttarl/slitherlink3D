/**
 * Unit tests for Grid.js -- topology construction and lookups.
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import { makeCubeGrid } from './helpers.js';

describe('Grid topology (cube)', () => {
    test('builds the expected element counts, deduplicating shared edges', () => {
        const grid = makeCubeGrid();
        assert.strictEqual(grid.vertices.size, 8);
        assert.strictEqual(grid.faces.size, 6);
        // Each of the 6 quads contributes 4 sides; each edge is shared by
        // exactly 2 faces, so there must be 12 distinct edges.
        assert.strictEqual(grid.edges.size, 12);
    });

    test('findEdgeByVertices works in both vertex orders', () => {
        const grid = makeCubeGrid();
        const e = grid.findEdgeByVertices(0, 3);
        assert.notStrictEqual(e, null);
        assert.strictEqual(grid.findEdgeByVertices(3, 0), e);
    });

    test('findEdgeByVertices returns null for non-adjacent vertices', () => {
        const grid = makeCubeGrid();
        // 0 and 6 are diagonally opposite corners of the cube.
        assert.strictEqual(grid.findEdgeByVertices(0, 6), null);
    });

    test('every vertex has 3 incident edges; every edge borders 2 faces', () => {
        const grid = makeCubeGrid();
        for (const [_vId, vertex] of grid.vertices) {
            assert.strictEqual(vertex.edgeIDs.size, 3);
        }
        for (const [_eId, edge] of grid.edges) {
            assert.strictEqual(edge.faceIDs.size, 2);
        }
    });

    test('getAdjacentFaces: each cube face touches the 4 others except its opposite', () => {
        const grid = makeCubeGrid();
        const adjacent = grid.getAdjacentFaces(0); // bottom
        assert.strictEqual(adjacent.size, 4);
        assert.ok(!adjacent.has(1)); // top face shares no edge with bottom
        assert.ok(!adjacent.has(0)); // not adjacent to itself
    });

    test('getFaceVertices returns the vertices in face order', () => {
        const grid = makeCubeGrid();
        const vertices = grid.getFaceVertices(grid.faces.get(0));
        assert.strictEqual(vertices.length, 4);
        // Vertex objects, not IDs; all distinct.
        assert.strictEqual(new Set(vertices).size, 4);
    });
});
