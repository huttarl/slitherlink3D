import * as THREE from './three/three.module.min.js';
import { OrbitControls } from './three/OrbitControls.js';
import { TrackballControls } from './three/TrackballControls.js';
import {CAMERA_DISTANCE, CAMERA_FOV_DEGREES, CAMERA_HEIGHT,
        CAMERA_INTRO_MAX_FRAME_SECONDS, CAMERA_INTRO_SECONDS,
        CAMERA_MAX_ZOOM, CAMERA_MIN_ZOOM, LEVEL_CAMERA_SECONDS, LIGHT_INTENSITIES,
        TRACKBALL_DAMPING, TRACKBALL_ROTATE_SPEED,
        TUMBLE_DEGREES_PER_SEC} from "./constants.js";
import {debug} from "./debug.js";
import {prefersReducedMotion} from "./motion.js";

// The direction levelCamera() restores as "up", and the reference the tumble
// carries along with the camera. Module-level so it isn't rebuilt every frame.
const WORLD_UP = new THREE.Vector3(0, 1, 0);

// "Very irrational", so two rates in this ratio keep out of step indefinitely
// and the tumble's path never closes on itself.
const GOLDEN_RATIO = 1.618033;

// The tumble's two turns; see updateTumble for why it takes two, in two
// different frames.
//
// The first is a pitch about the camera's OWN right-hand axis, which is square
// to its line of sight, so it always moves the viewpoint at exactly this rate --
// no coordinate factor to stall it anywhere.
const TUMBLE_PITCH_RATE = THREE.MathUtils.degToRad(TUMBLE_DEGREES_PER_SEC);
// The camera's right-hand axis, in its own frame.
const CAMERA_RIGHT = new THREE.Vector3(1, 0, 0);

