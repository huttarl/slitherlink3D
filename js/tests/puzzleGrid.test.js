/**
 * Unit tests for PuzzleGrid.js -- undo/redo history, reset, clear-errors,
 * and the checkUserSolution orchestration -- all headless (no THREE meshes,
 * no DOM; PuzzleGrid's observers and mesh lookups are null-safe by design).
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import { makeCubePuzzleGrid, setEdge, loopVertexPairs } from './helpers.js';

// Clues for the bottom-loop puzzle: bottom face = 4, top face = 0.
const CLUES = [4, 0, -1, -1, -1, -1];
const SOLUTION = [0, 3, 2, 1];

function makePuzzle() {
    return makeCubePuzzleGrid(CLUES, SOLUTION);
}

/** Fill the solution loop via the history-recording API. */
function fillSolution(pg) {
    for (const [v1, v2] of loopVertexPairs(SOLUTION)) {
        pg.setEdgeState(pg.findEdgeByVertices(v1, v2), 1);
    }
}

describe('puzzle setup', () => {
    test('applyCurrentPuzzleClues writes clues into face metadata', () => {
        const pg = makePuzzle();
        assert.strictEqual(pg.faces.get(0).metadata.clue, 4);
        assert.strictEqual(pg.faces.get(1).metadata.clue, 0);
        assert.strictEqual(pg.faces.get(2).metadata.clue, -1);
    });

    test('setCurrentPuzzle rejects out-of-range indices', () => {
        const pg = makePuzzle();
        assert.throws(() => pg.setCurrentPuzzle(1), /Invalid puzzle index/);
    });
});

describe('undo/redo history', () => {
    test('setEdgeState records a one-delta move and empties the redo stack', () => {
        const pg = makePuzzle();
        const edgeId = pg.findEdgeByVertices(0, 3);
        pg.setEdgeState(edgeId, 1);
        assert.strictEqual(pg.undoStack.length, 1);
        assert.deepStrictEqual(pg.undoStack[0], [{ edgeId, prevState: 0, newState: 1 }]);

        pg.undo();
        assert.strictEqual(pg.redoStack.length, 1);
        pg.setEdgeState(edgeId, 2); // a new move invalidates the undone one
        assert.strictEqual(pg.redoStack.length, 0);
    });

    test('undo restores the previous state; redo reapplies it', () => {
        const pg = makePuzzle();
        const edgeId = pg.findEdgeByVertices(0, 3);
        pg.setEdgeState(edgeId, 1);
        pg.setEdgeState(edgeId, 2);

        assert.strictEqual(pg.undo(), true);
        assert.strictEqual(pg.edges.get(edgeId).metadata.userGuess, 1);
        assert.strictEqual(pg.undo(), true);
        assert.strictEqual(pg.edges.get(edgeId).metadata.userGuess, 0);
        assert.strictEqual(pg.undo(), false); // history exhausted

        assert.strictEqual(pg.redo(), true);
        assert.strictEqual(pg.edges.get(edgeId).metadata.userGuess, 1);
    });

    test('onHistoryChanged observer fires on every history change', () => {
        const pg = makePuzzle();
        let calls = 0;
        pg.onHistoryChanged = () => calls++;
        const edgeId = pg.findEdgeByVertices(0, 3);
        pg.setEdgeState(edgeId, 1); // 1
        pg.undo();                  // 2
        pg.redo();                  // 3
        pg.resetPuzzle();           // 4
        assert.strictEqual(calls, 4);
    });
});

