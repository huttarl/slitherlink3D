/**
 * Unit tests for solutionChecker.js -- the pure rule/solution queries.
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import {
    countGuesses,
    findVertexViolations,
    findClueViolations,
    isClueSatisfied,
    partitionFacesByLoop,
    findSolutionMismatches,
    checkSingleLoop,
} from '../solutionChecker.js';
import { makeCubeGrid, setEdge, loopVertexPairs } from './helpers.js';

// The cube's bottom-face loop, used as a known solution in several tests.
const BOTTOM_LOOP = [0, 3, 2, 1];

describe('countGuesses', () => {
    test('counts filled and ruled-out edges, ignoring unknowns', () => {
        const grid = makeCubeGrid();
        setEdge(grid, 0, 3, 1); // filled
        setEdge(grid, 3, 2, 2); // ruled out
        // Count over the bottom face's edges (2 marked + 2 unknown).
        const face = grid.faces.get(0);
        assert.deepStrictEqual(countGuesses(grid, face.edgeIDs),
            { numEdgesFilled: 1, numEdgesRuledOut: 1 });
    });
});

describe('findVertexViolations', () => {
    test('flags a vertex with 3 filled edges', () => {
        const grid = makeCubeGrid();
        // Vertex 0 has exactly 3 edges on a cube; fill them all.
        for (const edgeId of grid.vertices.get(0).edgeIDs) {
            grid.edges.get(edgeId).metadata.userGuess = 1;
        }
        assert.deepStrictEqual(findVertexViolations(grid, grid.vertices.keys()), [0]);
    });

    test('accepts vertices with 0, 1 or 2 filled edges', () => {
        const grid = makeCubeGrid();
        setEdge(grid, 0, 3, 1);
        setEdge(grid, 0, 1, 1); // vertex 0 now has 2 filled: fine
        assert.deepStrictEqual(findVertexViolations(grid, grid.vertices.keys()), []);
    });

    test('checks only the requested vertices', () => {
        const grid = makeCubeGrid();
        for (const edgeId of grid.vertices.get(0).edgeIDs) {
            grid.edges.get(edgeId).metadata.userGuess = 1;
        }
        // Vertex 6 is not incident to any of vertex 0's edges.
        assert.deepStrictEqual(findVertexViolations(grid, [6]), []);
    });
});

describe('findClueViolations', () => {
    test('ignores unclued faces entirely', () => {
        const grid = makeCubeGrid();
        for (const [_id, edge] of grid.edges) edge.metadata.userGuess = 1; // absurd board
        assert.deepStrictEqual(findClueViolations(grid, grid.faces.keys(), false), []);
    });

    test('passive: no violation while the clue is still achievable', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 3;
        setEdge(grid, 0, 3, 1); // 1 of 3 filled so far: fine
        assert.deepStrictEqual(findClueViolations(grid, [0], false), []);
    });

    test('passive: flags overfilled clue', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 1;
        setEdge(grid, 0, 3, 1);
        setEdge(grid, 2, 1, 1); // 2 filled > clue 1
        const violations = findClueViolations(grid, [0], false);
        assert.strictEqual(violations.length, 1);
        assert.strictEqual(violations[0].faceId, 0);
        assert.match(violations[0].message, /should only have 1/);
    });

    test('passive: flags clue made impossible by ruled-out edges', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 3;
        setEdge(grid, 0, 3, 2);
        setEdge(grid, 3, 2, 2); // only 2 of 4 edges remain available < clue 3
        const violations = findClueViolations(grid, [0], false);
        assert.strictEqual(violations.length, 1);
        assert.match(violations[0].message, /ruled out/);
    });

    test('active (requireExact): flags any clue not exactly matched', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 2;
        setEdge(grid, 0, 3, 1); // 1 filled, needs exactly 2
        assert.strictEqual(findClueViolations(grid, [0], true).length, 1);
        setEdge(grid, 3, 2, 1); // now exactly 2
        assert.deepStrictEqual(findClueViolations(grid, [0], true), []);
    });
});

describe('isClueSatisfied', () => {
    test('an unclued face is never satisfied', () => {
        const grid = makeCubeGrid();
        // Face 0 keeps its clue of -1; fill an edge so the count isn't 0 either.
        setEdge(grid, 0, 3, 1);
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), false);
    });

    test('a 0 clue starts satisfied and stops when an edge is filled', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 0;
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), true);
        setEdge(grid, 0, 3, 1);
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), false);
    });

    test('satisfied exactly when the filled count reaches the clue', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 2;
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), false);
        setEdge(grid, 0, 3, 1);
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), false);
        setEdge(grid, 3, 2, 1);
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), true);
    });

    test('overfilled is not satisfied', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 1;
        setEdge(grid, 0, 3, 1);
        setEdge(grid, 3, 2, 1); // 2 filled, clue 1: over, not done
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), false);
    });

    test('ruled-out edges do not count toward the clue', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 1;
        setEdge(grid, 0, 3, 2); // ruled out, not filled
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), false);
        setEdge(grid, 3, 2, 1);
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), true);
    });

    test('counts only the face\'s own edges', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 0;
        // An edge of the top face, which face 0 (the bottom) does not touch.
        setEdge(grid, 4, 7, 1);
        assert.strictEqual(isClueSatisfied(grid, grid.faces.get(0)), true);
    });
});

describe('partitionFacesByLoop', () => {
    // The cube's bottom-face loop separates that one face from the other five.
    test('splits the surface in two, the loop being the only barrier', () => {
        const grid = makeCubeGrid();
        const {regions} = partitionFacesByLoop(grid, BOTTOM_LOOP);
        assert.strictEqual(regions.length, 2);
        const sizes = regions.map(r => r.length).sort((a, b) => a - b);
        assert.deepStrictEqual(sizes, [1, 5]);
        // The single-face region is the bottom, the face the loop encloses.
        assert.deepStrictEqual(regions.find(r => r.length === 1), [0]);
    });

    test('distance counts faces to the nearest boundary face', () => {
        const grid = makeCubeGrid();
        const {distance} = partitionFacesByLoop(grid, BOTTOM_LOOP);
        // The bottom face and all four sides touch the loop.
        assert.strictEqual(distance.get(0), 0);
        for (const side of [2, 3, 4, 5]) {
            assert.strictEqual(distance.get(side), 0, `face ${side}`);
        }
        // Only the top face is a step away from it.
        assert.strictEqual(distance.get(1), 1);
    });

    test('every face gets a region and a distance', () => {
        const grid = makeCubeGrid();
        const {regions, distance} = partitionFacesByLoop(grid, BOTTOM_LOOP);
        assert.strictEqual(regions.flat().length, grid.faces.size);
        assert.strictEqual(distance.size, grid.faces.size);
    });

    test('with no loop at all, one region and no NaN distances', () => {
        // Not a valid puzzle state, but the celebration must not divide by a
        // missing maximum if it ever sees one.
        const grid = makeCubeGrid();
        const {regions, distance} = partitionFacesByLoop(grid, []);
        assert.strictEqual(regions.length, 1);
        assert.strictEqual(regions[0].length, grid.faces.size);
        for (const d of distance.values()) assert.strictEqual(Number.isFinite(d), true);
    });
});

describe('checkSingleLoop', () => {
    test('empty board: noEdges', () => {
        const grid = makeCubeGrid();
        assert.deepStrictEqual(checkSingleLoop(grid), { ok: false, reason: 'noEdges' });
    });

    test('open path: incomplete, reporting the dead-end vertex', () => {
        const grid = makeCubeGrid();
        setEdge(grid, 0, 3, 1);
        setEdge(grid, 3, 2, 1); // path 0-3-2, ends dangling
        const result = checkSingleLoop(grid);
        assert.strictEqual(result.ok, false);
        assert.strictEqual(result.reason, 'incomplete');
        assert.ok([0, 2].includes(result.vertexId)); // one of the two dangling ends
    });

    test('one closed loop: ok, with its length', () => {
        const grid = makeCubeGrid();
        for (const [v1, v2] of loopVertexPairs(BOTTOM_LOOP)) setEdge(grid, v1, v2, 1);
        assert.deepStrictEqual(checkSingleLoop(grid), { ok: true, loopLength: 4 });
    });

    test('two disjoint loops: multipleLoops', () => {
        const grid = makeCubeGrid();
        for (const [v1, v2] of loopVertexPairs([0, 3, 2, 1])) setEdge(grid, v1, v2, 1); // bottom
        for (const [v1, v2] of loopVertexPairs([4, 5, 6, 7])) setEdge(grid, v1, v2, 1); // top
        const result = checkSingleLoop(grid);
        assert.strictEqual(result.ok, false);
        assert.strictEqual(result.reason, 'multipleLoops');
    });
});

describe('findSolutionMismatches', () => {
    test('correct marks and unknowns are never mismatches', () => {
        const grid = makeCubeGrid();
        setEdge(grid, 0, 3, 1);              // filled, on the solution loop
        setEdge(grid, 4, 5, 2);              // ruled out, not on the loop
        // All other edges unknown.
        assert.deepStrictEqual(findSolutionMismatches(grid, BOTTOM_LOOP), []);
    });

    test('a filled edge off the solution loop is a mismatch', () => {
        const grid = makeCubeGrid();
        const wrongId = setEdge(grid, 4, 5, 1); // top edge, not in bottom loop
        assert.deepStrictEqual(findSolutionMismatches(grid, BOTTOM_LOOP), [wrongId]);
    });

    test('a ruled-out edge on the solution loop is a mismatch', () => {
        const grid = makeCubeGrid();
        const wrongId = setEdge(grid, 0, 3, 2); // solution edge marked ruled-out
        assert.deepStrictEqual(findSolutionMismatches(grid, BOTTOM_LOOP), [wrongId]);
    });
});
