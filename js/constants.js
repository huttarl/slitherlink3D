import * as THREE from 'three';

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

// Edge state machine configuration
export const EDGE_COLORS = {
    unknown: new THREE.Color(0x808080), // 50% gray
    filledIn: new THREE.Color(0x111111), // almost black
    ruledOut: new THREE.Color(0xf8f8f8) // almost white
};
export const EDGE_STATES = ['unknown', 'filledIn', 'ruledOut'];


