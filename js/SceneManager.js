import * as THREE from './three/three.module.min.js';
import { OrbitControls } from './three/OrbitControls.js';
import { TrackballControls } from './three/TrackballControls.js';
import {CAMERA_MAX_ZOOM, CAMERA_MIN_ZOOM, LEVEL_CAMERA_SECONDS,
        TRACKBALL_DAMPING, TRACKBALL_ROTATE_SPEED,
        TUMBLE_DEGREES_PER_SEC} from "./constants.js";

// The direction levelCamera() restores as "up", and the reference the tumble
// carries along with the camera. Module-level so it isn't rebuilt every frame.
const WORLD_UP = new THREE.Vector3(0, 1, 0);

// "Very irrational", so two rates in this ratio keep out of step indefinitely
// and the tumble's path never closes on itself.
const GOLDEN_RATIO = 1.618033;

// How fast the tumble turns, and how fast it sweeps between the poles. The
// ratio matters more than the values: 1:1/phi^2 is irrational, so the two never
// synchronise. Latitude is the slower of the two, so the view circles a few
// times per pole-to-pole pass instead of pitching wildly.
const TUMBLE_AZIMUTH_RATE = THREE.MathUtils.degToRad(TUMBLE_DEGREES_PER_SEC);
const TUMBLE_LATITUDE_RATE = TUMBLE_AZIMUTH_RATE / (GOLDEN_RATIO ** 2);

// How long the tumble takes to reach full speed, so a solve doesn't lurch.
const TUMBLE_RAMP_SECONDS = 1.0;

/**
 * Manages all THREE.js scene objects and rendering components.
 * Centralizes THREE.js object references to reduce parameter passing.
 * 
 * @class SceneManager
 */
export class SceneManager {
    constructor() {
        // Core THREE.js objects
        this.scene = null;
        this.renderer = null;
        this.camera = null;
        this.controls = null;
        // True while the view is being tumbled, e.g. in celebration.
        // (We spin the camera ourselves rather than using OrbitControls'
        // autoRotate, since TrackballControls has no equivalent.)
        this.isTumbling = false;
        // True while the "Right side up" button's animation is running;
        // see levelCamera() and updateLevelling().
        this.isLevelling = false;
        // Timekeeping for the render loop and the solve timer. (THREE.Timer,
        // successor of the deprecated THREE.Clock.) connect(document) hooks
        // the Page Visibility API, so time doesn't accumulate while the tab
        // is hidden: no giant delta on return, and the solve timer doesn't
        // count time the player spends in other tabs.
        this.timer = new THREE.Timer();
        this.timer.connect(document);
        
        // Geometry and meshes
        this.polyhedronMesh = null;
        this.geometry = null;
        // Invisible line segments along the edges, which picking aims at
        // instead of the thin drawn cylinders, and the edge id of each segment.
        // Set by addEdgePickLines.
        this.pickLines = null;
        this.pickEdgeIds = [];
        // this.edgeMeshes = []; // unused?
        // this.vertexGroup = null; // unused?

        // Text elements
        this.clueTexts = null;
        this.vertexLabels = null;
        this.edgeLabels = null;
        
        // Lighting
        this.ambientLight = null;
        this.directionalLight = null;
        this.headlight = null;

        // Tumbling state. Where the path has got to, and how far the ease-in
        // has ramped; set by startTumble, advanced by updateTumble. (isTumbling
        // itself is declared with the other flags above.)
        this.tumbleAzimuth = 0;
        this.tumbleLatitudePhase = 0;
        this.tumbleSpeedFactor = 0;

        // Scratch objects, reused every frame rather than reallocated. The
        // orientation is carried as a quaternion, which is what keeps the poles
        // from being special cases; see updateTumble.
        this._cameraOffset = new THREE.Vector3();
        this._tumbleDirection = new THREE.Vector3();
        this._tumbleForward = new THREE.Vector3();
        this._tumbleAim = new THREE.Vector3();
        this._tumbleTurn = new THREE.Quaternion();

    }

    /**
     * Initializes the THREE.js scene with basic setup
     * TODO: this function is probably not helpful. Refactor.
     */
    initializeScene() {
        this.scene = new THREE.Scene();
        // Re-baseline the timer's delta computation so the first frame's
        // delta doesn't span construction-to-now. (Timer.reset() does not
        // zero the elapsed count -- but nothing has accumulated yet anyway,
        // since elapsed time only advances via update() calls in the
        // render loop, and only while the tab is visible.)
        this.timer.reset();
        return this.scene;
    }

