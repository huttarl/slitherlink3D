import * as THREE from './three/three.module.min.js';
import { addSkybox } from "./skybox.js";
import { createCube, createDodecahedron, createEdgeGeometry, loadPolyhedronFromJSON } from "./geometry.js";
import { loadPuzzleData } from "./puzzleLoader.js";
import {EDGE_COLORS, VERTEX_RADIUS} from "./constants.js";
import {createClueTexts, createEdgeLabels, createVertexLabels} from "./textRenderer.js";
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
    const gameState = GameState.getInstance();
    await gameState.initialize({ puzzleIndex: 0 });

    // Get the scene manager and initialize the scene
    const sceneManager = gameState.getSceneManager();
    const scene = sceneManager.initializeScene();
    addSkybox(scene, 'underwater');

    // Load geometry and puzzle data in parallel for better performance
    const gridFilename = "T"; // Try cube, T, D, icos
    const [polyhedronData, puzzleData] = await Promise.all([
        loadPolyhedronFromJSON(`data/${gridFilename}.json`),
        loadPuzzleData(`data/${gridFilename}-puzzles.json`)
    ]);

    polyhedronData.grid.gridName = polyhedronData.gridName;
    console.log(`createGameState: phD.gridName = ${polyhedronData.gridName}`);

    // Create materials
    const materials = {
        polyhedron: new THREE.MeshPhongMaterial({
            vertexColors: true, 
            side: THREE.DoubleSide, 
            shininess: 100, 
            specular: 0x222222 
        }),
        vertex: new THREE.MeshPhongMaterial({ color: EDGE_COLORS.filledIn, shininess: 100 })
    };

    // Set up the scene with geometry and puzzle data
    await gameState.setupScene(polyhedronData, puzzleData, materials);

    // Create edge geometry and meshes
    const edgeMeshes = createEdgeGeometry(gameState.getPuzzleGrid());
    gameState.setupEdges(edgeMeshes);

    // Create vertex group
    const vertexGroup = createVertexGroup(gameState.getPuzzleGrid(), materials.vertex);
    gameState.setupVertices(vertexGroup);

    // Create text elements
    const clueTexts = createClueTexts(gameState);
    const vertexLabels = createVertexLabels(gameState);
    const edgeLabels = createEdgeLabels(gameState);
    gameState.setupTextElements(clueTexts, vertexLabels, edgeLabels);

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
        const vGeom = new THREE.SphereGeometry(VERTEX_RADIUS, 16, 16);
        const vMesh = new THREE.Mesh(vGeom, material);
        vMesh.position.copy(vertex.position);
        vertexGroup.add(vMesh);
    }
    
    return vertexGroup;
}
