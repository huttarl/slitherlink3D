/**
 * Unit tests for catalogue.js -- walking the progression order.
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import { nextPuzzleLocation } from '../catalogue.js';

/** A stand-in catalogue: only the fields nextPuzzleLocation reads. */
const CATALOGUE = {
    grids: [
        { file: 'T', numPuzzles: 1 },
        { file: 'cube', numPuzzles: 3 },
        { file: 'empty', numPuzzles: 0 },   // grid with no puzzle file yet
        { file: 'D', numPuzzles: 2 },
    ],
};

describe('nextPuzzleLocation', () => {
    test('advances within a grid that has more puzzles', () => {
        assert.deepStrictEqual(nextPuzzleLocation(CATALOGUE, 'cube', 1),
            { file: 'cube', puzzle: 2 });
        assert.deepStrictEqual(nextPuzzleLocation(CATALOGUE, 'cube', 2),
            { file: 'cube', puzzle: 3 });
    });

    test('moves to the next grid after a grid\'s last puzzle', () => {
        assert.deepStrictEqual(nextPuzzleLocation(CATALOGUE, 'T', 1),
            { file: 'cube', puzzle: 1 });
    });

    test('skips grids that have no puzzles', () => {
        // After cube's last puzzle comes 'empty' (0 puzzles), so expect 'D'.
        assert.deepStrictEqual(nextPuzzleLocation(CATALOGUE, 'cube', 3),
            { file: 'D', puzzle: 1 });
    });

    test('returns null at the end of the catalogue', () => {
        assert.strictEqual(nextPuzzleLocation(CATALOGUE, 'D', 2), null);
    });

    test('returns null for a grid that is not in the catalogue', () => {
        assert.strictEqual(nextPuzzleLocation(CATALOGUE, 'nonesuch', 1), null);
    });

    test('treats an out-of-range puzzle number as being at the grid\'s end', () => {
        // GameState clamps such a request to the last puzzle, so "next"
        // should move on to the following grid rather than overshooting.
        assert.deepStrictEqual(nextPuzzleLocation(CATALOGUE, 'cube', 99),
            { file: 'D', puzzle: 1 });
    });

    test('a catalogue whose last grids have no puzzles still ends cleanly', () => {
        const trailing = { grids: [{ file: 'a', numPuzzles: 1 },
                                   { file: 'b', numPuzzles: 0 }] };
        assert.strictEqual(nextPuzzleLocation(trailing, 'a', 1), null);
    });
});