// The second is a yaw about the WORLD's up, slower, and in an irrational ratio
// to the pitch so the two never come back into step. Its contribution to the
// speed does vary with where the camera is, which is why it's the smaller of the
// two: it perturbs the pitch's steady sweep instead of dominating it.
const TUMBLE_WORLD_YAW_RATE = TUMBLE_PITCH_RATE / (GOLDEN_RATIO ** 2);

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
        // True while the board's opening zoom is running; see startIntroZoom().
        this.isIntroZooming = false;
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
        // Handles on the edge cylinders and the group of vertex spheres. Kept
        // commented out, along with the assignments in addEdgeMeshes and
        // addVertexGroup, because nothing reads them: edge picking goes through
        // pickLines, and recoloring through PuzzleGrid's edgeMeshMap. They're
        // the sort of thing a dispose() or an in-place scene swap would want,
        // so they stay here in comments rather than being forgotten.
        // this.edgeMeshes = [];
        // this.vertexGroup = null;

        // Text elements
        this.clueTexts = null;
        // The vertex/edge/face ID label groups, and the function that builds
        // them; both set up by addTextElements. Null until first shown -- see
        // getIdLabelGroups.
        this.idLabelGroups = null;
        this.makeIdLabelGroups = null;
        
        // Lighting
        this.ambientLight = null;
        this.directionalLight = null;
        this.headlight = null;

        // Tumbling state: just how far the ease-in has ramped. The turn itself
        // needs no accumulated coordinates -- each frame applies the same two
        // small rotations, in the camera's frame and the world's respectively --
        // and that absence is the point: world-frame coordinates are what used
        // to make the poles special. (isTumbling is declared with the other
        // flags above.)
        this.tumbleSpeedFactor = 0;

        // Scratch objects, reused every frame rather than reallocated.
        this._cameraOffset = new THREE.Vector3();
        this._tumbleForward = new THREE.Vector3();
        this._tumbleAim = new THREE.Vector3();
        this._tumbleTurn = new THREE.Quaternion();

    }

    /**
     * Creates the THREE.js Scene, and returns it.
     *
     * Separate from both the constructor and setupStuff because of when it has
     * to happen: createGameState needs the Scene early, to add the skybox and
     * the polyhedron to, while setupStuff (camera, renderer, controls) can only
     * run later, once the canvas container is in the DOM. So this is the point
     * where the scene begins.
     *
     * (A "TODO: this function is probably not helpful" sat here for a while.
     * The answer turned out to be that it is: the sequence above needs it.)
     */
    initializeScene() {
        this.scene = new THREE.Scene();
        return this.scene;
    }

    /**
     * Camera, renderer and controls. Separate from initializeScene; see the note
     * there for why.
     *
     * @param {number} [cameraDistance] - how far back to start the camera. The
     *     title screen passes a closer distance (see main.js); a board gets the
     *     default, which fits the whole solid comfortably.
     */
    setupStuff(cameraDistance = CAMERA_DISTANCE) {
        // Set up camera
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
    setupCamera(aspectRatio, distance = CAMERA_DISTANCE) {
        this.camera = new THREE.PerspectiveCamera(CAMERA_FOV_DEGREES, aspectRatio); // , distance - 2, 1000
        this.camera.position.y = CAMERA_HEIGHT;
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
     * Starts the board's opening zoom: pull the camera out, then let it settle in
     * to where it would have been.
     *
     * Only the DISTANCE from the target moves. The direction is left exactly as it
     * is on every frame, which is what lets this run alongside the tumble without
     * either having to know about the other: the tumble sets an orientation and
     * derives a position at whatever radius it finds, and this then corrects the
     * radius. Next frame the tumble takes the corrected radius as given, the same
     * way it accepts a zoom from the player's own scroll wheel.
     *
     * Call it AFTER setupControls, since it needs controls.target, and the caller
     * should place it after updateTumble in the frame (see main.js).
     *
     * @param {number} fromDistance - where to start, which must be inside the
     *     controls' maxDistance or they will pull it back on the first frame
     * @param {number} toDistance - where to end up
     */
    startIntroZoom(fromDistance, toDistance) {
        if (prefersReducedMotion()) {
            debug('intro zoom: skipped, prefers-reduced-motion');
            return;
        }
        this._introFrom = fromDistance;
        this._introTo = toDistance;
        this._introProgress = 0;
        this.isIntroZooming = true;
        // Put the camera at the starting distance now, before the first frame is
        // drawn, so the zoom begins from out there rather than jumping out on
        // frame two.
        this._setCameraDistance(fromDistance);
    }

    /** Abandons the opening zoom where it stands, leaving the camera put. Called
     *  when the player takes the view over; a zoom that fought a drag would
     *  win, since it runs later in the frame. */
    stopIntroZoom() {
        this.isIntroZooming = false;
    }

    /**
     * Advances the opening zoom, if one is running. A no-op otherwise, so the
     * render loop can call it unconditionally.
     * @param {number} deltaSeconds - time since the previous frame
     */
    updateIntroZoom(deltaSeconds) {
        if (!this.isIntroZooming) return;

        // Cap the step: see CAMERA_INTRO_MAX_FRAME_SECONDS. A slow frame stretches
        // the zoom rather than eating it, which for a one-off gesture this short is
        // the difference between arriving late and never being seen.
        const step = Math.min(deltaSeconds, CAMERA_INTRO_MAX_FRAME_SECONDS);
        this._introProgress = Math.min(
            1, this._introProgress + step / CAMERA_INTRO_SECONDS);
        // The same ease as updateLevelling: smoothstep is 0 at 0 and 1 at 1 with
        // zero slope at both ends, so the movement has no visible start or stop.
        const t = this._introProgress;
        const eased = t * t * (3 - 2 * t);
        this._setCameraDistance(
            this._introFrom + (this._introTo - this._introFrom) * eased);

        if (this._introProgress >= 1) this.isIntroZooming = false;
    }

    /**
     * Moves the camera to `distance` from the controls' target, along the
     * direction it is already looking from. Orientation is untouched.
     */
    _setCameraDistance(distance) {
        const outward = this._introOutward
            || (this._introOutward = new THREE.Vector3());
        outward.copy(this.camera.position).sub(this.controls.target);
        // A zero vector has no direction to preserve, and setLength would give
        // NaN. It cannot happen from any real camera position, but a NaN reaching
        // the camera is unrecoverable and silent, so it is worth the two lines.
        if (outward.lengthSq() === 0) return;
        this.camera.position.copy(
            outward.setLength(distance).add(this.controls.target));
    }

    /**
     * Starts/stops tumbling the view: a slow turn that brings every side of the
     * solid into sight in turn. Celebrating a solve is one caller (see
     * celebrateSolved in ui.js); this knows nothing about why it's running.
     *
     * We move the camera ourselves rather than using OrbitControls' autoRotate,
     * so the tumble behaves the same under both control schemes -- and because
     * autoRotate only spins about one axis, which is not a tumble.
     *
     * Declines for a player who has asked for less motion, and does so HERE rather
     * than at each call site: a turning solid is the plainest thing that setting
     * exists to prevent, and there are two callers, one of which is the
     * celebration's fallback for having already declined to animate.
     */
    startTumble() {
        if (prefersReducedMotion()) {
            debug('tumble: skipped, prefers-reduced-motion');
            return;
        }
        this.isTumbling = true;
        // Ease in, so the view doesn't lurch when the tumble begins.
        this.tumbleSpeedFactor = 0;

        // updateTumble derives the camera's POSITION from its orientation, so
        // the two have to agree before the first frame or the view would jump.
        // They can disagree: the controls aim the camera with lookAt, and
        // levelCamera interpolates it. Turn the orientation the short way onto
        // the target -- the aim only, no twist -- which leaves the derived
        // position exactly where the camera already is.
        this._tumbleForward.set(0, 0, -1).applyQuaternion(this.camera.quaternion);
        this._tumbleAim.copy(this.controls.target).sub(this.camera.position)
            .normalize();
        this._tumbleTurn.setFromUnitVectors(this._tumbleForward, this._tumbleAim);
        this.camera.quaternion.premultiply(this._tumbleTurn).normalize();
    }

    stopTumble() {
        this.isTumbling = false;
    }

    /**
     * Advances the tumble, if it's running. Called once per frame from the
     * render loop, AFTER the controls have had their turn -- see the note at
     * that call site for why that order is the thing that makes this work.
     *
     * Everything here happens in the CAMERA's frame; no world-frame azimuth or
     * latitude is involved. That's the point. Driving the camera by spherical
     * coordinates around the world's Y axis made the poles special in two ways
     * that showed on screen: the viewpoint's speed carried a cos(latitude)
     * factor, so it slowed to a third near the poles (the stall), and latitude
     * had to turn around when it got there, reversing direction between one
     * frame and the next (the bounce).
     *
     * Instead, two turns per frame, in two different frames:
     *
     *   - a pitch about the camera's own right-hand axis, which is square to its
     *     line of sight, so it moves the viewpoint at exactly that rate wherever
     *     the camera happens to be. No factor, nowhere slower, nothing to double
     *     back on.
     *   - a slower yaw about the world's up.
     *
     * Two frames, not one, is the whole trick. Rotations applied in the SAME
     * frame every frame collapse: by Euler's theorem their composition is a
     * single rotation about a single axis, so iterating it just traces a circle,
     * which is what every earlier version did. Even a body-frame axis that
     * precesses uniformly collapses -- that's the coning of a symmetric top, a
     * circle again, and it measured 47% of the solid ever shown square-on. A
     * body pitch and a world yaw don't commute, so they never reduce to one
     * rotation, and at an irrational rate ratio the path is dense: measured
     * 100% of the surface within 30 degrees of the camera.
     *
     * The cost is that the world yaw's contribution to the speed does depend on
     * where the camera is, so the rate isn't perfectly even -- measured 7%
     * variation, against roughly 180% for the spherical version it replaced, and
     * with no approach to zero anywhere, since the body pitch is always at full
     * strength.
     *
     * The position is then derived FROM the orientation, so the camera aims at
     * the target by construction rather than by correction: it sits along its
     * own +Z from the target, and a camera looks down its own -Z.
     *
     * The view also rolls freely as it goes, which is what makes this read as a
     * tumble rather than an orbit. lookAt(target) would hold the horizon dead
     * level -- measured, its roll relative to level stays at exactly 0 degrees
     * -- so the solid slid past without ever appearing to turn over. That, not
     * gimbal lock, was the complaint: lookAt was measured straight through the
     * poles with no snap at all.
     *
     * @param {number} deltaSeconds - time since the previous frame
     */
    updateTumble(deltaSeconds) {
        if (!this.isTumbling) return;

        // Ease in over the first second or so, rather than lurching.
        this.tumbleSpeedFactor = Math.min(
            1, this.tumbleSpeedFactor + deltaSeconds / TUMBLE_RAMP_SECONDS);
        const step = this.tumbleSpeedFactor * deltaSeconds;

        // Pitch in the camera's own frame: multiply on the RIGHT, which is what
        // makes the axis mean "the camera's right-hand axis" rather than the
        // world's X.
        this.camera.quaternion.multiply(
            this._tumbleTurn.setFromAxisAngle(CAMERA_RIGHT,
                                              TUMBLE_PITCH_RATE * step));
        // Yaw in the world's frame: multiply on the LEFT.
        this.camera.quaternion.premultiply(
            this._tumbleTurn.setFromAxisAngle(WORLD_UP,
                                              TUMBLE_WORLD_YAW_RATE * step));
        this.camera.quaternion.normalize();

        // Take the current distance as given, so a zoom mid-tumble sticks.
        const radius = this.camera.position.distanceTo(this.controls.target);
        this.camera.position.set(0, 0, radius)
            .applyQuaternion(this.camera.quaternion)
            .add(this.controls.target);

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
        // this.edgeMeshes = edgeMeshes;   // see the constructor: nothing reads it
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
        // this.vertexGroup = vertexGroup;   // see the constructor: nothing reads it
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
        this.ambientLight = new THREE.AmbientLight(0xffffff,
                                                   LIGHT_INTENSITIES.ambient);
        this.scene.add(this.ambientLight);

        this.directionalLight = new THREE.DirectionalLight(
            0xffffff, LIGHT_INTENSITIES.directional);
        this.directionalLight.position.set(5, 5, 5);
        this.scene.add(this.directionalLight);

        this.headlight = new THREE.DirectionalLight(0xffffff,
                                                   LIGHT_INTENSITIES.headlight);
        // Positioned by updateHeadlight, both once at startup and every frame
        // after. Its target is the default, the world origin, which is where the
        // solid is centered -- so aiming it is just a matter of moving it to the
        // camera. Note we can't do that here: setupLighting runs during
        // createGameState, and the camera isn't built until setupStuff, later.
        this.scene.add(this.headlight);

        debug("setupLighting done");
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
     * Adds the clue digits to the scene, and registers how to build the ID
     * labels if they're ever asked for.
     *
     * @param {THREE.Group} clueTexts - Group containing clue text objects
     * @param {function(): THREE.Group[]} makeIdLabelGroups - see
     *     getIdLabelGroups
     */
    addTextElements(clueTexts, makeIdLabelGroups) {
        this.clueTexts = clueTexts;
        this.makeIdLabelGroups = makeIdLabelGroups;

        this.scene.add(clueTexts);
        // Note: the ID label groups are neither built nor added until requested
        // (GameState.toggleShowIDs).
    }

    /**
     * The ID label groups -- vertices, edges and faces -- building them on the
     * first request and keeping them thereafter.
     *
     * Building costs a canvas and a texture per label, which is why it waits:
     * see the note in createGameState. Rebuilding on every toggle instead of
     * caching would put that cost in the player's way each time.
     *
     * @returns {THREE.Group[]} the groups, in vertex/edge/face order
     */
    getIdLabelGroups() {
        if (this.idLabelGroups === null) {
            this.idLabelGroups = this.makeIdLabelGroups();
        }
        return this.idLabelGroups;
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
