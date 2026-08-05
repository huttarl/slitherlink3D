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
    expandPanel, inflateCanvasContainer, makeOneMistake, restoreCanvasContainer,
    someVisibleEdge, solvePuzzle, stopTumbling, touchPress,
    visibleWithinViewport, waitForScene,
} from './helpers.js';
// The app's own value, rather than a copy that would drift out of step with it.
// (constants.js pulls in THREE, which imports fine under Node -- the headless
// unit tests do the same.)
import { LONG_PRESS_MS } from '../../constants.js';

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
    // Hold the camera still: these tests aim at coordinates worked out a moment
    // earlier, and the tumble would have moved the target by then. See
    // stopTumbling.
    test.beforeEach(async ({page}) => {
        await openDefaultPuzzle(page);
        await stopTumbling(page);
    });

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

test.describe('the tumble', () => {
    // These are the tests that need a real browser most of all: the tumble is
    // driven by the render loop, whose Timer is connected to the Page Visibility
    // API, so it only advances when the page is genuinely visible. Poking at it
    // from a hidden context yields zero deltas and a camera that never moves.
    test.beforeEach(({page}) => openDefaultPuzzle(page));

    /** Where the camera is, as a direction from the target. */
    const viewpoint = page => page.evaluate(async () => {
        const {GameState} = await import('/js/GameState.js');
        const sm = GameState.getInstance().getSceneManager();
        const d = sm.camera.position.clone().sub(sm.controls.target).normalize();
        return {x: d.x, y: d.y, z: d.z, tumbling: sm.isTumbling};
    });

    const degreesApart = (a, b) => {
        const dot = Math.min(1, Math.max(-1, a.x * b.x + a.y * b.y + a.z * b.z));
        return Math.acos(dot) * 180 / Math.PI;
    };

    test('starts by itself when the puzzle loads', async ({page}) => {
        const before = await viewpoint(page);
        expect(before.tumbling, 'the tumble should be running on load').toBe(true);
        await page.waitForTimeout(1500);
        const after = await viewpoint(page);
        // 30 deg/s, easing in over the first second, so well over a degree.
        expect(degreesApart(before, after),
            'the view should have moved on its own').toBeGreaterThan(5);
    });

    test('any press on the board stops it, drag or click', async ({page}) => {
        const canvas = page.locator('canvas');
        const box = await canvas.boundingBox();
        // A plain click, no movement: the point is that a tap counts too, not
        // just a drag.
        await page.mouse.click(Math.round(box.x + box.width * 0.8),
                              Math.round(box.y + box.height * 0.2));

        expect((await viewpoint(page)).tumbling,
            'a press on the board should hand the view back to the player')
            .toBe(false);

        // And it stays put afterwards.
        const settled = await viewpoint(page);
        await page.waitForTimeout(700);
        expect(degreesApart(settled, await viewpoint(page)),
            'the view should be still once the tumble has been stopped')
            .toBeLessThan(0.5);
    });

    test('keeps the camera aimed at the solid while it runs', async ({page}) => {
        // The position is derived from the orientation, so this should hold by
        // construction rather than by correction -- worth pinning, since an
        // aiming bug would be invisible in a still screenshot.
        await page.waitForTimeout(1200);
        const aimErrorDeg = await page.evaluate(async () => {
            const {GameState} = await import('/js/GameState.js');
            const THREE = await import('/js/three/three.module.min.js');
            const sm = GameState.getInstance().getSceneManager();
            const toTarget = sm.controls.target.clone()
                .sub(sm.camera.position).normalize();
            const forward = new THREE.Vector3(0, 0, -1)
                .applyQuaternion(sm.camera.quaternion);
            return forward.angleTo(toTarget) * 180 / Math.PI;
        });
        expect(aimErrorDeg).toBeLessThan(0.5);
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

    test('expanding the panel keeps it on screen', async ({page}) => {
        // The expanded drawer has a FIXED width (480px), wide enough that the
        // About card's lines mostly don't wrap. That's more than a phone has, so
        // it leans on max-width: calc(100vw - 20px); without that the panel and
        // its pickers would hang off the right edge. Long name loaded, since the
        // polyhedron select is the widest thing in there.
        await page.goto('/main.html?grid=bD');
        await waitForScene(page);
        await expandPanel(page);
        await page.locator('#aboutSolidToggle').click();

        for (const selector of ['#info', '#gridSelect', '#aboutSolidToggle',
                                '#aboutSolid', '#nextPuzzle']) {
            const box = await visibleWithinViewport(page, selector);
            expect(box.rendered, `${selector} is not shown`).toBe(true);
            expect(box.insideViewport,
                `${selector} hangs off the screen: ${JSON.stringify(box.rect)} in `
                + `a ${JSON.stringify(box.viewport)} viewport`).toBe(true);
        }
    });

    test('the solid and its categories share the card\'s first line',
        async ({page}) => {
            // "Cuboctahedron — Archimedean solid · quasiregular polyhedron", not
            // a line each. Asserted on the categories' FIRST line box, since the
            // run may well wrap after that on a narrow card -- and asserted here
            // rather than in the browser pane, whose zero-width layout reports
            // every box as being on its own line.
            await page.goto('/main.html?grid=aC');
            await waitForScene(page);
            await expandPanel(page);
            await page.locator('#aboutSolidToggle').click();

            const heading = await page.evaluate(() => {
                const card = document.getElementById('aboutSolid');
                const name = card.querySelector('.about-name').getClientRects()[0];
                const categories =
                    card.querySelector('.about-categories').getClientRects()[0];
                if (!name || !categories) return null;
                return {sameLine: Math.abs(name.top - categories.top) < 2,
                        toTheRight: categories.left >= name.right};
            });
            expect(heading, 'the card heading has no layout boxes').not.toBeNull();
            expect(heading.sameLine,
                'the categories are not on the same line as the name').toBe(true);
            expect(heading.toTheRight,
                'the categories do not start to the right of the name').toBe(true);
        });

    test('the About toggle stays on the picker row', async ({page}) => {
        // It used to wrap onto a line of its own once the polyhedron name was
        // long. The row is flex now, so the select gives up width instead.
        await page.goto('/main.html?grid=bD');
        await waitForScene(page);
        await expandPanel(page);

        const sameRow = await page.evaluate(() => {
            const select = document.getElementById('gridSelect').getBoundingClientRect();
            const about = document.getElementById('aboutSolidToggle').getBoundingClientRect();
            return {vertical: Math.abs(select.top - about.top) < select.height,
                    beside: about.left >= select.right - 1};
        });
        expect(sameRow.vertical,
            'the About button is not on the same line as the polyhedron select')
            .toBe(true);
        expect(sameRow.beside, 'the About button is not to the right of the select')
            .toBe(true);
    });
    });
});