describe('the auto-rule-out setting', () => {
    // What the rules deduce is solutionChecker's business (see
    // findDeducibleRuleOuts there); what matters here is that a move and its
    // consequences travel through the history together.
    //
    // The position: fill the bottom edge 0-3, then 0-1. Vertex 0 then has its two
    // filled edges, so the vertical 0-4 can be ruled out -- one deduction, from the
    // second move.
    function playIntoADeduction(pg) {
        pg.setEdgeState(pg.findEdgeByVertices(0, 3), 1);
        pg.setEdgeState(pg.findEdgeByVertices(0, 1), 1);
    }

    test('the move and what it rules out are ONE history entry', () => {
        // The requirement the whole design turns on: were these recorded
        // separately, Undo would peel off the assistant's marks one at a time,
        // in an order the player never chose.
        const pg = makePuzzle();
        pg.autoRuleOut = true;
        playIntoADeduction(pg);

        assert.strictEqual(pg.undoStack.length, 2, 'two clicks, two entries');
        const move = pg.undoStack[1];
        assert.strictEqual(move.length, 2);
        // The player's own change comes first, and the deduced mark after it.
        assert.deepStrictEqual(move[0],
            {edgeId: pg.findEdgeByVertices(0, 1), prevState: 0, newState: 1});
        assert.deepStrictEqual(move[1],
            {edgeId: pg.findEdgeByVertices(0, 4), prevState: 0, newState: 2});
    });

    test('one undo takes back the move and its rule-outs; one redo restores them',
        () => {
            const pg = makePuzzle();
            pg.autoRuleOut = true;
            playIntoADeduction(pg);
            const guess = (v1, v2) =>
                pg.edges.get(pg.findEdgeByVertices(v1, v2)).metadata.userGuess;
            assert.strictEqual(guess(0, 4), 2, 'the vertical should be ruled out');

            pg.undo();
            assert.strictEqual(guess(0, 1), 0, 'the click should be taken back');
            assert.strictEqual(guess(0, 4), 0,
                'and the mark it caused with it, in the same press');
            assert.strictEqual(guess(0, 3), 1,
                'but not the move before it');

            pg.redo();
            assert.strictEqual(guess(0, 1), 1);
            assert.strictEqual(guess(0, 4), 2);
        });

    test('with the setting off, moves record exactly as they always did', () => {
        const pg = makePuzzle();            // autoRuleOut defaults to off
        assert.strictEqual(pg.autoRuleOut, false, 'it should be off by default');
        playIntoADeduction(pg);
        assert.strictEqual(pg.undoStack[1].length, 1);
        assert.strictEqual(
            pg.edges.get(pg.findEdgeByVertices(0, 4)).metadata.userGuess, 0,
            'nothing should have been ruled out');
    });

    test('a move that deduces nothing is still a plain one-delta move', () => {
        const pg = makePuzzle();
        pg.autoRuleOut = true;
        pg.setEdgeState(pg.findEdgeByVertices(0, 3), 1);   // the first move alone
        assert.strictEqual(pg.undoStack[0].length, 1);
    });
});

describe('resetPuzzle', () => {
    test('clears all guesses as one compound move; one undo restores them', () => {
        const pg = makePuzzle();
        const e1 = pg.findEdgeByVertices(0, 3);
        const e2 = pg.findEdgeByVertices(4, 5);
        pg.setEdgeState(e1, 1);
        pg.setEdgeState(e2, 2);

        pg.resetPuzzle();
        assert.strictEqual(pg.edges.get(e1).metadata.userGuess, 0);
        assert.strictEqual(pg.edges.get(e2).metadata.userGuess, 0);

        pg.undo(); // a single undo brings BOTH guesses back
        assert.strictEqual(pg.edges.get(e1).metadata.userGuess, 1);
        assert.strictEqual(pg.edges.get(e2).metadata.userGuess, 2);
    });

    test('on a pristine board, records no move', () => {
        const pg = makePuzzle();
        pg.resetPuzzle();
        assert.strictEqual(pg.undoStack.length, 0);
    });
});

