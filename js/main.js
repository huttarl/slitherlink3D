import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { addSkybox } from './skybox.js';
import { createDodecahedron, createCube, createEdgeGeometry } from './geometry.js';
import { createClueTexts, updateTextVisibility } from './textRenderer.js';
import { VERTEX_RADIUS, CAMERA_MIN_ZOOM, CAMERA_MAX_ZOOM } from './constants.js';
import { makeInteraction } from './interaction.js';

function main() {
    // Scene
    const scene = new THREE.Scene();
    addSkybox(scene, 'constellation');

    // Camera
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 5;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    document.getElementById('canvas-container').appendChild(renderer.domElement);

    // Geometry and topology
    const { geometry, topology, faceMap, faceVertexRanges } = (true) ? createCube() : createDodecahedron();
    const material = new THREE.MeshPhongMaterial({ vertexColors: true, side: THREE.DoubleSide, shininess: 100, specular: 0x222222 });
    const dodecahedron = new THREE.Mesh(geometry, material);
    scene.add(dodecahedron);

    // Edges
    const { edgeMeshes } = createEdgeGeometry(topology);
    const edgeGroup = new THREE.Group();
    edgeMeshes.forEach(mesh => edgeGroup.add(mesh));
    scene.add(edgeGroup);

    // Vertices
    const vertexGroup = new THREE.Group();
    const vertexMaterial = new THREE.MeshPhongMaterial({ color: 0x808080, shininess: 100 });
    for (const [vertexId, vertex] of topology.vertices) {
        const vgeom = new THREE.SphereGeometry(VERTEX_RADIUS, 16, 16);
        const vmesh = new THREE.Mesh(vgeom, vertexMaterial);
        vmesh.position.copy(vertex.position);
        vertexGroup.add(vmesh);
    }
    scene.add(vertexGroup);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);
    controls.minDistance = CAMERA_MIN_ZOOM;
    controls.maxDistance = CAMERA_MAX_ZOOM;
    controls.update();

    // Create clue text meshes
    const clueTexts = createClueTexts(topology);
    scene.add(clueTexts);

    // Interaction with controls for drag detection
    const interaction = makeInteraction({ renderer, camera, scene, dodecahedron, geometry, topology, faceMap, faceVertexRanges, edgeMeshes, controls });

    // Render loop
    function animate() {
        requestAnimationFrame(animate);

        // Update text visibility based on camera position
        updateTextVisibility(clueTexts, camera, topology);

        renderer.render(scene, camera);
    }
    animate();
}

main();
