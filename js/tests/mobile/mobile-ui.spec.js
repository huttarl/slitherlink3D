/**
 * Phone-shaped tests: layout that only misbehaves at phone size, and input that
 * only exists on touch.
 *
 * Each test here corresponds to a bug this project actually shipped. The
 * default (jsdom-free, browser-free) suite cannot see any of them, because they
 * are all about where things land on screen or how touch events sequence.
 */
import { test, expect } from '@playwright/test';
import {
    clearAllMarks, collectConsoleErrors, edgeMidpointOnScreen, edgeState,
    inflateCanvasContainer, makeOneMistake, restoreCanvasContainer,
    someVisibleEdge, touchPress, visibleWithinViewport, waitForScene,
} from './helpers.js';

const LONG_PRESS_MS = 500;   // keep in step with js/constants.js

/**
 * Loads the default puzzle and waits for the scene.
 *
 * Deliberately NOT a top-level beforeEach: the tests that navigate somewhere
 * else themselves (the smoke tests, the slow-load test) would then build a
 * whole scene twice, and on an emulated phone with several workers competing
 * for the CPU that was enough to blow the timeout.
 */
async function openDefaultPuzzle(page) {
    await page.goto('/main.html');
    await waitForScene(page);
}

test.describe('check results reach the player', () => {
    test.beforeEach(({page}) => openDefaultPuzzle(page));
    test('a mistake is reported somewhere visible', async ({page}) => {
        await makeOneMistake(page);
        await page.getByRole('button', {name: /check/i}).click();

        // Either channel is acceptable -- the toast when the panel is collapsed,
        // the drawer's line when it's open -- but one of them has to be both
        // rendered AND on screen.
        const toast = await visibleWithinViewport(page, '#checkToast');
        const drawer = await visibleWithinViewport(page, '#checkFeedback');
        const shown = [toast, drawer].filter(r => r.found && r.rendered);
        expect(shown.length,
            'neither the toast nor the drawer feedback was rendered').toBeGreaterThan(0);
        for (const r of shown) {
            expect(r.insideViewport,
                `check result is rendered but off screen: ${JSON.stringify(r.rect)} `
                + `in a ${JSON.stringify(r.viewport)} viewport`).toBe(true);
        }
        expect(shown.map(r => r.text).join(' ')).toMatch(/match the solution/i);
    });

    test('stays on screen when the container is taller than the viewport',
        async ({page}) => {
            // The regression for the shipped bug: #checkToast was position:
            // absolute inside #canvas-container, which is 100vh tall. On a phone
            // 100vh spans the area behind the browser's toolbars, so the toast
            // sat ~110px below the fold and tapping Check appeared to do nothing.
            // Device emulation doesn't reproduce browser chrome, so force the
            // condition: make the container taller and insist the toast ignores
            // it, which only position: fixed does.
            await makeOneMistake(page);
            await inflateCanvasContainer(page, 120);
            await page.getByRole('button', {name: /check/i}).click();

            const toast = await visibleWithinViewport(page, '#checkToast');
            if (toast.found && toast.rendered) {
                expect(toast.insideViewport,
                    'the toast follows #canvas-container past the bottom of the '
                    + 'screen -- it needs position: fixed, not absolute').toBe(true);
            }
            await restoreCanvasContainer(page);
        });
});

test.describe('touch input', () => {
    test.beforeEach(({page}) => openDefaultPuzzle(page));

    // Phone project only. Not merely because touchscreen.tap needs a
    // touch-capable context, but because the behaviour under test is
    // touch-specific by design: long press is offered to fingers and pens and
    // withheld from a mouse, which has a shift key. Driving these with a mouse
    // would assert the opposite of what the code intends.
    test.skip(({hasTouch}) => !hasTouch, 'needs a touch-capable context');

    test('a tap cycles an edge forward', async ({page}) => {
        const edgeId = await someVisibleEdge(page);
        expect(edgeId, 'no camera-facing edge found').not.toBeNull();
        await clearAllMarks(page);
        const {x, y} = await edgeMidpointOnScreen(page, edgeId);

        await touchPress(page, x, y, 0);
        expect(await edgeState(page, edgeId),
            'a tap on an edge should fill it in').toBe(1);
    });

    test('a long press cycles an edge backward', async ({page}) => {
        // The touch stand-in for shift+click, a phone having no shift key.
        const edgeId = await someVisibleEdge(page);
        await clearAllMarks(page);
        const {x, y} = await edgeMidpointOnScreen(page, edgeId);

        await touchPress(page, x, y, LONG_PRESS_MS + 200);
        expect(await edgeState(page, edgeId),
            'a long press should step backward to ruledOut, and the click that '
            + 'follows the release must not cycle it on again').toBe(2);
    });

    test('holding while dragging does nothing: that is a camera rotation',
        async ({page}) => {
            const edgeId = await someVisibleEdge(page);
            await clearAllMarks(page);
            const {x, y} = await edgeMidpointOnScreen(page, edgeId);

            await touchPress(page, x, y, LONG_PRESS_MS + 200, {driftPx: 40});
            expect(await edgeState(page, edgeId),
                'a press that wanders is a drag, so no mark should be made')
                .toBe(0);
        });
});

