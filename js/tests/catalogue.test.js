/**
 * Unit tests for catalogue.js -- walking the progression order.
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { groupGridsByFamily, nextPuzzleLocation, playableGrids } from '../catalogue.js';

/** A stand-in catalogue: only the fields nextPuzzleLocation reads. */
const CATALOGUE = {
    grids: [
        { file: 'T', numPuzzles: 1 },
        { file: 'cube', numPuzzles: 3 },
        { file: 'empty', numPuzzles: 0 },   // grid with no puzzle file yet
        { file: 'D', numPuzzles: 2 },
    ],
};

describe('playableGrids', () => {
    test('leaves out grids that have no puzzles', () => {
        assert.deepStrictEqual(playableGrids(CATALOGUE).map(g => g.file),
            ['T', 'cube', 'D']);
    });

    test('keeps catalogue (progression) order', () => {
        const files = playableGrids(CATALOGUE).map(g => g.file);
        assert.deepStrictEqual(files, ['T', 'cube', 'D']);
    });

    test('keeps the current grid even when it has no puzzles', () => {
        // Reachable with an explicit ?grid=empty. Dropping it would leave the
        // picker naming a different polyhedron than the one on screen.
        assert.deepStrictEqual(playableGrids(CATALOGUE, 'empty').map(g => g.file),
            ['T', 'cube', 'empty', 'D']);
    });

    test('does not duplicate the current grid when it has puzzles', () => {
        assert.deepStrictEqual(playableGrids(CATALOGUE, 'cube').map(g => g.file),
            ['T', 'cube', 'D']);
    });

    test('agrees with nextPuzzleLocation about which grids exist', () => {
        // Both skip empty grids; if they disagreed, Next could land on a grid
        // the picker refuses to show, or vice versa.
        const reachable = new Set();
        let at = { file: 'T', puzzle: 1 };
        reachable.add(at.file);
        while (at) {
            at = nextPuzzleLocation(CATALOGUE, at.file, at.puzzle);
            if (at) reachable.add(at.file);
        }
        assert.deepStrictEqual([...reachable],
            playableGrids(CATALOGUE).map(g => g.file));
    });

    test('handles a catalogue with nothing playable', () => {
        const barren = { grids: [{ file: 'a', numPuzzles: 0 }] };
        assert.deepStrictEqual(playableGrids(barren), []);
    });
});

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

/** Catalogue entries with the categories the real data carries. */
const CATEGORIZED = [
    { file: 'T', categories: ['Platonic solid', 'deltahedron'] },
    { file: 'J1', categories: ['Johnson solid'] },
    { file: 'aC', categories: ['Archimedean solid', 'quasiregular polyhedron'] },
    { file: 'cube', categories: ['Platonic solid', 'parallelohedron'] },
    { file: 'tI', categories: ['Archimedean solid'] },
];

describe('groupGridsByFamily', () => {
    test('groups by family, in the order a player meets them', () => {
        assert.deepStrictEqual(
            groupGridsByFamily(CATEGORIZED).map(g => [g.label, g.grids.map(x => x.file)]),
            [['Platonic solids', ['T', 'cube']],
             ['Archimedean solids', ['aC', 'tI']],
             ['Johnson solids', ['J1']]]);
    });

    test('a family wins over a cross-cutting category', () => {
        // The tetrahedron is a Platonic solid AND a deltahedron; it belongs
        // under the family, not in a deltahedron group of its own.
        const groups = groupGridsByFamily(CATEGORIZED);
        assert.ok(!groups.some(g => g.family === 'deltahedron'));
    });

    test('keeps catalogue order within a group', () => {
        const platonic = groupGridsByFamily(CATEGORIZED)[0];
        assert.deepStrictEqual(platonic.grids.map(g => g.file), ['T', 'cube']);
    });

    test('an unknown category becomes its own group, after the known families', () => {
        // So adding a family to the data shows up immediately, rather than
        // being silently lumped in with something else.
        const grids = [...CATEGORIZED, { file: 'x', categories: ['zonohedron'] }];
        const labels = groupGridsByFamily(grids).map(g => g.label);
        assert.deepStrictEqual(labels, ['Platonic solids', 'Archimedean solids',
                                        'Johnson solids', 'Zonohedra']);
    });

    test('-hedron pluralizes to -hedra', () => {
        const groups = groupGridsByFamily([{ file: 'x', categories: ['zonohedron'] }]);
        assert.strictEqual(groups[0].label, 'Zonohedra');
    });

    test('a grid with no categories still lands somewhere', () => {
        const groups = groupGridsByFamily([{ file: 'x' }, { file: 'y', categories: [] }]);
        assert.deepStrictEqual(groups.map(g => [g.label, g.grids.length]),
                               [['Others', 2]]);
    });

    test('an empty list gives no groups', () => {
        assert.deepStrictEqual(groupGridsByFamily([]), []);
    });
});

/**
 * Conventions for the `categories` in the real data (data/<grid>.json, gathered
 * into data/grids.json by util/build_catalogue.py).
 */
describe('the catalogue\'s categories', () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const catalogue = JSON.parse(
        readFileSync(join(here, '..', '..', 'data', 'grids.json'), 'utf8'));

    // Where one category implies another, only the narrower is listed: the
    // broader is a click away on the narrower one's page, and the card has
    // little room. Every parallelohedron is a zonohedron, so the cube is listed
    // as a parallelohedron and leaves it at that.
    // Goldberg implies fullerene for the same reason: a Goldberg polyhedron is the
    // fullerene cage with icosahedral symmetry, so tI and cD say 'Goldberg' and
    // stop, while C70 and C26 -- which have no (m,n) -- say 'fullerene'.
    const IMPLIES = [['parallelohedron', 'zonohedron'],
                     ['Goldberg', 'fullerene']];

    test('no grid lists both a category and one it implies', () => {
        const redundant = [];
        for (const grid of catalogue.grids) {
            const categories = grid.categories || [];
            for (const [narrow, broad] of IMPLIES) {
                if (categories.includes(narrow) && categories.includes(broad)) {
                    redundant.push(`${grid.gridId}: ${narrow} implies ${broad}`);
                }
            }
        }
        assert.deepStrictEqual(redundant, []);
    });

    test('every grid names exactly one family', () => {
        // The picker groups by family, and a grid in two of them would have to
        // be filed under one arbitrarily.
        const FAMILIES = ['Platonic solid', 'Archimedean solid', 'Catalan solid',
                          'Johnson solid', 'Miscellaneous'];
        for (const grid of catalogue.grids) {
            const families = (grid.categories || [])
                .filter(category => FAMILIES.includes(category));
            assert.strictEqual(families.length, 1,
                `${grid.gridId} has families ${JSON.stringify(families)}`);
        }
    });
});
