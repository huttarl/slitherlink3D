/**
 * Helpers for the phone-shaped tests.
 *
 * The app exposes no globals, but GameState is a singleton, so importing its
 * module inside the page hands back the very instance the app is using -- scene,
 * camera, grid and all. That's how these helpers reach in without the app
 * needing test hooks.
 */

/** Waits until the scene is built and the first frame has been drawn. */
export async function waitForScene(page) {
    await page.waitForFunction(async () => {
        const {GameState} = await import('/js/GameState.js');
        const sm = GameState.getInstance().getSceneManager();
        return !!(sm && sm.polyhedronMesh && sm.camera && sm.renderer);
    }, null, {timeout: 10_000});
}

/**
 * Is this element both displayed and fully inside the visible viewport?
 *
 * The distinction that matters on a phone: an element can be present, styled,
 * and carrying the right text while sitting below the fold. Asserting on
 * textContent (as an earlier round of manual checking did) says nothing about
 * whether a player can see it.
 */
export async function visibleWithinViewport(page, selector) {
    return await page.evaluate(sel => {
        const el = document.querySelector(sel);
        if (!el) return {found: false};
        const r = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
            found: true,
            rect: {top: Math.round(r.top), bottom: Math.round(r.bottom),
                   left: Math.round(r.left), right: Math.round(r.right),
                   width: Math.round(r.width), height: Math.round(r.height)},
            viewport: {width: window.innerWidth, height: window.innerHeight},
            rendered: r.width > 0 && r.height > 0 && style.visibility !== 'hidden'
                      && style.display !== 'none',
            insideViewport: r.top >= 0 && r.left >= 0
                            && r.bottom <= window.innerHeight + 1
                            && r.right <= window.innerWidth + 1,
            text: (el.textContent || '').replace(/\s+/g, ' ').trim(),
        };
    }, selector);
}

/**
 * Grows #canvas-container past the viewport, the way 100vh does on a real phone
 * (where it spans the area behind the browser's toolbars).
 *
 * Device emulation does not reproduce browser chrome, so this forces the
 * condition instead of hoping for it. It is what turned the check-toast bug
 * from invisible to obvious.
 */
export async function inflateCanvasContainer(page, extraPx = 120) {
    await page.evaluate(extra => {
        const c = document.getElementById('canvas-container');
        c.dataset.testOriginalHeight = c.style.height;
        c.style.height = (window.innerHeight + extra) + 'px';
    }, extraPx);
}

/** Undoes inflateCanvasContainer. */
export async function restoreCanvasContainer(page) {
    await page.evaluate(() => {
        const c = document.getElementById('canvas-container');
        c.style.height = c.dataset.testOriginalHeight || '';
        delete c.dataset.testOriginalHeight;
    });
}

/**
 * Fills in an edge that is NOT part of the solution, so a check has something
 * to complain about. Returns the edge id.
 */
export async function makeOneMistake(page) {
    return await page.evaluate(async () => {
        const {GameState} = await import('/js/GameState.js');
        const grid = GameState.getInstance().getPuzzleGrid();
        const loop = grid.getCurrentPuzzle().solution;
        const onLoop = new Set();
        for (let i = 0; i < loop.length; i++) {
            onLoop.add(grid.findEdgeByVertices(loop[i], loop[(i + 1) % loop.length]));
        }
        const wrong = [...grid.edges.keys()].find(id => !onLoop.has(id));
        grid.setEdgeState(wrong, 1);   // 1 = filled in
        return wrong;
    });
}

/** Sets every edge back to unknown, without disturbing the undo history. */
export async function clearAllMarks(page) {
    await page.evaluate(async () => {
        const {GameState} = await import('/js/GameState.js');
        const grid = GameState.getInstance().getPuzzleGrid();
        for (const [id, edge] of grid.edges) {
            if (edge.metadata.userGuess !== 0) grid.applyEdgeState(id, 0);
        }
    });
}

/**
 * Stops the tumble, so the camera holds still.
 *
 * Any test that works out a screen position and then aims at it needs this: the
 * tumble starts on load and turns at 30 deg/s, so between computing an edge's
 * coordinates and dispatching a tap the edge has moved and the tap misses. A
 * player doesn't hit that -- their press stops the tumble in the same instant
 * they aim -- but a test's two steps are hundreds of milliseconds apart.
 */
export async function stopTumbling(page) {
    await page.evaluate(async () => {
        const {GameState} = await import('/js/GameState.js');
        GameState.getInstance().getSceneManager().stopTumble();
    });
}

