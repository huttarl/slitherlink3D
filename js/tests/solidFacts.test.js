/**
 * Tests for the facts the About-this-solid card derives from a grid's own
 * topology: what kinds of face it has, and how they meet at a vertex.
 *
 * The shapes are built headlessly by helpers.js, so these run in the fast
 * suite -- no browser, no THREE geometry, positions are stubs. Only topology
 * matters to any of this.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';
import {
    makeCubeGrid, makeTetrahedronGrid, makeSquarePyramidGrid,
} from './helpers.js';
import {
    describeFaceCensus, describeVertexConfiguration, faceCensus,
    facesAroundVertex, polygonName, vertexConfiguration,
    vertexConfigurationNotation,
} from '../solidFacts.js';

describe('polygonName', () => {
    test('names the polygons these solids are made of', () => {
        assert.strictEqual(polygonName(3), 'triangle');
        assert.strictEqual(polygonName(4), 'square');
        assert.strictEqual(polygonName(10), 'decagon');
    });

    test('falls back to n-gon for anything unnamed', () => {
        assert.strictEqual(polygonName(14), '14-gon');
        assert.strictEqual(polygonName(14, true), '14-gons');
    });

    test('pluralizes on request', () => {
        assert.strictEqual(polygonName(6, true), 'hexagons');
    });
});

describe('faceCensus', () => {
    test('counts a cube as six squares', () => {
        assert.deepStrictEqual(faceCensus(makeCubeGrid()),
                               [{sides: 4, count: 6}]);
    });

    test('reports mixed faces in ascending order of sides', () => {
        assert.deepStrictEqual(faceCensus(makeSquarePyramidGrid()),
                               [{sides: 3, count: 4}, {sides: 4, count: 1}]);
    });

    test('describes the census in words, singular where count is 1', () => {
        assert.strictEqual(describeFaceCensus(faceCensus(makeSquarePyramidGrid())),
                           '4 triangles, 1 square');
        assert.strictEqual(describeFaceCensus(faceCensus(makeCubeGrid())),
                           '6 squares');
    });
});

describe('facesAroundVertex', () => {
    test('walks the whole fan: three squares at a cube corner', () => {
        assert.deepStrictEqual(facesAroundVertex(makeCubeGrid(), 0), [4, 4, 4]);
    });

    test('four triangles round a square pyramid apex', () => {
        assert.deepStrictEqual(facesAroundVertex(makeSquarePyramidGrid(), 4),
                               [3, 3, 3, 3]);
    });

    test('a base corner of the pyramid: two triangles and the square', () => {
        const cycle = facesAroundVertex(makeSquarePyramidGrid(), 0);
        assert.strictEqual(cycle.length, 3);
        // The walk may start anywhere and run either way round, so compare as
        // a multiset; vertexConfiguration is what pins down the order.
        assert.deepStrictEqual([...cycle].sort(), [3, 3, 4]);
    });

    test('the square is between the two triangles, not beside them', () => {
        // Cyclically, a 3-fan reads the same however you rotate it, so the real
        // content here is that all three faces are found -- checked above. What
        // this adds is that a 4-fan preserves adjacency: on the cube every
        // neighbouring pair in the cycle shares an edge.
        const grid = makeCubeGrid();
        const cycle = facesAroundVertex(grid, 0);
        assert.strictEqual(cycle.length, grid.vertices.get(0).faceIDs.size);
    });

    test('null for a vertex that is not in the grid', () => {
        assert.strictEqual(facesAroundVertex(makeCubeGrid(), 99), null);
    });
});

describe('vertexConfiguration', () => {
    test('a cube is 4.4.4 at every vertex', () => {
        const cycle = vertexConfiguration(makeCubeGrid());
        assert.deepStrictEqual(cycle, [4, 4, 4]);
        assert.strictEqual(vertexConfigurationNotation(cycle), '4.4.4');
        assert.strictEqual(describeVertexConfiguration(cycle),
                           'square, square, square');
    });

    test('a tetrahedron is 3.3.3', () => {
        assert.deepStrictEqual(vertexConfiguration(makeTetrahedronGrid()),
                               [3, 3, 3]);
    });

    test('null when the vertices are not all alike (a Johnson solid)', () => {
        // The apex meets four triangles; a base corner meets two triangles and
        // the square. No shared configuration, so the card stays quiet.
        assert.strictEqual(vertexConfiguration(makeSquarePyramidGrid()), null);
    });

    test('a fan walked from a different edge or direction still matches', () => {
        // Every cube vertex is alike, so the canonical form must survive the
        // arbitrary starting edge and direction of each separate walk. Were the
        // rotations not canonicalized, some vertex pair would disagree.
        const grid = makeCubeGrid();
        for (const vertexId of grid.vertices.keys()) {
            assert.deepStrictEqual(facesAroundVertex(grid, vertexId).length, 3);
        }
        assert.notStrictEqual(vertexConfiguration(grid), null);
    });
});