test.describe('the collapsed panel', () => {
    // No shared navigation: the first test here drives its own slowed-down load.
    test('never paints expanded on a phone, even on a slow load',
        async ({page}, testInfo) => {
            // The panel used to come up full-size and snap to the strip once
            // loading finished, because the JS that collapses it only ran after
            // the grid and puzzle JSON had been fetched and the geometry built.
            // main.html now collapses it in a synchronous inline script, before
            // the first paint, and main.js moves the strip's buttons before the
            // slow work rather than after.
            //
            // Holding the JSON back exaggerates a slow phone connection, so the
            // window where the old code showed the wrong layout is wide open. A
            // fast local server would hide the bug.
            await page.route('**/data/*.json', async route => {
                await new Promise(r => setTimeout(r, 800));
                await route.continue();
            });

            const wantCollapsed = testInfo.project.name === 'phone';
            const samples = [];
            const navigation = page.goto('/main.html', {waitUntil: 'commit'});
            for (let i = 0; i < 8; i++) {
                await page.waitForTimeout(120);
                samples.push(await page.evaluate(() => {
                    const info = document.getElementById('info');
                    if (!info) return null;
                    return {collapsed: info.classList.contains('collapsed'),
                            width: Math.round(info.getBoundingClientRect().width),
                            boardUp: !!document.querySelector('canvas')};
                }).catch(() => null));
            }
            await navigation;

            const seen = samples.filter(Boolean);
            expect(seen.length, 'never managed to sample the panel').toBeGreaterThan(3);
            expect(seen.some(s => s.boardUp),
                'the board never appeared, so the slow-load window was missed')
                .toBe(true);
            for (const s of seen) {
                expect(s.collapsed,
                    `panel was ${s.collapsed ? 'collapsed' : 'EXPANDED'} mid-load; `
                    + `samples: ${JSON.stringify(seen)}`).toBe(wantCollapsed);
            }
            // And the strip mustn't visibly resize as its buttons arrive --
            // hence the fixed width on #info.collapsed. Collapsed only: the
            // expanded panel is content-sized, so it legitimately grows a little
            // when the polyhedron picker's options arrive from grids.json.
            if (wantCollapsed) {
                const widths = new Set(seen.map(s => s.width));
                expect(widths.size,
                    `the strip changed width during loading: ${[...widths].join(', ')}`)
                    .toBe(1);
            }
        });

    // The rest want an ordinary, fully-loaded page.
    test.describe('once loaded', () => {
    test.beforeEach(({page}) => openDefaultPuzzle(page));

    test('starts collapsed on a phone and expanded on a desktop',
        async ({page}, testInfo) => {
            const collapsed = await page.evaluate(() =>
                document.getElementById('info').classList.contains('collapsed'));
            expect(collapsed).toBe(testInfo.project.name === 'phone');
        });

    test('every strip control is on screen', async ({page}) => {
        // The strip is the whole point on a phone; a control hanging off the
        // edge would be unusable, and the panel once ran into the debug panel.
        for (const selector of ['#panelToggle', '#whereAmI', '#checkSolution',
                                '#undoMove', '#redoMove']) {
            const box = await visibleWithinViewport(page, selector);
            if (!box.rendered) continue;   // hidden in this state, fine
            expect(box.insideViewport,
                `${selector} is outside the viewport: ${JSON.stringify(box.rect)}`)
                .toBe(true);
        }
    });

    test('the panel and the debug panel do not overlap', async ({page}) => {
        const overlap = await page.evaluate(() => {
            const a = document.getElementById('info').getBoundingClientRect();
            const b = document.querySelector('.debugging').getBoundingClientRect();
            return !(a.right < b.left || b.right < a.left
                     || a.bottom < b.top || b.bottom < a.top);
        });
        expect(overlap, 'the info panel and the debug panel overlap').toBe(false);
    });
    });
});

test.describe('smoke', () => {
    for (const grid of ['T', 'cube', 'tI']) {
        test(`${grid} loads and renders without console errors`, async ({page}) => {
            const errors = collectConsoleErrors(page);
            await page.goto(`/main.html?grid=${grid}`);
            await waitForScene(page);
            // A frame has to have been drawn, not just the scene assembled: a
            // throw in the render loop leaves a black screen and no errors here.
            const framesAdvanced = await page.evaluate(async () => {
                const {GameState} = await import('/js/GameState.js');
                const sm = GameState.getInstance().getSceneManager();
                const before = sm.renderer.info.render.frame;
                await new Promise(r => setTimeout(r, 300));
                return sm.renderer.info.render.frame - before;
            });
            expect(framesAdvanced,
                'the render loop is not running').toBeGreaterThan(0);
            expect(errors).toEqual([]);
        });
    }
});
