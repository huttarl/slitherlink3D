import { SceneManager } from './SceneManager.js';
import { PuzzleGrid } from './PuzzleGrid.js';

/**
 * Main application state container that manages all game components.
 * Provides a single entry point for accessing scene, grid, and interaction data.
 * Access the single instance via GameState.getInstance().
 * 
 * @class GameState
 */
export class GameState {
    constructor() {
        // Singleton pattern
        if (GameState._instance) {
            throw new Error('Use GameState.getInstance() instead of new');
        }

        this.sceneManager = new SceneManager();
        this.puzzleGrid = new PuzzleGrid();
        this.interaction = null;
        
        // Application state
        this.isInitialized = false;
        this.currentPuzzleIndex = 0;
        // this.showIDsMode = false; // not used
        // this.showSolutionMode = false; // not used

        // Try ar-EG, fa, mr, en, bn, ccp, dz-BT, my-MM
        // Not all of them will give different numerals. :-l
        this.numberLocale = 'en';
    }

    /**
     * Gets the singleton instance of GameState
     * @returns {GameState}
     */
    static getInstance() {
        if (!GameState._instance) GameState._instance = new GameState();
        return GameState._instance;
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

        // TODO why are we copying data from the grid, instead of inheriting it?
        // Copy grid data to our puzzle grid
        this.puzzleGrid.gridName = grid.gridName;
        this.puzzleGrid.vertices = grid.vertices;
        this.puzzleGrid.edges = grid.edges;
        this.puzzleGrid.faces = grid.faces;
        this.puzzleGrid.nextId = grid.nextId;
        this.puzzleGrid.vertexPairToEdge = grid.vertexPairToEdge;
        
        // Set up puzzle data
        this.puzzleGrid.setPuzzleData(puzzleData, gridId);
        // Clamp the requested puzzle index to the available range, so that
        // e.g. a stale ?puzzle= URL parameter (carried over from a grid
        // with more puzzles) degrades gracefully instead of throwing.
        if (this.currentPuzzleIndex >= puzzleData.puzzles.length) {
            console.warn(`Puzzle index ${this.currentPuzzleIndex} out of range; using the last puzzle.`);
            this.currentPuzzleIndex = puzzleData.puzzles.length - 1;
        }
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
     * @param {THREE.LineSegments} pickLines - Invisible lines picking aims at
     * @param {number[]} pickEdgeIds - Edge id of each of pickLines' segments
     */
    setupEdges(edgeMeshes, pickLines = null, pickEdgeIds = []) {
        this.sceneManager.addEdgeMeshes(edgeMeshes);
        this.sceneManager.addEdgePickLines(pickLines, pickEdgeIds);
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
     * @param {function(): THREE.Group[]} makeIdLabelGroups - builds the ID
     *     label groups (vertices, edges, faces); called on first use
     */
    setupTextElements(clueTexts, makeIdLabelGroups) {
        this.sceneManager.addTextElements(clueTexts, makeIdLabelGroups);
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

        const sceneManager = this.sceneManager;
        if (!enable && sceneManager.idLabelGroups === null) {
            // Never shown, so there is nothing to hide -- and no reason to build
            // the labels merely to take them back out of the scene.
            return;
        }
        // The groups are built on this first request, then kept, and belong to
        // the scene only while the setting is on. One loop over all three kinds,
        // so a fourth would need no new branch.
        for (const group of sceneManager.getIdLabelGroups()) {
            if (enable) {
                sceneManager.scene.add(group);
            } else {
                sceneManager.scene.remove(group);
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
