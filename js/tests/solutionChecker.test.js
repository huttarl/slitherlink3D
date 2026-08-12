/**
 * Unit tests for solutionChecker.js -- the pure rule/solution queries.
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import {
    countGuesses,
    findDeducibleRuleOuts,
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

describe('findDeducibleRuleOuts', () => {
    // Cube topology, for reading the expectations below: vertices 0-3 round the
    // bottom and 4-7 round the top, face 0 the bottom and face 1 the top, and each
    // vertex has exactly 3 edges -- two round its face and one vertical.

    /** The edge IDs of the given vertex pairs, as a set, for order-free compares. */
    function edgeSet(grid, pairs) {
        return new Set(pairs.map(([v1, v2]) => grid.findEdgeByVertices(v1, v2)));
    }

    test('a satisfied clue rules out the rest of its face', () => {
        const grid = makeCubeGrid();
        grid.faces.get(1).metadata.clue = 0;      // the top face wants no edges
        // Ruling out one of its edges doesn't change the count, but it is the move
        // that brings the player to the face, and a 0 clue was satisfied all along.
        const moved = setEdge(grid, 4, 5, 2);
        assert.deepStrictEqual(
            new Set(findDeducibleRuleOuts(grid, moved)),
            edgeSet(grid, [[5, 6], [6, 7], [7, 4]]));
    });

    test('one pass only: what it rules out, it does not then reason from', () => {
        // THE DESIGN DECISION, pinned down. After the three top edges go, vertex 4
        // has nothing filled and only the vertical left, so a chaining version
        // would take that too, and keep going round the solid. This asks for the
        // move's own consequences and stops.
        const grid = makeCubeGrid();
        grid.faces.get(1).metadata.clue = 0;
        const moved = setEdge(grid, 4, 5, 2);
        const first = findDeducibleRuleOuts(grid, moved);
        const verticals = edgeSet(grid, [[0, 4], [1, 5]]);
        assert.ok(!first.some(edgeId => verticals.has(edgeId)),
            'a single pass should not reach the verticals');

        // And the chain really is there -- so this is a decision, not an accident.
        for (const edgeId of first) grid.edges.get(edgeId).metadata.userGuess = 2;
        const second = findDeducibleRuleOuts(grid, moved);
        assert.deepStrictEqual(new Set(second), verticals,
            'the next pass is what a cascading version would have gone on to do');
    });

    test('two filled edges at a vertex rule out the rest', () => {
        const grid = makeCubeGrid();
        setEdge(grid, 0, 1, 1);
        const moved = setEdge(grid, 0, 3, 1);     // vertex 0 now has its two
        assert.deepStrictEqual(new Set(findDeducibleRuleOuts(grid, moved)),
            edgeSet(grid, [[0, 4]]));
    });

    test('a lone candidate at an untouched vertex is ruled out', () => {
        // Nothing filled here and only one edge left, and the loop cannot enter a
        // vertex and stop: it needs two edges or none.
        const grid = makeCubeGrid();
        setEdge(grid, 0, 1, 2);
        const moved = setEdge(grid, 0, 3, 2);
        assert.deepStrictEqual(new Set(findDeducibleRuleOuts(grid, moved)),
            edgeSet(grid, [[0, 4]]));
    });

    test('never the edge just moved, so cycling it back to unknown sticks', () => {
        // The trap this guards: vertex 0 has its two filled edges, and the player
        // clicks the third from ruled-out back to unknown. It is the only candidate
        // there, so the vertex rule would rule it out again on the spot and the
        // third click of the cycle would look broken.
        const grid = makeCubeGrid();
        setEdge(grid, 0, 1, 1);
        setEdge(grid, 0, 3, 1);
        const moved = setEdge(grid, 0, 4, 0);     // 0 = unknown again
        assert.deepStrictEqual(findDeducibleRuleOuts(grid, moved), []);
    });

    test('marks only unknown edges, and several rules can fire at once', () => {
        const grid = makeCubeGrid();
        grid.faces.get(0).metadata.clue = 2;
        setEdge(grid, 0, 3, 1);
        const moved = setEdge(grid, 3, 2, 1);
        // The clue is satisfied, so the bottom's other two edges go; and vertex 3
        // now has two filled, so its vertical goes as well.
        const deduced = findDeducibleRuleOuts(grid, moved);
        assert.deepStrictEqual(new Set(deduced),
            edgeSet(grid, [[2, 1], [1, 0], [3, 7]]));
        // The player's own filled edges are untouched -- a rule that wanted to rule
        // out a filled edge would be reporting a mistake, which is not this job.
        for (const edgeId of deduced) {
            assert.strictEqual(grid.edges.get(edgeId).metadata.userGuess, 0,
                'only unknown edges should be marked');
        }
    });

    test('deduces nothing from a position that is already wrong', () => {
        // Both rules ask for an exact count, so neither fires here. Burying a
        // mistake under marks that follow from it would be the worst kind of help.
        const threeAtAVertex = makeCubeGrid();
        setEdge(threeAtAVertex, 0, 1, 1);
        setEdge(threeAtAVertex, 0, 3, 1);
        const third = setEdge(threeAtAVertex, 0, 4, 1);   // 3 at vertex 0
        assert.deepStrictEqual(findDeducibleRuleOuts(threeAtAVertex, third), []);

        const overfilledClue = makeCubeGrid();
        overfilledClue.faces.get(0).metadata.clue = 1;
        setEdge(overfilledClue, 0, 3, 1);
        // Opposite edge, so no vertex gains a second filled edge either.
        const over = setEdge(overfilledClue, 2, 1, 1);
        assert.deepStrictEqual(findDeducibleRuleOuts(overfilledClue, over), []);
    });

    test('an unclued face says nothing, however its edges are marked', () => {
        const grid = makeCubeGrid();     // every clue is -1
        const moved = setEdge(grid, 0, 3, 1);
        assert.deepStrictEqual(findDeducibleRuleOuts(grid, moved), []);
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

    test('every face lands in exactly one region', () => {
        const grid = makeCubeGrid();
        const {regions} = partitionFacesByLoop(grid, BOTTOM_LOOP);
        assert.strictEqual(regions.flat().length, grid.faces.size);
        assert.strictEqual(new Set(regions.flat()).size, grid.faces.size);
    });

    test('with no loop at all, one region holding everything', () => {
        // Not a valid puzzle state, but the celebration must not be handed an
        // empty or ragged answer if it ever sees one.
        const grid = makeCubeGrid();
        const {regions} = partitionFacesByLoop(grid, []);
        assert.strictEqual(regions.length, 1);
        assert.strictEqual(regions[0].length, grid.faces.size);
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
