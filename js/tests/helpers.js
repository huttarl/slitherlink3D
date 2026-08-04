/**
 * Shared helpers for the JS test suite (run with: node --test js/tests).
 *
 * Builds small, real Grid/PuzzleGrid instances headlessly -- no THREE
 * meshes, no DOM. Vertex positions are stubs, since only topology matters
 * to the logic under test. (This file doesn't match Node's test-file
 * naming convention, so the runner won't try to execute it as tests.)
 */
import { Grid } from '../Grid.js';
import { PuzzleGrid } from '../PuzzleGrid.js';

// Grid.addVertex only needs something with clone(); geometry is irrelevant here.
function stubPosition() {
    return { clone() { return this; } };
}

// The same cube as util/tests/test_slisolver.py's fixture:
// 8 vertices (0-3 bottom, 4-7 top), 6 quad faces, 12 edges.
export const CUBE_FACES = [
    [0, 3, 2, 1],   // 0: bottom
    [4, 5, 6, 7],   // 1: top
    [0, 1, 5, 4],   // 2: front
    [1, 2, 6, 5],   // 3: right
    [2, 3, 7, 6],   // 4: back
    [3, 0, 4, 7],   // 5: left
];

/** Populate the given grid (Grid or PuzzleGrid) with cube topology. */
export function buildCubeTopology(grid) {
    for (let v = 0; v < 8; v++) {
        grid.addVertex(stubPosition(), {}, v);
    }
    CUBE_FACES.forEach((face, i) => {
        // Mirror createPolyhedron's face metadata (the parts logic depends on).
        grid.addFace(face, { index: i, clue: -1 }, i);
    });
    for (const [_edgeId, edge] of grid.edges) {
        edge.metadata.userGuess = 0; // 0 = unknown
    }
    return grid;
}

/** A bare cube Grid. */
export function makeCubeGrid() {
    return buildCubeTopology(new Grid());
}

/**
 * A cube PuzzleGrid with one puzzle loaded and its clues applied.
 * @param {number[]} clues - clue array indexed by face (-1 = no clue)
 * @param {number[]} solution - the solution loop as a vertex ID list
 */
export function makeCubePuzzleGrid(clues, solution) {
    const pg = buildCubeTopology(new PuzzleGrid());
    pg.setPuzzleData({ gridId: 'testCube', puzzles: [{ clues, solution }] }, 'testCube');
    pg.setCurrentPuzzle(0);
    pg.applyCurrentPuzzleClues();
    return pg;
}

/** Builds a grid from a list of faces, each a list of vertex IDs. */
function makeGridFromFaces(faceList, numVertices) {
    const grid = new Grid();
    for (let v = 0; v < numVertices; v++) {
        grid.addVertex(stubPosition(), {}, v);
    }
    faceList.forEach((face, i) => grid.addFace(face, { index: i, clue: -1 }, i));
    return grid;
}

/**
 * A tetrahedron Grid: 4 vertices, 4 triangles, 6 edges. Every vertex alike
 * (3.3.3), so it exercises the uniform-vertex case with triangles.
 */
export function makeTetrahedronGrid() {
    return makeGridFromFaces([[0, 1, 2], [0, 2, 3], [0, 3, 1], [1, 3, 2]], 4);
}

/**
 * A square pyramid Grid (Johnson solid J1): a square base and 4 triangles.
 * Its vertices are NOT all alike -- the apex meets four triangles, each base
 * corner two triangles and the square -- which is what makes it the useful
 * negative case for vertexConfiguration.
 */
export function makeSquarePyramidGrid() {
    return makeGridFromFaces(
        [[0, 1, 2, 3], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]], 5);
}

/**
 * Set the guess state of the edge between two vertices, directly
 * (bypassing undo history).
 * @returns {number} the edge's ID
 */
export function setEdge(grid, v1, v2, state) {
    const edgeId = grid.findEdgeByVertices(v1, v2);
    if (edgeId == null) throw new Error(`no edge between v${v1} and v${v2}`);
    grid.edges.get(edgeId).metadata.userGuess = state;
    return edgeId;
}

/** The consecutive vertex pairs of a loop, including last-to-first. */
export function loopVertexPairs(loop) {
    return loop.map((v, i) => [v, loop[(i + 1) % loop.length]]);
}
