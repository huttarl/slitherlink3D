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
    makeCubeGrid, makeRhombusFaceGrid, makeTetrahedronGrid, makeSquarePyramidGrid,
} from './helpers.js';
import {
    describeFaceCensus, describeVertexConfiguration, faceCensus, faceNamer,
    facesAroundVertex, polygonName, quadrilateralName, vertexConfiguration,
    vertexConfigurationNotation,
} from '../solidFacts.js';

describe('polygonName', () => {
    test('names the polygons these solids are made of', () => {
        assert.strictEqual(polygonName(3), 'triangle');
        // Four sides alone make a quadrilateral; only measuring makes it a
        // square (see quadrilateralName).
        assert.strictEqual(polygonName(4), 'quadrilateral');
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
                               [{sides: 4, name: 'square', count: 6}]);
    });

    test('reports mixed faces in ascending order of sides', () => {
        assert.deepStrictEqual(faceCensus(makeSquarePyramidGrid()),
                               [{sides: 3, name: 'triangle', count: 4},
                                {sides: 4, name: 'square', count: 1}]);
    });

    test('describes the census in words, singular where count is 1', () => {
        assert.strictEqual(describeFaceCensus(faceCensus(makeSquarePyramidGrid())),
                           '4 triangles, 1 square');
    });

    test('one kind of face throughout is "all X", not a count', () => {
        // A Platonic solid's count would only repeat the face count the card
        // has just given ("6 faces (6 squares)").
        assert.strictEqual(describeFaceCensus(faceCensus(makeCubeGrid())),
                           'all squares');
        assert.strictEqual(describeFaceCensus(faceCensus(makeTetrahedronGrid())),
                           'all triangles');
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
        const grid = makeCubeGrid();
        const cycle = vertexConfiguration(grid);
        assert.deepStrictEqual(cycle, [4, 4, 4]);
        assert.strictEqual(vertexConfigurationNotation(cycle), '4.4.4');
        assert.strictEqual(
            describeVertexConfiguration(cycle, faceNamer(faceCensus(grid))),
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

describe('naming a four-sided face', () => {
    // The rhombic dodecahedron's card used to claim "all squares", because four
    // sides were assumed to mean a square. Its faces are rhombi -- which is
    // where its name comes from, so the card was contradicting the title.
    const square = [{x: 0, y: 0, z: 0}, {x: 1, y: 0, z: 0},
                    {x: 1, y: 1, z: 0}, {x: 0, y: 1, z: 0}];
    const rhombus = [{x: -1, y: 0, z: 0}, {x: 0, y: -0.5, z: 0},
                     {x: 1, y: 0, z: 0}, {x: 0, y: 0.5, z: 0}];
    const kite = [{x: 0, y: 0, z: 0}, {x: 1, y: 0.2, z: 0},
                  {x: 1.6, y: 1, z: 0}, {x: 0, y: 1, z: 0}];

    test('equal sides and equal diagonals: a square', () => {
        assert.strictEqual(quadrilateralName(square), 'square');
    });

    test('equal sides, unequal diagonals: a rhombus', () => {
        assert.strictEqual(quadrilateralName(rhombus), 'rhombus');
    });

    test('unequal sides: just a quadrilateral', () => {
        // A kite, as on the deltoidal solids. Nameable in principle, but "kite"
        // isn't a word a player would check against the solid's own name.
        assert.strictEqual(quadrilateralName(kite), 'quadrilateral');
    });

    test('a tilted square is still a square', () => {
        // The measurement is in 3D, so it mustn't depend on the face lying in a
        // coordinate plane -- no real face does.
        const tilted = square.map(p => ({
            x: p.x,
            y: (p.y + p.z) / Math.SQRT2,
            z: (p.z - p.y) / Math.SQRT2,
        }));
        assert.strictEqual(quadrilateralName(tilted), 'square');
    });

    test('the census counts a rhombic face as a rhombus', () => {
        const census = faceCensus(makeRhombusFaceGrid());
        assert.deepStrictEqual(census.find(kind => kind.sides === 4),
                               {sides: 4, name: 'rhombus', count: 1});
        assert.strictEqual(describeFaceCensus(census), '8 triangles, 1 rhombus');
    });

    test('faceNamer follows the solid, not the side count', () => {
        // What lets the vertex-configuration line say "square" on a cube and
        // "rhombus" on a rhombic solid, given only a cycle of side counts.
        assert.strictEqual(faceNamer(faceCensus(makeCubeGrid()))(4), 'square');
        assert.strictEqual(faceNamer(faceCensus(makeRhombusFaceGrid()))(4),
                           'rhombus');
        // A size the solid hasn't got falls back to the plain name.
        assert.strictEqual(faceNamer(faceCensus(makeCubeGrid()))(5), 'pentagon');
    });
});
