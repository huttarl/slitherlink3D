import * as THREE from './three/three.module.min.js';
import { OrbitControls } from './three/OrbitControls.js';
import { TrackballControls } from './three/TrackballControls.js';
import {CAMERA_MAX_ZOOM, CAMERA_MIN_ZOOM, CELEBRATION_SPIN_DEGREES_PER_SEC,
        LEVEL_CAMERA_SECONDS, TRACKBALL_DAMPING, TRACKBALL_ROTATE_SPEED} from "./constants.js";

// Axis the celebration spin turns about, and the direction levelCamera()
// restores as "up". Module-level so it isn't rebuilt every frame.
const WORLD_UP = new THREE.Vector3(0, 1, 0);

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
        // True while the solved-puzzle celebration is spinning the view.
        // (We spin the camera ourselves rather than using OrbitControls'
        // autoRotate, since TrackballControls has no equivalent.)
        this.isCelebrationSpinning = false;
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
        // ?controls=trackball opts into free rotation; anything else (or
        // nothing) gets the default orbit controls. See setupControls.
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
     * - 'orbit' (default): OrbitControls keeps the camera's up direction
     *   pointing at world +Y, so the view never rolls and the player can't get
     *   disoriented. The cost is that dragging stops at the poles -- you can
     *   still reach every face by dragging sideways, but the vertical motion
     *   hits a wall, which players read as "I can't turn it that way."
     * - 'trackball': TrackballControls rotates freely in any direction, with no
     *   up direction maintained, so the polyhedron can be tumbled to any
     *   orientation (including upside-down). The view can end up rolled, hence
     *   the "Right side up" button that ui.js shows in this mode.
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

        this.controlsStyle = config.style === 'trackball' ? 'trackball' : 'orbit';
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
     * Starts/stops the celebration spin. We rotate the camera about world up
     * ourselves rather than using OrbitControls' autoRotate, so that the
     * celebration behaves the same under both control schemes (TrackballControls
     * has no autoRotate).
     */
    startCelebrationSpin() {
        this.isCelebrationSpinning = true;
    }

    stopCelebrationSpin() {
        this.isCelebrationSpinning = false;
    }

    /**
     * Advances the celebration spin, if it's running. Called once per frame
     * from the render loop.
     * @param {number} deltaSeconds - time since the previous frame
     */
    updateCelebrationSpin(deltaSeconds) {
        if (!this.isCelebrationSpinning) return;
        const angle = THREE.MathUtils.degToRad(CELEBRATION_SPIN_DEGREES_PER_SEC) * deltaSeconds;
        // Orbit the camera around the target, about world up.
        this.camera.position.sub(this.controls.target)
            .applyAxisAngle(WORLD_UP, angle)
            .add(this.controls.target);
        this.camera.lookAt(this.controls.target);
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
