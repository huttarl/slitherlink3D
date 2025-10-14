import * as THREE from 'three';
import { addSkybox } from "./skybox.js";
import { createCube, createDodecahedron, createEdgeGeometry, loadPolyhedronFromJSON } from "./geometry.js";
import { loadPuzzleData } from "./puzzleLoader.js";
import { VERTEX_RADIUS } from "./constants.js";
import { createClueTexts, createVertexLabels } from "./textRenderer.js";
import { SceneManager } from "./SceneManager.js";
import { PuzzleGrid } from "./PuzzleGrid.js";
import { GameState } from "./GameState.js";

/**
 * Creates and configures a complete GameState for the Slitherlink puzzle.
 * This function replaces the old createScene() and returns a fully configured GameState.
 * 
 * @returns {Promise<GameState>} A fully configured GameState instance
 */
export async function createGameState() {
    // Initialize the game state
    const gameState = new GameState();
    await gameState.initialize({ puzzleIndex: 0 });

    // Get the scene manager and initialize the scene
    const sceneManager = gameState.getSceneManager();
    const scene = sceneManager.initializeScene();
    addSkybox(scene, 'underwater');

    // Load geometry and puzzle data in parallel for better performance
    const [polyhedronData, puzzleData] = await Promise.all([
        loadPolyhedronFromJSON('data/cube.json'),
        loadPuzzleData('data/cube-puzzles.json')
    ]);

    // Create materials
    const materials = {
        polyhedron: new THREE.MeshPhongMaterial({
            vertexColors: true, 
            side: THREE.DoubleSide, 
            shininess: 100, 
            specular: 0x222222 
        }),
        vertex: new THREE.MeshPhongMaterial({ color: 0x808080, shininess: 100 })
    };

    // Set up the scene with geometry and puzzle data
    const { geometry, faceMap, faceVertexRanges, gridId } = await gameState.setupScene(
        polyhedronData, puzzleData, materials
    );

    // Create edge geometry and meshes
    const { edgeMeshes } = createEdgeGeometry(gameState.getPuzzleGrid());
    gameState.setupEdges(edgeMeshes);

    // Create vertex group
    const vertexGroup = createVertexGroup(gameState.getPuzzleGrid(), materials.vertex);
    gameState.setupVertices(vertexGroup);

    // Create text elements
    const clueTexts = createClueTexts(gameState.getPuzzleGrid());
    const vertexLabels = createVertexLabels(gameState.getPuzzleGrid());
    gameState.setupTextElements(clueTexts, vertexLabels);

    // Set up lighting
    gameState.setupLighting();

    return gameState;
}

/**
 * Creates a vertex group containing sphere meshes for all vertices in the grid.
 * @param {PuzzleGrid} grid - The puzzle grid containing vertex data
 * @param {THREE.Material} material - Material for the vertex spheres
 * @returns {THREE.Group} Group containing all vertex meshes
 */
function createVertexGroup(grid, material) {
    const vertexGroup = new THREE.Group();
    
    for (const [_vertexId, vertex] of grid.vertices) {
        const vgeom = new THREE.SphereGeometry(VERTEX_RADIUS, 16, 16);
        const vmesh = new THREE.Mesh(vgeom, material);
        vmesh.position.copy(vertex.position);
        vertexGroup.add(vmesh);
    }
    
    return vertexGroup;
}

/**
 * Legacy function for backward compatibility.
 * Creates and configures the 3D scene using the old approach.
 * 
 * @deprecated Use createGameState() instead for better organization
 * @returns {Object} An object containing all the created scene elements and data structures
 */
export async function createScene() {
    // For now, create a GameState and extract the old format for compatibility
    const gameState = await createGameState();
    const sceneManager = gameState.getSceneManager();
    const puzzleGrid = gameState.getPuzzleGrid();
    
    return {
        scene: sceneManager.scene,
        polyhedronMesh: sceneManager.polyhedronMesh,
        geometry: sceneManager.geometry,
        grid: puzzleGrid,
        faceMap: puzzleGrid.faceMap,
        faceVertexRanges: puzzleGrid.faceVertexRanges,
        edgeMeshes: puzzleGrid.getAllEdgeMeshes(),
        clueTexts: sceneManager.clueTexts,
        vertexLabels: sceneManager.vertexLabels,
        vertexGroup: sceneManager.vertexGroup,
        ambientLight: sceneManager.ambientLight,
        directionalLight: sceneManager.directionalLight,
        puzzleData: puzzleGrid.puzzleData,
        // Store gameState reference for future migration
        _gameState: gameState
    };
}