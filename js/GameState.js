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
        this.showIDsMode = false;
        this.showSolutionMode = false;
        // Try ar-EG, fa, mr, en, bn, ccp, dz-BT, my-MM
        // Not all of them will give different numerals. :-l
        this.numberLocale = 'en';
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
        this.puzzleGrid.validatePuzzleSolution();
        
        // Set up scene manager with geometry
        this.sceneManager.addPolyhedronMesh(geometry, materials.polyhedron);
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
     * @param {THREE.Group} edgeLabels - Group containing edge label objects
     */
    setupTextElements(clueTexts, vertexLabels, edgeLabels) {
        this.sceneManager.addTextElements(clueTexts, vertexLabels, edgeLabels);
    }

    /**
     * Sets up lighting
     */
    setupLighting() {
        return this.sceneManager.setupLighting();
    }

    /**
     * Toggles mode that shows ID labels
     * @param {boolean} enable - Whether to enable mode
     */
    toggleShowIDs(enable) {
        this.showIDsMode = enable;
        
        if (enable) {
            // Add ID labels to scene
            if (this.sceneManager.vertexLabels) {
                this.sceneManager.scene.add(this.sceneManager.vertexLabels);
            }
            if (this.sceneManager.edgeLabels) {
                this.sceneManager.scene.add(this.sceneManager.edgeLabels);
            }
        } else {
            // Remove ID labels from scene
            if (this.sceneManager.vertexLabels) {
                this.sceneManager.scene.remove(this.sceneManager.vertexLabels);
            }
            if (this.sceneManager.edgeLabels) {
                this.sceneManager.scene.remove(this.sceneManager.edgeLabels);
            }
        }
    }

    /**
     * Toggles mode that shows solution
     * @param {boolean} enable - Whether to enable mode
     */
    toggleShowSolution(enable) {
        this.showSolutionMode = enable;

        if (enable) {
            // Highlight solution
            this.puzzleGrid.highlightPuzzleSolution(); // Disable for now; control separately
        } else {
            // Remove solution highlight
            this.puzzleGrid.clearEdgeHighlights();
        }
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
