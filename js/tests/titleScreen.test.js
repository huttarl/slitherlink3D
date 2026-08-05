/**
 * Tests for the rule that decides whether a URL is a title screen or a board,
 * and which grid it loads. Pure query-string logic, so it runs headless; the
 * screen itself is covered by the browser suite (js/tests/mobile).
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import { DEFAULT_GRID, TITLE_SCREEN_GRID } from '../constants.js';
import { gridIdFromUrl, wantsHowToPlay, wantsTitleScreen } from '../titleScreen.js';

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

describe('gridIdFromUrl', () => {
    test('the title screen gets its own showy solid', () => {
        assert.strictEqual(gridIdFromUrl(''), TITLE_SCREEN_GRID);
    });

    test('the title solid is not the one the game starts on', () => {
        // The point of the pair: impressive for the title, simple to play.
        assert.notStrictEqual(TITLE_SCREEN_GRID, DEFAULT_GRID);
    });

    test('an explicit grid wins', () => {
        assert.strictEqual(gridIdFromUrl('?grid=bD'), 'bD');
    });

    test('a puzzle without a grid means the default grid, not the title one', () => {
        // ?puzzle=2 is a board request, so it must not load the title solid --
        // and the puzzle number refers to the default grid's list.
        assert.strictEqual(gridIdFromUrl('?puzzle=2'), DEFAULT_GRID);
    });
});

describe('wantsHowToPlay', () => {
    test('set by the title screen button, absent otherwise', () => {
        assert.strictEqual(wantsHowToPlay('?grid=T&howto=1'), true);
        assert.strictEqual(wantsHowToPlay('?grid=T'), false);
    });
});
