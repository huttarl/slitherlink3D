// TODO: these first two imports take a lot of time. How can we optimize? Get minified versions?
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { updateTextVisibility } from './textRenderer.js';
import { CAMERA_MIN_ZOOM, CAMERA_MAX_ZOOM } from './constants.js';
import { makeInteraction } from './interaction.js';
import { createScene } from "./scene.js";

async function main() {
    // Create scene and get all necessary objects
    const {
        scene, polyhedronMesh, geometry, grid, faceMap,
        faceVertexRanges, edgeMeshes, clueTexts
    } = await createScene();

    // Camera
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    // Set the camera so that perspective distortion is not too pronounced.
    const cameraDistance = 6;
    camera.position.z = cameraDistance;
    camera.fov = 35;
    camera.near = cameraDistance - 2;
    // camera.far = cameraDistance + 10; // Don't cut out the skybox.
    camera.updateProjectionMatrix();

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    document.getElementById('canvas-container').appendChild(renderer.domElement);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);
    controls.minDistance = CAMERA_MIN_ZOOM;
    controls.maxDistance = CAMERA_MAX_ZOOM;
    controls.update();

    // Interaction with controls for drag detection
    const _interaction = makeInteraction({
        renderer, camera, scene, polyhedronMesh, geometry, grid, faceMap, faceVertexRanges,
        edgeMeshes, controls
    });

    // Render loop
    function animate() {
        requestAnimationFrame(animate);

        // Update text visibility based on camera position
        updateTextVisibility(clueTexts, camera, grid);

        renderer.render(scene, camera);
    }
    animate();
}

main();
