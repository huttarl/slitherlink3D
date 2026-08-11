/**
 * Tests for the board's opening zoom.
 *
 * The movement itself needs a browser -- and note that requestAnimationFrame does
 * not run in a headless page here, so even Playwright cannot watch it. What can be
 * pinned down is the arithmetic: that the constants are consistent with the limits
 * the controls impose, and that stepping the animation by hand walks the camera's
 * distance from one end to the other without overshooting or moving the direction
 * it looks from.
 *
 * SceneManager is exercised directly, with a stub camera and controls, because the
 * zoom touches nothing else: it reads controls.target and writes camera.position.
 *
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import * as THREE from '../three/three.module.min.js';
import { CAMERA_DISTANCE, CAMERA_INTRO_FACTOR, CAMERA_INTRO_SECONDS,
         CAMERA_MAX_ZOOM, CAMERA_MIN_ZOOM } from '../constants.js';

// SceneManager's constructor hands its THREE.Timer to document, so that time
// doesn't accumulate while the tab is hidden. Nothing to do with the zoom, but it
// has to exist before the class can be built. Set before the import below, which is
// why that one is dynamic: a static import would be hoisted above this.
globalThis.document = {addEventListener() {}, removeEventListener() {}};
const { SceneManager } = await import('../SceneManager.js');

const START = CAMERA_DISTANCE * CAMERA_INTRO_FACTOR;

/**
 * A SceneManager with just enough of a camera and controls to zoom.
 * @param {THREE.Vector3} at - where to put the camera
 */
function managerLookingFrom(at) {
    const manager = new SceneManager();
    manager.camera = new THREE.PerspectiveCamera(35, 1);
    manager.camera.position.copy(at);
    manager.controls = {target: new THREE.Vector3(0, 0, 0)};
    return manager;
}

/** The camera's distance from the target. */
function distance(manager) {
    return manager.camera.position.distanceTo(manager.controls.target);
}

describe('the opening zoom constants', () => {
    test('it starts farther out than it finishes', () => {
        assert.ok(CAMERA_INTRO_FACTOR > 1,
            'a factor of 1 or less would zoom out, or not move at all');
        assert.ok(START > CAMERA_DISTANCE);
    });

    test('it starts inside the range the controls allow', () => {
        // The controls clamp the distance every frame, so a start beyond their
        // limit would be hauled back before the zoom was seen. This is the check
        // that keeps CAMERA_INTRO_FACTOR and CAMERA_MAX_ZOOM in step.
        assert.ok(START <= CAMERA_MAX_ZOOM,
            `starts at ${START}, but the controls cap the distance at `
            + `${CAMERA_MAX_ZOOM}`);
        assert.ok(CAMERA_DISTANCE >= CAMERA_MIN_ZOOM);
    });

    test('it is brief enough not to hold up play', () => {
        assert.ok(CAMERA_INTRO_SECONDS > 0 && CAMERA_INTRO_SECONDS < 3);
    });
});

describe('startIntroZoom', () => {
    test('puts the camera out at the starting distance straight away', () => {
        // Before any frame is drawn, or the board would appear at its normal
        // distance and then jump outward.
        const manager = managerLookingFrom(new THREE.Vector3(0, 0, CAMERA_DISTANCE));
        manager.startIntroZoom(START, CAMERA_DISTANCE);
        assert.ok(Math.abs(distance(manager) - START) < 1e-9);
        assert.strictEqual(manager.isIntroZooming, true);
    });

    test('keeps the direction it looks from, moving only the distance', () => {
        // The whole reason this composes with the tumble: the tumble owns the
        // direction, this owns the radius.
        const from = new THREE.Vector3(1, 2, 3).setLength(CAMERA_DISTANCE);
        const manager = managerLookingFrom(from);
        manager.startIntroZoom(START, CAMERA_DISTANCE);
        const moved = manager.camera.position.clone().normalize();
        assert.ok(moved.distanceTo(from.clone().normalize()) < 1e-9);
    });
});

describe('updateIntroZoom', () => {
    /** Run the zoom to completion in `steps` equal frames, collecting distances. */
    function runToEnd(steps) {
        const manager = managerLookingFrom(new THREE.Vector3(0, 0, CAMERA_DISTANCE));
        manager.startIntroZoom(START, CAMERA_DISTANCE);
        const seen = [distance(manager)];
        for (let i = 0; i < steps; i++) {
            manager.updateIntroZoom(CAMERA_INTRO_SECONDS / steps);
            seen.push(distance(manager));
        }
        return {manager, seen};
    }

    test('ends at exactly the normal distance, and stops', () => {
        const {manager, seen} = runToEnd(20);
        assert.ok(Math.abs(seen[seen.length - 1] - CAMERA_DISTANCE) < 1e-9);
        assert.strictEqual(manager.isIntroZooming, false);
    });

    test('closes in the whole way without ever backing off', () => {
        // Monotonic: an ease that overshot would pull the camera past its resting
        // distance and back, which reads as a bounce.
        const {seen} = runToEnd(30);
        for (let i = 1; i < seen.length; i++) {
            assert.ok(seen[i] <= seen[i - 1] + 1e-12,
                `distance grew at step ${i}: ${seen[i - 1]} -> ${seen[i]}`);
            assert.ok(seen[i] >= CAMERA_DISTANCE - 1e-9, 'overshot inward');
        }
    });

    test('eases: it moves less in the first and last frames than in the middle', () => {
        // What smoothstep buys, and the reason for it: no visible start or stop.
        const {seen} = runToEnd(10);
        const step = (i) => seen[i] - seen[i + 1];
        const middle = step(Math.floor(seen.length / 2) - 1);
        assert.ok(step(0) < middle, 'should start gently');
        assert.ok(step(seen.length - 2) < middle, 'should finish gently');
    });

    test('a long frame finishes the zoom rather than shooting past', () => {
        // A tab that was hidden, or a slow first frame, hands over a huge delta.
        const manager = managerLookingFrom(new THREE.Vector3(0, 0, CAMERA_DISTANCE));
        manager.startIntroZoom(START, CAMERA_DISTANCE);
        manager.updateIntroZoom(60);
        assert.ok(Math.abs(distance(manager) - CAMERA_DISTANCE) < 1e-9);
        assert.strictEqual(manager.isIntroZooming, false);
    });

    test('does nothing at all when no zoom is running', () => {
        const manager = managerLookingFrom(new THREE.Vector3(0, 0, 4));
        manager.updateIntroZoom(0.1);
        assert.strictEqual(distance(manager), 4);
    });

    test('stopIntroZoom leaves the camera where it had got to', () => {
        const manager = managerLookingFrom(new THREE.Vector3(0, 0, CAMERA_DISTANCE));
        manager.startIntroZoom(START, CAMERA_DISTANCE);
        manager.updateIntroZoom(CAMERA_INTRO_SECONDS / 2);
        const interrupted = distance(manager);
        manager.stopIntroZoom();
        manager.updateIntroZoom(CAMERA_INTRO_SECONDS);
        assert.strictEqual(distance(manager), interrupted);
        assert.ok(interrupted > CAMERA_DISTANCE && interrupted < START,
            'should have been caught partway');
    });
});