describe('clearErrors', () => {
    test('clears only solution-contradicting guesses, as one undoable move', () => {
        const pg = makePuzzle();
        const right = pg.setEdgeState(pg.findEdgeByVertices(0, 3), 1); // correct fill
        const wrongFillId = pg.findEdgeByVertices(4, 5);   // top edge: not in solution
        const wrongRuleoutId = pg.findEdgeByVertices(2, 1); // solution edge
        pg.setEdgeState(wrongFillId, 1);
        pg.setEdgeState(wrongRuleoutId, 2);

        assert.strictEqual(pg.clearErrors(), 2);
        assert.strictEqual(pg.edges.get(wrongFillId).metadata.userGuess, 0);
        assert.strictEqual(pg.edges.get(wrongRuleoutId).metadata.userGuess, 0);
        // The correct guess is untouched.
        assert.strictEqual(pg.edges.get(pg.findEdgeByVertices(0, 3)).metadata.userGuess, 1);

        pg.undo(); // single undo restores both wrong marks
        assert.strictEqual(pg.edges.get(wrongFillId).metadata.userGuess, 1);
        assert.strictEqual(pg.edges.get(wrongRuleoutId).metadata.userGuess, 2);
    });

    test('with no errors, clears nothing and records no move', () => {
        const pg = makePuzzle();
        pg.setEdgeState(pg.findEdgeByVertices(0, 3), 1); // correct
        const movesBefore = pg.undoStack.length;
        assert.strictEqual(pg.clearErrors(), 0);
        assert.strictEqual(pg.undoStack.length, movesBefore);
    });
});

describe('checkUserSolution (active mode, headless)', () => {
    test('empty board: failed, no mismatches, clues unsatisfied', () => {
        const pg = makePuzzle();
        const result = pg.checkUserSolution(true);
        assert.strictEqual(result.status, 1);
        assert.deepStrictEqual(result.mismatchedEdgeIds, []);
        assert.ok(result.clueViolations.length > 0); // bottom clue 4 unmet
    });

    test('correct solution: solved, and onSolved observer fires', () => {
        const pg = makePuzzle();
        let solvedCalls = 0;
        pg.onSolved = () => solvedCalls++;
        fillSolution(pg);
        const result = pg.checkUserSolution(true);
        assert.strictEqual(result.status, 2);
        assert.strictEqual(solvedCalls, 1);
        assert.deepStrictEqual(result.mismatchedEdgeIds, []);
    });

    test('a wrong mark is counted but its location checks are spoiler-only data', () => {
        const pg = makePuzzle();
        fillSolution(pg);
        const wrongId = pg.findEdgeByVertices(4, 5);
        pg.setEdgeState(wrongId, 1);
        const result = pg.checkUserSolution(true);
        assert.strictEqual(result.status, 1);
        assert.deepStrictEqual(result.mismatchedEdgeIds, [wrongId]);
    });

    test('self-crossing vertex: failed without crashing (no meshes to highlight)', () => {
        const pg = makePuzzle();
        for (const edgeId of pg.vertices.get(0).edgeIDs) {
            pg.setEdgeState(edgeId, 1); // 3 filled edges at vertex 0
        }
        const result = pg.checkUserSolution(true);
        assert.strictEqual(result.status, 1);
        assert.deepStrictEqual(result.vertexViolations, [0]);
    });
});

describe('fillInSolution', () => {
    test('solves the board, and one undo puts it back', () => {
        const pg = makePuzzle();
        const changed = pg.fillInSolution();
        assert.strictEqual(changed, SOLUTION.length);   // the four bottom edges
        assert.strictEqual(pg.checkUserSolution(true).status, 2);   // solved
        // ONE move, so a single undo undoes the lot.
        assert.strictEqual(pg.undoStack.length, 1);
        pg.undo();
        assert.strictEqual(pg.hasAnyFilledEdges(), false);
    });

    test('clears a wrong filled edge, since it would fail the check', () => {
        const pg = makePuzzle();
        const wrongId = pg.findEdgeByVertices(4, 5);    // a top-face edge
        pg.setEdgeState(wrongId, 1);
        pg.fillInSolution();
        assert.strictEqual(pg.edges.get(wrongId).metadata.userGuess, 0);
        assert.strictEqual(pg.checkUserSolution(true).status, 2);
    });

    test('leaves ruled-out marks alone, so beat 1 still has something to fade', () => {
        const pg = makePuzzle();
        const ruledId = pg.findEdgeByVertices(4, 5);
        pg.setEdgeState(ruledId, 2);                    // 2 = ruled out
        pg.fillInSolution();
        assert.strictEqual(pg.edges.get(ruledId).metadata.userGuess, 2);
    });

    test('on an already-solved board, records no move', () => {
        const pg = makePuzzle();
        fillSolution(pg);
        const before = pg.undoStack.length;
        assert.strictEqual(pg.fillInSolution(), 0);
        assert.strictEqual(pg.undoStack.length, before);
    });
});

