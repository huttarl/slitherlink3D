/**
 * Tests for the rule that decides whether a URL is a title screen or a board,
 * and which grid it loads. Pure query-string logic, so it runs headless; the
 * screen itself is covered by the browser suite (js/tests/mobile).
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { CAMERA_DISTANCE, DEFAULT_GRID, TITLE_SCREEN_FALLBACK_GRID,
         TITLE_SCREEN_MIN_FACES } from '../constants.js';
import { chooseTitleScreenGrid, gridIdFromUrl, titleScreenCameraDistance,
         titleScreenCandidates, wantsHowToPlay,
         wantsTitleScreen } from '../titleScreen.js';

/** The real catalogue, for the tests that check the pick against the data. */
const here = dirname(fileURLToPath(import.meta.url));
const REAL_CATALOGUE = JSON.parse(
    readFileSync(join(here, '..', '..', 'data', 'grids.json'), 'utf8'));

/** Enough of a catalogue to pick from: two big solids, two too small, one
 *  big but with no puzzles. */
const CATALOGUE = {grids: [
    {file: 'T', faces: 4, numPuzzles: 1},
    {file: 'D', faces: 12, numPuzzles: 3},
    {file: 'O', faces: 8, numPuzzles: 3},
    {file: 'sD', faces: 92, numPuzzles: 3},
    {file: 'unbuilt', faces: 60, numPuzzles: 0},
]};

describe('wantsTitleScreen', () => {
    test('a cold launch: nothing asked for', () => {
        assert.strictEqual(wantsTitleScreen(''), true);
        assert.strictEqual(wantsTitleScreen('?'), true);
    });

    test('naming a grid or a puzzle goes straight to the board', () => {
        // Shared links, bookmarks, and everything the test suite loads.
        assert.strictEqual(wantsTitleScreen('?grid=aC'), false);
        assert.strictEqual(wantsTitleScreen('?puzzle=2'), false);
        assert.strictEqual(wantsTitleScreen('?grid=aC&puzzle=2'), false);
    });

    test('an unrelated parameter is still a cold launch', () => {
        // ?debug=1 or a tracking parameter shouldn't skip the title screen.
        assert.strictEqual(wantsTitleScreen('?debug=1'), true);
    });

    test('accepts URLSearchParams as well as a string', () => {
        assert.strictEqual(wantsTitleScreen(new URLSearchParams('?grid=T')), false);
        assert.strictEqual(wantsTitleScreen(new URLSearchParams('')), true);
    });
});

describe('choosing the title screen solid', () => {
    test('only the big solids are candidates', () => {
        const files = titleScreenCandidates(CATALOGUE).map(grid => grid.file);
        assert.deepStrictEqual(files, ['D', 'sD']);
    });

    test('a grid with no puzzles is never shown', () => {
        // 'unbuilt' is big enough, but there is nothing on it to show off.
        const files = titleScreenCandidates(CATALOGUE).map(grid => grid.file);
        assert.ok(!files.includes('unbuilt'));
    });

    test('picks by the given randomness, and stays in range', () => {
        // Both ends of random()'s [0, 1): the first candidate and the last.
        assert.strictEqual(chooseTitleScreenGrid(CATALOGUE, () => 0), 'D');
        assert.strictEqual(chooseTitleScreenGrid(CATALOGUE, () => 0.999), 'sD');
    });

    test('falls back rather than failing when nothing qualifies', () => {
        const tiny = {grids: [{file: 'T', faces: 4, numPuzzles: 1}]};
        assert.strictEqual(chooseTitleScreenGrid(tiny), TITLE_SCREEN_FALLBACK_GRID);
    });

    test('the real catalogue offers a decent choice', () => {
        // Guards the pick against the data: if the criteria ever left one solid
        // (or none), every launch would look the same and nobody would notice.
        const candidates = titleScreenCandidates(REAL_CATALOGUE);
        assert.ok(candidates.length >= 5,
                  `only ${candidates.length} solid(s) qualify for the title screen`);
        for (const grid of candidates) {
            assert.ok(grid.faces >= TITLE_SCREEN_MIN_FACES);
            assert.ok(grid.numPuzzles > 0);
        }
        // And the fallback is one of them, so it's a real grid that qualifies.
        assert.ok(candidates.some(grid => grid.file === TITLE_SCREEN_FALLBACK_GRID));
    });
});

describe('titleScreenCameraDistance', () => {
    test('a wide window gets a closer view than a board does', () => {
        const distance = titleScreenCameraDistance(1280 / 800);
        assert.ok(distance < CAMERA_DISTANCE,
                  `${distance} is no closer than a board's ${CAMERA_DISTANCE}`);
        // Close, but not so close that the solid is cropped: the whole
        // circumsphere still fits the 35-degree vertical field of view, which
        // wants 3.33 at this aspect.
        assert.ok(distance > 3.33, `${distance} would crop the solid`);
    });

    test('a tall screen is never pulled back past a board', () => {
        // A phone's narrow horizontal field of view would want ~7.7 to fit the
        // whole solid, which would be zooming OUT. Clamped instead.
        assert.strictEqual(titleScreenCameraDistance(375 / 812), CAMERA_DISTANCE);
    });

    test('the narrower the screen, the farther back -- up to the clamp', () => {
        // Monotonic in the aspect ratio, so no shape of window is a special case.
        const distances = [2, 1.5, 1, 0.8, 0.6].map(titleScreenCameraDistance);
        for (let i = 1; i < distances.length; i++) {
            assert.ok(distances[i] >= distances[i - 1],
                      `${distances[i]} < ${distances[i - 1]}`);
        }
    });
});

describe('gridIdFromUrl', () => {
    test('an explicit grid wins', async () => {
        assert.strictEqual(await gridIdFromUrl('?grid=bD'), 'bD');
    });

    test('a puzzle without a grid means the default grid, not the title one', async () => {
        // ?puzzle=2 is a board request, so it must not load the title solid --
        // and the puzzle number refers to the default grid's list.
        assert.strictEqual(await gridIdFromUrl('?puzzle=2'), DEFAULT_GRID);
    });

    // The cold-launch case isn't tested here: it fetches the catalogue, which
    // needs a server. The browser suite covers it (js/tests/mobile).

    test('the title solid is never the one the game starts on', () => {
        // The point of the pair: impressive for the title, simple to play. The
        // default grid is too small to be a candidate, which is what keeps them
        // apart no matter how the random pick falls.
        const files = titleScreenCandidates(REAL_CATALOGUE).map(grid => grid.file);
        assert.ok(!files.includes(DEFAULT_GRID));
    });
});

describe('wantsHowToPlay', () => {
    test('set by the title screen button, absent otherwise', () => {
        assert.strictEqual(wantsHowToPlay('?grid=T&howto=1'), true);
        assert.strictEqual(wantsHowToPlay('?grid=T'), false);
    });
});