/** The guess state of one edge: 0 unknown, 1 filled in, 2 ruled out. */
export async function edgeState(page, edgeId) {
    return await page.evaluate(async id => {
        const {GameState} = await import('/js/GameState.js');
        return GameState.getInstance().getPuzzleGrid()
            .edges.get(id).metadata.userGuess;
    }, edgeId);
}

/**
 * Where an edge's midpoint lands on screen, in CSS pixels -- so a test can aim
 * a real tap at it rather than guessing coordinates.
 */
export async function edgeMidpointOnScreen(page, edgeId) {
    return await page.evaluate(async id => {
        const {GameState} = await import('/js/GameState.js');
        const gs = GameState.getInstance();
        const grid = gs.getPuzzleGrid();
        const camera = gs.getSceneManager().camera;
        const edge = grid.edges.get(id);
        const a = grid.vertices.get(edge.vertexIDs[0]).position;
        const b = grid.vertices.get(edge.vertexIDs[1]).position;
        const mid = a.clone().add(b).multiplyScalar(0.5).project(camera);
        return {x: Math.round((mid.x + 1) / 2 * window.innerWidth),
                y: Math.round((1 - mid.y) / 2 * window.innerHeight)};
    }, edgeId);
}

/** An edge facing the camera, which is therefore safe to aim a tap at. */
export async function someVisibleEdge(page) {
    return await page.evaluate(async () => {
        const {GameState} = await import('/js/GameState.js');
        const THREE = await import('/js/three/three.module.min.js');
        const gs = GameState.getInstance();
        const grid = gs.getPuzzleGrid();
        const camera = gs.getSceneManager().camera;
        for (const [id, edge] of grid.edges) {
            const facing = [...edge.faceIDs].some(fid => {
                const face = grid.faces.get(fid);
                const pts = face.vertexIDs.map(v => grid.vertices.get(v).position);
                const centroid = pts.reduce((acc, p) => acc.clone().add(p),
                                            new THREE.Vector3())
                    .multiplyScalar(1 / pts.length);
                const normal = new THREE.Vector3().subVectors(pts[1], pts[0])
                    .cross(new THREE.Vector3().subVectors(pts[2], pts[0])).normalize();
                if (normal.dot(centroid) < 0) normal.negate();
                return camera.position.clone().sub(centroid).dot(normal) > 0;
            });
            if (facing) return id;
        }
        return null;
    });
}

/**
 * A touch press of a given duration on the canvas.
 *
 * A quick tap goes through Playwright's own touchscreen, which is the most
 * faithful path. A HOLD can't: tap() is instantaneous and there is no
 * hold-then-release in that API, so the press is dispatched as pointer events
 * instead -- still the page's own event model, and what the long-press timer
 * listens to.
 *
 * @param {number} holdMs - 0 for a tap; longer than LONG_PRESS_MS for a hold
 * @param {{driftPx: number}} [options] - move the finger mid-press, to test
 *     that a drag (a camera rotation) cancels the long press
 */
export async function touchPress(page, x, y, holdMs = 0, options = {}) {
    const driftPx = options.driftPx || 0;
    if (holdMs === 0 && driftPx === 0) {
        await page.touchscreen.tap(x, y);
        return;
    }
    await page.evaluate(async ({x, y, holdMs, driftPx}) => {
        const canvas = document.querySelector('canvas');
        const opts = {clientX: x, clientY: y, pointerType: 'touch', bubbles: true,
                      isPrimary: true, buttons: 1, pointerId: 1};
        canvas.dispatchEvent(new PointerEvent('pointerdown', opts));
        if (driftPx) {
            canvas.dispatchEvent(new PointerEvent('pointermove',
                {...opts, clientX: x + driftPx, clientY: y - driftPx}));
        }
        await new Promise(r => setTimeout(r, holdMs));
        const endX = x + driftPx, endY = y - driftPx;
        canvas.dispatchEvent(new PointerEvent('pointerup',
            {...opts, clientX: endX, clientY: endY, buttons: 0}));
        canvas.dispatchEvent(new MouseEvent('click',
            {clientX: endX, clientY: endY, bubbles: true}));
    }, {x, y, holdMs, driftPx});
}

/** Collects console errors for a test to assert on. */
export function collectConsoleErrors(page) {
    const errors = [];
    page.on('console', msg => {
        if (msg.type() === 'error') errors.push(msg.text());
    });
    page.on('pageerror', err => errors.push(String(err)));
    return errors;
}