    setupStuff() {
        // Set up camera
        const cameraDistance = 6;
        this.setupCamera(window.innerWidth / window.innerHeight, cameraDistance);

        // Set up renderer
        this.setupRenderer(
            document.getElementById('canvas-container'),
            window.innerWidth, window.innerHeight
        );

        // Set up controls
        // ?controls=orbit opts into the level-locked orbit style; anything
        // else (or nothing) gets the default trackball. See setupControls.
        const controlsStyle = new URLSearchParams(window.location.search).get('controls');
        this.setupControls({minDistance: CAMERA_MIN_ZOOM, maxDistance: CAMERA_MAX_ZOOM,
                            style: controlsStyle});

        // Now that there is a camera, put the headlight on it, so the very first
        // frame is lit like all the others.
        this.updateHeadlight();
    }

    /**
     * Sets up the camera with standard configuration
     * @param {number} aspectRatio - Camera aspect ratio
     * @param {number} distance - Camera distance from origin
     */
    setupCamera(aspectRatio, distance = 6) {
        this.camera = new THREE.PerspectiveCamera(35, aspectRatio); // , distance - 2, 1000
        this.camera.position.y = 1;
        this.camera.position.z = distance;
        this.camera.lookAt(0, 0, 0);
        this.camera.updateProjectionMatrix();
    }

    /**
     * Sets up the WebGL renderer
     * @param {HTMLElement} container - DOM element to append renderer to
     * @param {number} width - Renderer width
     * @param {number} height - Renderer height
     */
    setupRenderer(container, width, height) {
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(this.renderer.domElement);
    }

    /**
     * Sets up camera controls.
     *
     * Two schemes, chosen by config.style:
     *
     * - 'trackball' (default): TrackballControls rotates freely in any
     *   direction, with no up direction maintained, so the polyhedron can be
     *   tumbled to any orientation (including upside-down). The view can end up
     *   rolled, hence the "Right side up" button that ui.js shows in this mode.
     * - 'orbit': OrbitControls keeps the camera's up direction pointing at
     *   world +Y, so the view never rolls and the player can't get
     *   disoriented. The cost is that dragging stops at the poles -- you can
     *   still reach every face by dragging sideways, but the vertical motion
     *   hits a wall, which players read as "I can't turn it that way."
     *
     * Clue digits stay legible either way: clueRenderer rolls them toward the
     * camera every frame.
     *
     * @param {Object} config - {minDistance, maxDistance, style}
     */
    setupControls(config = {}) {
        if (!this.camera || !this.renderer) {
            throw new Error('Camera and renderer must be set up before controls');
        }

        this.controlsStyle = config.style === 'orbit' ? 'orbit' : 'trackball';
        const minDistance = config.minDistance || 3;
        const maxDistance = config.maxDistance || 20;

        if (this.controlsStyle === 'trackball') {
            this.controls = new TrackballControls(this.camera, this.renderer.domElement);
            // staticMoving = false gives inertia, the counterpart of
            // OrbitControls' damping -- but note the factor works the opposite
            // way round: here it's the fraction of the remaining rotation
            // applied per frame, so HIGHER means the camera keeps up with the
            // pointer better. See the constants for tuning.
            this.controls.staticMoving = false;
            this.controls.dynamicDampingFactor = TRACKBALL_DAMPING;
            this.controls.rotateSpeed = TRACKBALL_ROTATE_SPEED;
        } else {
            this.controls = new OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
            // Default dampingFactor is 0.05, but we want more because when the
            // shape keeps rotating it's hard to click on the right thing.
            this.controls.dampingFactor = 0.1;
        }

        this.controls.target.set(0, 0, 0);
        this.controls.minDistance = minDistance;
        this.controls.maxDistance = maxDistance;

        // TrackballControls converts pointer positions into rotations using a
        // cached rectangle of the canvas, which it only measures in
        // handleResize(). It calls that itself on connect, but at that moment
        // the freshly appended canvas can still measure zero, leaving the
        // rectangle empty and every drag computing NaN. Measure again now, and
        // whenever the window resizes (see onWindowResize). OrbitControls
        // needs no equivalent.
        if (this.controls.handleResize) {
            this.controls.handleResize();
        }

        this.controls.update();
    }

