import * as THREE from 'three';

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
        
        // Geometry and meshes
        this.polyhedronMesh = null;
        this.geometry = null;
        this.edgeMeshes = [];
        this.vertexGroup = null;
        
        // Text elements
        this.clueTexts = null;
        this.vertexLabels = null;
        
        // Lighting
        this.ambientLight = null;
        this.directionalLight = null;
        
        // Material references
        this.polyhedronMaterial = null;
        this.vertexMaterial = null;
    }

    /**
     * Initializes the THREE.js scene with basic setup
     */
    initializeScene() {
        this.scene = new THREE.Scene();
        return this.scene;
    }

    /**
     * Sets up the camera with standard configuration
     * @param {number} aspectRatio - Camera aspect ratio
     * @param {number} distance - Camera distance from origin
     */
    setupCamera(aspectRatio, distance = 6) {
        this.camera = new THREE.PerspectiveCamera(35, aspectRatio, distance - 2, 1000);
        this.camera.position.y = 1;
        this.camera.position.z = distance;
        this.camera.lookAt(0, 0, 0);
        this.camera.updateProjectionMatrix();
        return this.camera;
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
        return this.renderer;
    }

    /**
     * Sets up camera controls
     * @param {Object} config - Controls configuration
     */
    setupControls(config = {}) {
        if (!this.camera || !this.renderer) {
            throw new Error('Camera and renderer must be set up before controls');
        }
        
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.set(0, 0, 0);
        this.controls.minDistance = config.minDistance || 3;
        this.controls.maxDistance = config.maxDistance || 20;
        this.controls.update();
        return this.controls;
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
     */
    setupLighting() {
        this.ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(this.ambientLight);
        
        this.directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        this.directionalLight.position.set(5, 5, 5);
        this.scene.add(this.directionalLight);
        
        return { ambientLight: this.ambientLight, directionalLight: this.directionalLight };
    }

    /**
     * Adds text elements to the scene
     * @param {THREE.Group} clueTexts - Group containing clue text objects
     * @param {THREE.Group} vertexLabels - Group containing vertex label objects
     */
    addTextElements(clueTexts, vertexLabels) {
        this.clueTexts = clueTexts;
        this.vertexLabels = vertexLabels;
        
        this.scene.add(clueTexts);
        // Note: vertexLabels are only added in debug mode
    }

    /**
     * Handles window resize events
     */
    onWindowResize() {
        if (this.camera && this.renderer) {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
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
    }
}
