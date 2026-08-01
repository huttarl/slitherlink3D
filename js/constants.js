import * as THREE from './three/three.module.min.js';

// Shared constants for Slitherlink 3D

// Visual parameters for edge and vertex rendering
export const EDGE_RADIUS = 0.03;
export const VERTEX_RADIUS = 0.04;

// Camera movement constraints
export const CAMERA_MIN_ZOOM = 2;
export const CAMERA_MAX_ZOOM = 10;

// Mouse interaction threshold (pixels moved before considering it a drag)
export const DRAG_THRESHOLD_PIXELS = 5;

// Face color states
export const FACE_DEFAULT_COLOR = new THREE.Color(0xeeeeee);
export const FACE_HIGHLIGHT_COLOR = new THREE.Color(0x44ff44); // Used for debugging

// How fast the view spins while celebrating a solved puzzle.
export const CELEBRATION_SPIN_DEGREES_PER_SEC = 30;

// Grid (polyhedron) shown when the URL has no ?grid= parameter.
// The value is a data/ filename stem (see data/grids.json), which can
// differ from the grid's internal gridId.
export const DEFAULT_GRID = 'tI';

// Edge state machine configuration
export const EDGE_COLORS = {
    unknown: new THREE.Color(0x808080), // 50% gray
    filledIn: new THREE.Color(0x0000a0), // almost black
    ruledOut: new THREE.Color(0xf8f8f8), // almost white
    solution: new THREE.Color(0x66dd66), // green
    error: new THREE.Color(0xff8888), // red
};
export const EDGE_STATES = ['unknown', 'filledIn', 'ruledOut'];