test.describe('the celebration overlay', () => {
    test.beforeEach(({page}) => openDefaultPuzzle(page));

    test('Next puzzle stays on screen with the About card below it',
        async ({page}) => {
            // The About-this-solid card is deliberately BELOW the Next button
            // (see aboutSolid.js): many players want to move straight on, and on
            // a phone anything added above the button pushes it toward the fold.
            // This is the guard on that ordering.
            await solvePuzzle(page);
            await page.getByRole('button', {name: /check/i}).click();

            const next = await visibleWithinViewport(page, '#overlayNextPuzzle');
            expect(next.rendered, 'the Next puzzle button is not shown').toBe(true);
            expect(next.insideViewport,
                `Next puzzle is off screen: ${JSON.stringify(next.rect)} in a `
                + `${JSON.stringify(next.viewport)} viewport -- has something been `
                + 'added above it in the overlay?').toBe(true);

            const card = await visibleWithinViewport(page, '#overlayAboutSolid');
            expect(card.rendered, 'the About card is missing').toBe(true);
            expect(card.rect.top,
                'the About card must sit below the Next button')
                .toBeGreaterThanOrEqual(next.rect.bottom);
            // It says something real about the solid on screen.
            expect(card.text).toMatch(/vertices, \d+ edges/);
        });

    test('the whole overlay fits the screen', async ({page}) => {
        await solvePuzzle(page);
        await page.getByRole('button', {name: /check/i}).click();
        const box = await visibleWithinViewport(page, '.message-box');
        expect(box.rendered).toBe(true);
        expect(box.insideViewport,
            `the celebration box overflows the screen: ${JSON.stringify(box.rect)} `
            + `in a ${JSON.stringify(box.viewport)} viewport`).toBe(true);
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