describe('isReadyToCheck', () => {
    test('an untouched board is not ready', () => {
        assert.strictEqual(makePuzzle().isReadyToCheck(), false);
    });

    test('a partial loop is not ready', () => {
        const pg = makePuzzle();
        // Three of the bottom loop's four edges: two dangling ends.
        pg.setEdgeState(pg.findEdgeByVertices(0, 3), 1);
        pg.setEdgeState(pg.findEdgeByVertices(3, 2), 1);
        pg.setEdgeState(pg.findEdgeByVertices(2, 1), 1);
        assert.strictEqual(pg.isReadyToCheck(), false);
    });

    test('a closed loop is ready', () => {
        const pg = makePuzzle();
        fillSolution(pg);
        assert.strictEqual(pg.isReadyToCheck(), true);
    });

    test('ready even when the clues are WRONG, which is the point', () => {
        // The top face's loop closes just as well as the bottom's, but the clues
        // (bottom 4, top 0) make it wrong. Readiness has to be about the drawing,
        // not the answer -- otherwise the highlight would only ever appear once
        // the puzzle was already solved.
        const pg = makePuzzle();
        for (const [v1, v2] of loopVertexPairs([4, 5, 6, 7])) {
            pg.setEdgeState(pg.findEdgeByVertices(v1, v2), 1);
        }
        assert.strictEqual(pg.isReadyToCheck(), true);
        assert.strictEqual(pg.checkUserSolution(true).status, 1); // and it fails
    });

    test('a crossing is not ready', () => {
        const pg = makePuzzle();
        for (const edgeId of pg.vertices.get(0).edgeIDs) {
            pg.setEdgeState(edgeId, 1); // 3 filled edges at vertex 0
        }
        assert.strictEqual(pg.isReadyToCheck(), false);
    });

    test('two separate loops are not ready', () => {
        const pg = makePuzzle();
        fillSolution(pg);                                   // bottom loop
        for (const [v1, v2] of loopVertexPairs([4, 5, 6, 7])) {
            pg.setEdgeState(pg.findEdgeByVertices(v1, v2), 1);   // and the top
        }
        assert.strictEqual(pg.isReadyToCheck(), false);
    });

    test('ruled-out edges do not make a board ready', () => {
        const pg = makePuzzle();
        for (const [v1, v2] of loopVertexPairs(SOLUTION)) {
            pg.setEdgeState(pg.findEdgeByVertices(v1, v2), 2);   // 2 = ruled out
        }
        assert.strictEqual(pg.isReadyToCheck(), false);
    });

    test('undoing back to empty stops being ready', () => {
        const pg = makePuzzle();
        fillSolution(pg);
        assert.strictEqual(pg.isReadyToCheck(), true);
        pg.undo();
        assert.strictEqual(pg.isReadyToCheck(), false);
    });
});

describe('checkUserSolution (passive mode)', () => {
    test('reports only local findings and never computes spoiler data', () => {
        const pg = makePuzzle();
        for (const edgeId of pg.vertices.get(0).edgeIDs) {
            pg.setEdgeState(edgeId, 1);
        }
        const someEdgeId = [...pg.vertices.get(0).edgeIDs][0];
        const edge = pg.edges.get(someEdgeId);
        const result = pg.checkUserSolution(false, null, edge);
        assert.strictEqual(result.status, 1);
        assert.deepStrictEqual(result.vertexViolations, [0]);
        assert.strictEqual(result.mismatchedEdgeIds, null); // spoilers not computed passively
        assert.strictEqual(result.loopCheck, null);         // loop not traced passively
    });
});
