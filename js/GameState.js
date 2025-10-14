import { SceneManager } from './SceneManager.js';
import { PuzzleGrid } from './PuzzleGrid.js';

/**
 * Main application state container that manages all game components.
 * Provides a single entry point for accessing scene, grid, and interaction data.
 * 
 * @class GameState
 */
export class GameState {
    constructor() {
        this.sceneManager = new SceneManager();
        this.puzzleGrid = new PuzzleGrid();
        this.interaction = null;
        
        // Application state
        this.isInitialized = false;
        this.currentPuzzleIndex = 0;
        this.debugMode = false;
        this.numberLocale = 'mr'; // Try ar, fa, mr, en
    }

    /**
     * Initializes the game state with all necessary components
     * @param {Object} config - Configuration object
     * @returns {Promise<GameState>} This GameState instance
     */
    async initialize(config = {}) {
        if (this.isInitialized) {
            console.warn('GameState is already initialized');
            return this;
        }

        // Initialize scene manager
        this.sceneManager.initializeScene();
        
        // Store puzzle index for later use (after puzzle data is loaded)
        this.currentPuzzleIndex = config.puzzleIndex || 0;
        
        this.isInitialized = true;
        return this;
    }

    /**
     * Gets the scene manager instance
     * @returns {SceneManager} The scene manager
     */
    getSceneManager() {
        return this.sceneManager;
    }

    /**
     * Gets the puzzle grid instance
     * @returns {PuzzleGrid} The puzzle grid
     */
    getPuzzleGrid() {
        return this.puzzleGrid;
    }

    /**
     * Sets the interaction handler
     * @param {Object} interaction - The interaction handler instance
     */
    setInteraction(interaction) {
        this.interaction = interaction;
    }

    /**
     * Gets the interaction handler
     * @returns {Object} The interaction handler
     */
    getInteraction() {
        return this.interaction;
    }

    /**
     * Sets up the complete scene with geometry, puzzle data, and interaction
     * @param {Object} polyhedronData - Geometry and grid data
     * @param {Object} puzzleData - Puzzle data
     * @param {Object} materials - Material configurations
     * @returns {Object} Setup results for further processing
     */
    async setupScene(polyhedronData, puzzleData, materials) {
        if (!this.isInitialized) {
            throw new Error('GameState must be initialized before setting up scene');
        }

        const { geometry, grid, faceMap, faceVertexRanges, gridId } = polyhedronData;
        
        // Copy grid data to our puzzle grid
        this.puzzleGrid.vertices = grid.vertices;
        this.puzzleGrid.edges = grid.edges;
        this.puzzleGrid.faces = grid.faces;
        this.puzzleGrid.nextId = grid.nextId;
        this.puzzleGrid.vertexPairToEdge = grid.vertexPairToEdge;
        
        // Set up puzzle data
        this.puzzleGrid.setPuzzleData(puzzleData, gridId);
        this.puzzleGrid.setCurrentPuzzle(this.currentPuzzleIndex);
        
        // Apply puzzle clues and validate
        this.puzzleGrid.applyCurrentPuzzleClues();
        this.puzzleGrid.validateCurrentSolution();
        
        // Set up scene manager with geometry
        this.sceneManager.addPolyhedronMesh(geometry, materials.polyhedron);
        
        return {
            geometry,
            faceMap,
            faceVertexRanges,
            gridId
        };
    }

    /**
     * Sets up edge meshes and cross-references
     * @param {THREE.Mesh[]} edgeMeshes - Array of edge meshes
     */
    setupEdges(edgeMeshes) {
        this.sceneManager.addEdgeMeshes(edgeMeshes);
        this.puzzleGrid.setupCrossReferences(
            this.sceneManager.faceMap || new Map(),
            this.sceneManager.faceVertexRanges || new Map(),
            edgeMeshes
        );
    }

    /**
     * Sets up vertex group
     * @param {THREE.Group} vertexGroup - Group containing vertex meshes
     */
    setupVertices(vertexGroup) {
        this.sceneManager.addVertexGroup(vertexGroup);
    }

    /**
     * Sets up text elements
     * @param {THREE.Group} clueTexts - Group containing clue text objects
     * @param {THREE.Group} vertexLabels - Group containing vertex label objects
     */
    setupTextElements(clueTexts, vertexLabels) {
        this.sceneManager.addTextElements(clueTexts, vertexLabels);
    }

    /**
     * Sets up lighting
     */
    setupLighting() {
        return this.sceneManager.setupLighting();
    }

    /**
     * Toggles debug mode
     * @param {boolean} enabled - Whether to enable debug mode
     */
    toggleDebugMode(enabled) {
        this.debugMode = enabled;
        
        if (enabled) {
            // Add vertex labels to scene
            if (this.sceneManager.vertexLabels) {
                this.sceneManager.scene.add(this.sceneManager.vertexLabels);
            }
            
            // Highlight solution
            this.puzzleGrid.highlightSolution();
        } else {
            // Remove vertex labels from scene
            if (this.sceneManager.vertexLabels) {
                this.sceneManager.scene.remove(this.sceneManager.vertexLabels);
            }
            
            // Reset puzzle state (TODO: implement reset functionality)
            this.puzzleGrid.resetEdgeStates();
        }
    }

    /**
     * Gets the current debug mode state
     * @returns {boolean} Whether debug mode is enabled
     */
    isDebugMode() {
        return this.debugMode;
    }

    /**
     * Gets all data needed for interaction setup
     * @returns {Object} Interaction setup data
     */
    getInteractionData() {
        return {
            renderer: this.sceneManager.renderer,
            camera: this.sceneManager.camera,
            scene: this.sceneManager.scene,
            polyhedronMesh: this.sceneManager.polyhedronMesh,
            geometry: this.sceneManager.geometry,
            grid: this.puzzleGrid,
            faceMap: this.puzzleGrid.faceMap,
            faceVertexRanges: this.puzzleGrid.faceVertexRanges,
            edgeMeshes: this.puzzleGrid.getAllEdgeMeshes(),
            controls: this.sceneManager.controls
        };
    }

    /**
     * Gets all data needed for debugging
     * @returns {Object} Debug data
     */
    getDebugData() {
        return {
            grid: this.puzzleGrid,
            scene: this.sceneManager.scene,
            puzzleData: this.puzzleGrid.puzzleData,
            vertexLabels: this.sceneManager.vertexLabels,
            edgeMeshes: this.puzzleGrid.getAllEdgeMeshes()
        };
    }

    /**
     * Gets text visibility data
     * @returns {Object} Text visibility data
     */
    getTextVisibilityData() {
        return {
            clueTexts: this.sceneManager.clueTexts,
            camera: this.sceneManager.camera,
            grid: this.puzzleGrid
        };
    }

    /**
     * Handles window resize
     */
    onWindowResize() {
        this.sceneManager.onWindowResize();
    }

    /**
     * Renders the scene
     */
    render() {
        this.sceneManager.render();
    }

    /**
     * Cleans up resources
     */
    dispose() {
        if (this.interaction && this.interaction.dispose) {
            this.interaction.dispose();
        }
        this.sceneManager.dispose();
    }
}
