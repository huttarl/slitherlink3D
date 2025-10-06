import * as THREE from 'three';
import { addSkybox } from "./skybox.js";
import { createCube, createDodecahedron, createEdgeGeometry, loadPolyhedronFromJSON } from "./geometry.js";
import { loadPuzzleData, applyPuzzleToGrid, applySolutionToGrid } from "./puzzleLoader.js";
import { VERTEX_RADIUS } from "./constants.js";
import { createClueTexts, createVertexLabels } from "./textRenderer.js";

/**
 * Creates and configures the 3D scene for the Slitherlink puzzle, including geometry,
 * materials, lighting, and interactive elements.
 * 
 * @returns {Object} An object containing all the created scene elements and data structures
 * @property {THREE.Scene} scene - The main Three.js scene containing all 3D objects
 * @property {THREE.Mesh} polyhedronMesh - The main puzzle mesh (dodecahedron or cube)
 * @property {THREE.BufferGeometry} geometry - The geometry of the puzzle polyhedron
 * @property {Grid} grid - The grid data structure containing puzzle state and topology
 * @property {Map} faceMap - Mapping of face indices to face IDs
 * @property {Map} faceVertexRanges - Mapping of face IDs to vertex ranges in the geometry
 * @property {THREE.Mesh[]} edgeMeshes - Array of meshes representing the puzzle edges
 * @property {THREE.Group} clueTexts - Group containing all the clue number text objects
 * @property {THREE.Group} vertexLabels - Group containing all vertex label text objects
 * @property {THREE.Group} vertexGroup - Group containing all vertex sphere meshes
 * @property {THREE.AmbientLight} ambientLight - The scene's ambient light source
 * @property {THREE.DirectionalLight} directionalLight - The scene's main directional light
 */
export async function createScene() {
    const scene = new THREE.Scene();
    addSkybox(scene, 'underwater');

    // Load geometry and puzzle data in parallel for better performance
    const [polyhedronData, puzzleData] = await Promise.all([
        loadPolyhedronFromJSON('data/T.json'),
        loadPuzzleData('data/T-puzzles.json')
    ]);

    const { geometry, grid, faceMap, faceVertexRanges, gridId } = polyhedronData;

    // Apply puzzle clues to grid (validates gridId match)
    applyPuzzleToGrid(grid, puzzleData, 0, gridId);

    // Display the solution, for now. This is only for testing.
    applySolutionToGrid(grid, puzzleData, 0);

    const material = new THREE.MeshPhongMaterial({ 
        vertexColors: true, 
        side: THREE.DoubleSide, 
        shininess: 100, 
        specular: 0x222222 
    });
    const polyhedronMesh = new THREE.Mesh(geometry, material);
    scene.add(polyhedronMesh);

    // Create edge geometry and group
    const { edgeMeshes } = createEdgeGeometry(grid);
    const edgeGroup = new THREE.Group();
    edgeGroup.add(...edgeMeshes);
    scene.add(edgeGroup);

    // Create vertex group
    const vertexGroup = new THREE.Group();
    const vertexMaterial = new THREE.MeshPhongMaterial({ color: 0x808080, shininess: 100 });
    for (const [_vertexId, vertex] of grid.vertices) {
        const vgeom = new THREE.SphereGeometry(VERTEX_RADIUS, 16, 16);
        const vmesh = new THREE.Mesh(vgeom, vertexMaterial);
        vmesh.position.copy(vertex.position);
        vertexGroup.add(vmesh);
    }
    scene.add(vertexGroup);

    // Create text elements
    const clueTexts = createClueTexts(grid);
    scene.add(clueTexts);
    
    const vertexLabels = createVertexLabels(grid);
    scene.add(vertexLabels);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    return {
        scene, polyhedronMesh, geometry, grid, faceMap, faceVertexRanges, edgeMeshes, clueTexts,
        vertexLabels, vertexGroup, ambientLight, directionalLight
    };
}