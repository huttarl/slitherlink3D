import * as THREE from './three/three.module.min.js';
import { addSkybox } from "./skybox.js";
import { createEdgeGeometry, loadPolyhedronFromJSON } from "./geometry.js";
import { loadPuzzleData } from "./puzzleLoader.js";
import {DEFAULT_GRID, EDGE_COLORS, VERTEX_RADIUS} from "./constants.js";
import {createClueTexts} from "./clueRenderer.js";
import {createEdgeLabels, createVertexLabels} from "./idLabels.js";
import { PuzzleGrid } from "./PuzzleGrid.js";
import { GameState } from "./GameState.js";

/**
 * Loads a grid's geometry and its puzzles, in parallel.
 *
 * @param {string} gridFilename - a data/ filename stem, e.g. 'cube'
 * @returns {Promise<Array>} [polyhedronData, puzzleData]
 * @throws {Error} if either file is missing or unusable -- including a puzzle
 *     file with no puzzles in it. See createGameState for what happens then.
 */
async function loadGrid(gridFilename) {
    return await Promise.all([
        loadPolyhedronFromJSON(`data/${gridFilename}.json`),
        loadPuzzleData(`data/${gridFilename}-puzzles.json`)
    ]);
}

/**
 * Creates and configures a complete GameState for the Slitherlink puzzle.
 * This function replaces the old createScene() and returns a fully configured GameState.
 *
 * @returns {Promise<GameState>} A fully configured GameState instance
 */
export async function createGameState() {
    // The grid and puzzle are chosen by URL query parameters (see the
    // pickers in ui.js). ?puzzle= is 1-based for human readability;
    // internally puzzle indices are 0-based.
    const urlParams = new URLSearchParams(window.location.search);
    const puzzleIndex = Math.max(0, (parseInt(urlParams.get('puzzle'), 10) || 1) - 1);

    // Initialize the game state
    const gameState = GameState.getInstance();
    await gameState.initialize({ puzzleIndex });

    // Get the scene manager and initialize the scene
    const sceneManager = gameState.getSceneManager();
    const scene = sceneManager.initializeScene();
    addSkybox(scene, 'underwater');

    // Load geometry and puzzle data in parallel for better performance.
    // The grid is chosen by the ?grid= query parameter (a data/ filename
    // stem; the picker in ui.js offers the ones listed in data/grids.json).
    const requestedGrid = urlParams.get('grid') || DEFAULT_GRID;
    let [polyhedronData, puzzleData] = [null, null];
    try {
        [polyhedronData, puzzleData] = await loadGrid(requestedGrid);
    } catch (problem) {
        // A ?grid= can name something that isn't there: grids get renamed or
        // removed, and players keep URLs. Rather than dying with a blank panel
        // and no board, fall back to the default grid and say so. Reasons this
        // fires: no such grid file, or a grid whose puzzle file is missing or
        // empty (loadPuzzleData throws for that).
        if (requestedGrid === DEFAULT_GRID) throw problem;  // Nothing to fall back to.
        console.warn(`Couldn't load grid '${requestedGrid}' ` +
                     `(${problem.message}); falling back to '${DEFAULT_GRID}'.`);
        [polyhedronData, puzzleData] = await loadGrid(DEFAULT_GRID);
        gameState.startupNotice =
            `“${requestedGrid}” isn't available — it may have been renamed or ` +
            `removed. Showing ${polyhedronData.gridName} instead.`;
        // Correct the URL to match what actually loaded, so the pickers and the
        // where-am-I label don't report the grid we failed to open, and so a
        // re-bookmark is accurate. The puzzle number goes too: it numbered the
        // other grid's puzzles. replaceState, not a navigation -- we're already
        // loading the right thing.
        urlParams.delete('grid');
        urlParams.delete('puzzle');
        const query = urlParams.toString();
        history.replaceState(null, '',
            window.location.pathname + (query ? `?${query}` : ''));
    }

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
        vertex: new THREE.MeshPhongMaterial({ color: new THREE.Color(0), shininess: 100 })
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