    /**
     * Restores the view to "right side up": keeps the camera where it is, but
     * rotates away any roll, so world up is up on screen again.
     *
     * Animated over LEVEL_CAMERA_SECONDS rather than snapping, because an
     * instant reorientation is disorienting -- the point of the button is to
     * recover your bearings, so you need to see which way the view turned.
     *
     * Only meaningful with trackball controls, since OrbitControls never lets
     * the view roll in the first place (there it's harmless but does nothing).
     */
    levelCamera() {
        // Work out the target orientation by momentarily applying it, then
        // rewind: slerping quaternions avoids any chance of the interpolated
        // 'up' passing through the view direction, where lookAt degenerates.
        const startQuaternion = this.camera.quaternion.clone();
        const startUp = this.camera.up.clone();
        this.camera.up.set(0, 1, 0);
        this.camera.lookAt(this.controls.target);
        this._levelToQuaternion = this.camera.quaternion.clone();
        this.camera.quaternion.copy(startQuaternion);
        this.camera.up.copy(startUp);

        this._levelFromQuaternion = startQuaternion;
        this._levelProgress = 0;
        this.isLevelling = true;
    }

    /**
     * Advances the "right side up" animation, if one is running. Called once
     * per frame from the render loop, which skips the controls' own update()
     * while this is in progress -- their lookAt() would otherwise overwrite
     * the orientation we're interpolating.
     * @param {number} deltaSeconds - time since the previous frame
     */
    updateLevelling(deltaSeconds) {
        if (!this.isLevelling) return;

        this._levelProgress = Math.min(1, this._levelProgress + deltaSeconds / LEVEL_CAMERA_SECONDS);
        // Ease in and out, so the turn starts and finishes gently.
        const t = this._levelProgress * this._levelProgress * (3 - 2 * this._levelProgress);
        this.camera.quaternion.slerpQuaternions(this._levelFromQuaternion,
                                                this._levelToQuaternion, t);

        if (this._levelProgress >= 1) {
            this.isLevelling = false;
            // Hand a level 'up' back to the controls, so they carry on from
            // the orientation we just settled into.
            this.camera.up.set(0, 1, 0);
        }
    }

    /**
     * Starts/stops tumbling the view: a slow turn that brings every side of the
     * solid into sight in turn. Celebrating a solve is one caller (see
     * celebrateSolved in ui.js); this knows nothing about why it's running.
     *
     * We move the camera ourselves rather than using OrbitControls' autoRotate,
     * so the tumble behaves the same under both control schemes -- and because
     * autoRotate only spins about one axis, which is not a tumble.
     */
    startTumble() {
        this.isTumbling = true;
        // Ease in, so the view doesn't lurch when the tumble begins.
        this.tumbleSpeedFactor = 0;

        // Start the path from where the player left the view, so the first frame
        // barely moves. Latitude and azimuth are the path's own coordinates; see
        // updateTumble.
        const offset = this._cameraOffset.copy(this.camera.position)
            .sub(this.controls.target);
        this.tumbleAzimuth = Math.atan2(offset.z, offset.x);
        this.tumbleLatitudePhase = Math.asin(
            THREE.MathUtils.clamp(offset.y / (offset.length() || 1), -1, 1));
    }

    stopTumble() {
        this.isTumbling = false;
    }

    /**
     * Advances the tumble, if it's running. Called once per frame from the
     * render loop, AFTER the controls have had their turn -- see the note at
     * that call site for why that order is the thing that makes this work.
     *
     * Two halves, deliberately separate:
     *
     * WHERE the camera goes. Azimuth turns steadily while latitude sweeps from
     * pole to pole, the two rates in an irrational ratio so the path never
     * closes. That covers the whole solid, poles included, from any starting
     * viewpoint (measured: every point on the surface comes within 30 degrees of
     * the camera). What does NOT work is nudging the camera with the same
     * rotation every frame, however many axes it is built from: by Euler's
     * theorem a composition of rotations is one rotation about one axis, so
     * iterating it traces a circle -- which is what the previous versions did,
     * and why some of the solid was never shown.
     *
     * WHICH WAY IS UP -- and this, not the path, is what makes it read as a
     * tumble rather than an orbit. The orientation is carried in the camera's
     * quaternion, turned each frame by the shortest arc from where it was
     * looking to where it now looks, adding no twist of its own.
     *
     * The obvious alternative, lookAt(target) with an up vector, holds the
     * horizon dead level: measured, its roll relative to level is exactly 0
     * degrees for the entire path. The solid then slides past without ever
     * appearing to turn over, however much of it the camera visits -- which was
     * the complaint about the previous version. Transporting the orientation
     * instead lets the roll follow the path, and it goes right around: measured
     * over a minute, a spread of 358 degrees. That is the tumble.
     *
     * Note it is NOT about gimbal lock, whatever the shape of the maths
     * suggests. lookAt was measured through the exact poles with no snap at all
     * (largest orientation change in a frame 0.54 degrees, the same as the
     * path's own step, with no spikes) -- near a pole the roll rate is bounded
     * by the azimuth rate, which is a fraction of a degree per frame. The
     * quaternion is here for the free roll, not to avoid a degeneracy.
     *
     * @param {number} deltaSeconds - time since the previous frame
     */
    updateTumble(deltaSeconds) {
        if (!this.isTumbling) return;

        // Ease in over the first second or so, rather than lurching.
        this.tumbleSpeedFactor = Math.min(
            1, this.tumbleSpeedFactor + deltaSeconds / TUMBLE_RAMP_SECONDS);
        const step = this.tumbleSpeedFactor * deltaSeconds;

        // Advance the path's own coordinates. Accumulating these (rather than
        // deriving them from a running clock) keeps the ratio between the two
        // rates exact while the ease-in is still scaling both.
        this.tumbleAzimuth += TUMBLE_AZIMUTH_RATE * step;
        this.tumbleLatitudePhase += TUMBLE_LATITUDE_RATE * step;

        // asin(sin(phase)) is a triangle wave: latitude crosses at a constant
        // rate instead of lingering at the extremes. The full range is fine now
        // -- nothing here divides by cos(latitude).
        const latitude = Math.asin(Math.sin(this.tumbleLatitudePhase));
        const cosLatitude = Math.cos(latitude);

        // Take the current distance as given, so a zoom mid-tumble sticks.
        const radius = this.camera.position.distanceTo(this.controls.target);
        this._tumbleDirection.set(
            cosLatitude * Math.cos(this.tumbleAzimuth),
            Math.sin(latitude),
            cosLatitude * Math.sin(this.tumbleAzimuth),
        );

        // Turn the camera the short way from its present line of sight to the
        // new one. A camera looks down its own -Z.
        this._tumbleForward.set(0, 0, -1).applyQuaternion(this.camera.quaternion);
        this._tumbleAim.copy(this._tumbleDirection).negate();
        this._tumbleTurn.setFromUnitVectors(this._tumbleForward, this._tumbleAim);
        this.camera.quaternion.premultiply(this._tumbleTurn).normalize();

        this.camera.position.copy(this._tumbleDirection)
            .multiplyScalar(radius).add(this.controls.target);

        // Keep `up` consistent with the orientation we just set. Nothing here
        // reads it, but the controls and levelCamera do, so leaving it stale
        // would make the view jump when the player next drags.
        this.camera.up.copy(WORLD_UP).applyQuaternion(this.camera.quaternion);
    }

    /**
     * Adds the main polyhedron mesh to the scene
     * @param {THREE.BufferGeometry} geometry - The geometry for the polyhedron
     * @param {THREE.Material} material - The material for the polyhedron
     */
    addPolyhedronMesh(geometry, material) {
        this.geometry = geometry;
        this.polyhedronMaterial = material;
        this.polyhedronMesh = new THREE.Mesh(geometry, material);
        this.scene.add(this.polyhedronMesh);
        return this.polyhedronMesh;
    }

    /**
     * Adds edge meshes to the scene
     * @param {THREE.Mesh[]} edgeMeshes - Array of edge meshes
     */
    addEdgeMeshes(edgeMeshes) {
        this.edgeMeshes = edgeMeshes;
        const edgeGroup = new THREE.Group();
        edgeMeshes.forEach(mesh => edgeGroup.add(mesh));
        this.scene.add(edgeGroup);
        return edgeGroup;
    }

    /**
     * Registers the invisible lines that edge picking aims at (see
     * makeEdgePickLines in geometry.js), and adds them to the scene so their
     * world matrix is kept up to date like anything else in it. They never
     * render, being invisible.
     *
     * @param {THREE.LineSegments|null} pickLines
     * @param {number[]} pickEdgeIds - Edge id of each segment, by segment index
     */
    addEdgePickLines(pickLines, pickEdgeIds = []) {
        this.pickLines = pickLines;
        this.pickEdgeIds = pickEdgeIds;
        if (pickLines) this.scene.add(pickLines);
        return pickLines;
    }

    /**
     * Adds vertex group to the scene
     * @param {THREE.Group} vertexGroup - Group containing vertex meshes
     */
    addVertexGroup(vertexGroup) {
        this.vertexGroup = vertexGroup;
        this.scene.add(vertexGroup);
        return vertexGroup;
    }

    /**
     * Sets up lighting for the scene
     *
     * Three lights, with distinct jobs:
     *
     *   - ambient, so nothing is ever pure black;
     *   - a fixed directional light, which is what gives the solid its sense of
     *     form: because it does NOT follow the camera, its shading and specular
     *     highlights shift as you rotate, and that motion reads as shape;
     *   - a "headlight" that follows the camera (see updateHeadlight), so the
     *     faces you are looking at are always lit.
     *
     * The headlight is there because a fixed light alone leaves the solid
     * backlit from half of the possible viewpoints, and on a dim face the edge
     * colors are hard to tell apart -- which matters here, since the colors are
     * what the player is reading. The fixed light was turned down from 1.2 to
     * make room for it, so the brightest a face can now get is about what it
     * was before; the difference is at the dim end, where a camera-facing face
     * used to fall back to ambient alone.
     */
    setupLighting() {
        this.ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
        this.scene.add(this.ambientLight);

        this.directionalLight = new THREE.DirectionalLight(0xffffff, 0.55);
        this.directionalLight.position.set(5, 5, 5);
        this.scene.add(this.directionalLight);

        this.headlight = new THREE.DirectionalLight(0xffffff, 0.75);
        // Positioned by updateHeadlight, both once at startup and every frame
        // after. Its target is the default, the world origin, which is where the
        // solid is centered -- so aiming it is just a matter of moving it to the
        // camera. Note we can't do that here: setupLighting runs during
        // createGameState, and the camera isn't built until setupStuff, later.
        this.scene.add(this.headlight);

        console.log("setupLighting done");
    }

    /**
     * Moves the headlight to the camera, so it lights whatever we're looking at.
     *
     * Call once per frame AFTER the camera is final for that frame, or the
     * lighting trails the view by a frame during a drag.
     *
     * Parenting the light to the camera instead would also work, but it needs
     * the camera itself added to the scene graph for the renderer to find the
     * light -- an indirection that is easy to trip over later. Copying the
     * position is one line and says what it does.
     */
    updateHeadlight() {
        if (this.headlight && this.camera) {
            this.headlight.position.copy(this.camera.position);
        }
    }

    /**
     * Adds text elements to the scene
     * @param {THREE.Group} clueTexts - Group containing clue text objects
     * @param {THREE.Group} vertexLabels - Group containing vertex label objects
     * @param {THREE.Group} edgeLabels - Group containing edge label objects
     */
    addTextElements(clueTexts, vertexLabels, edgeLabels) {
        this.clueTexts = clueTexts;
        this.vertexLabels = vertexLabels;
        this.edgeLabels = edgeLabels;
        
        this.scene.add(clueTexts);
        // Note: vertexLabels and edgeLabels are only added upon request.
    }

    /**
     * Handles window resize events
     */
    onWindowResize() {
        if (this.camera && this.renderer) {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
            // TrackballControls caches the canvas rectangle; re-measure it.
            if (this.controls && this.controls.handleResize) {
                this.controls.handleResize();
            }
        }
    }

    /**
     * Renders the scene
     */
    render() {
        if (this.renderer && this.camera && this.scene) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    /**
     * Disposes of resources
     */
    dispose() {
        if (this.renderer) {
            this.renderer.dispose();
        }
        if (this.controls) {
            this.controls.dispose();
        }
        // Disconnects the timer's Page Visibility listener.
        this.timer.dispose();
    }
}
