import * as THREE from './three/three.module.min.js';

// Shared constants for Slitherlink 3D

// Visual parameters for edge and vertex rendering
export const EDGE_RADIUS = 0.03;
export const VERTEX_RADIUS = 0.04;

// Camera movement constraints
export const CAMERA_MIN_ZOOM = 2;
export const CAMERA_MAX_ZOOM = 10;

// How far the camera starts from the solid (which is normalized to a
// circumradius near 1), in the same units as the zoom limits above.
export const CAMERA_DISTANCE = 6;

// How far above the solid's equator the camera starts, so the first view of it
// is slightly from above rather than dead-on. Its real distance from the solid
// is therefore hypot(CAMERA_DISTANCE, CAMERA_HEIGHT), a little more than the
// distance asked for.
export const CAMERA_HEIGHT = 1;

// The camera's vertical field of view, in degrees. A perspective camera's fov is
// the VERTICAL one, so the horizontal view depends on the viewport's aspect
// ratio -- which is why a tall phone screen sees less of the solid at a given
// distance than a wide desktop window does (see titleScreenCameraDistance).
export const CAMERA_FOV_DEGREES = 35;

// How much of the frame the solid should span on the title screen, as a fraction
// of the narrower field of view. Higher than a board's framing: nothing here has
// to be clicked, so the solid can be big -- which also gets the interesting part
// of it out from behind the centred title box. Under 1 so it isn't cropped.
export const TITLE_SCREEN_FILL = 0.85;

// Mouse interaction threshold (pixels moved before considering it a drag)
export const DRAG_THRESHOLD_PIXELS = 5;

// How near an edge a click has to land to count, as a radius around the edge's
// centre line: the drawn cylinders are thin enough that hitting one exactly is
// fiddly, especially on a phone. Twice the drawn radius, so the target is
// effectively twice as wide.
//
// Applied as raycaster.params.Line.threshold against a LineSegments standing in
// for the edges -- threshold only exists for Line and Points, never for Mesh,
// whose raycast is exact triangle intersection. Being a raycaster parameter
// rather than geometry, it can be changed at any time without rebuilding
// anything, which is what would make a zoom-dependent (constant on screen)
// tolerance easy: scale it by camera distance. It's in world units today, so it
// covers fewer pixels when zoomed out.
export const PICK_RADIUS_FACTOR = 2;
export const PICK_RADIUS = EDGE_RADIUS * PICK_RADIUS_FACTOR;

// How much farther than the nearest face an edge may be and still count as
// picked. The solid is opaque, so an edge behind it must not be clickable
// (see pickAt); but an edge's centre line lies ON the surface, and a tolerant
// pick reports the depth where the ray passes closest to that line, which can
// be a little beyond the face beside it -- especially at a grazing angle near
// the silhouette. Two pick radii of slack covers that, while the margin to a
// BACK edge is on the order of the solid's diameter -- solids are normalized to
// a circumradius near 1 -- so this can't let one through except right at the
// rim, where near and far surfaces meet and the distinction stops meaning much.
export const PICK_DEPTH_TOLERANCE = PICK_RADIUS * 2;

// How long a touch must be held to count as a long press, which cycles an
// edge's state backwards -- the touch equivalent of shift+click, since a phone
// has no shift key. Matches the ~500ms most platforms use for their own
// long-press gestures, so it should feel neither twitchy nor sluggish.
export const LONG_PRESS_MS = 500;

// How fast the view turns while tumbling (see SceneManager.updateTumble).
// Celebrating a solve is one caller of the tumble. If some
// other use wants a different speed, that belongs in a parameter to
// startTumble rather than a second constant here.
export const TUMBLE_DEGREES_PER_SEC = 30;

// Trackball controls (the default style). Both are feel settings; tune here.
// How much rotation a drag produces. TrackballControls' own default is 1.0,
// where dragging the full width of the canvas turns the view roughly 115 deg.
export const TRACKBALL_ROTATE_SPEED = 3.0;
// How quickly the camera catches up to the pointer, 0..1: each frame it closes
// this fraction of the remaining rotation. Low values feel laggy and jerky
// (the camera trails the drag for many frames); 1.0 tracks the pointer exactly
// with no glide at all.
export const TRACKBALL_DAMPING = 0.5;

// How long the "Right side up" button takes to rotate the view level.
// Instant would be disorienting; this is short enough not to feel sluggish.
export const LEVEL_CAMERA_SECONDS = 0.5;

// Grid (polyhedron) the player starts on: what "Start" loads, and what a
// ?grid=-less URL falls back to.
// The value is a data/ filename stem (see data/grids.json), which can
// differ from the grid's internal gridId.
// The tetrahedron: the simplest possible board, the right place for a
// newcomer to learn the rules. Revisit once progress is saved (start where
// the player left off).
export const DEFAULT_GRID = 'T';

// Which solids may appear tumbling behind the title screen: any playable grid
// with more than this many faces, picked at random per launch (see
// chooseTitleScreenGrid). Not a board to be played, so the criteria are the
// opposite of DEFAULT_GRID's: as impressive as we can afford, and a different
// one each time you arrive.
//
// The face count is a proxy for "this grid has several puzzles", so that showing
// one of them off -- eventually with its solution loop drawn on it -- can't spoil
// a grid's only puzzle.
export const TITLE_SCREEN_MIN_FACES = 11;

// Used when the catalogue can't be read, so the pick can't be made: a solid we
// know is there and comfortably meets the criteria (the rhombicosidodecahedron,
// 62 faces of three kinds, intricate from any angle).
export const TITLE_SCREEN_FALLBACK_GRID = 'eD';

// Face color states
export const FACE_DEFAULT_COLOR = new THREE.Color(0xeeeeee);
export const FACE_HIGHLIGHT_COLOR = new THREE.Color(0x44ff44); // Used for debugging

// Edge state machine configuration
export const EDGE_COLORS = {
    unknown: new THREE.Color(0x808080), // 50% gray
    filledIn: new THREE.Color(0x0000a0), // almost black
    ruledOut: new THREE.Color(0xf8f8f8), // almost white
    solution: new THREE.Color(0x66dd66), // green
    error: new THREE.Color(0xff8888), // red
};
export const EDGE_STATES = ['unknown', 'filledIn', 'ruledOut'];

// Clue digit colors. Unlike EDGE_COLORS these are CSS color strings, not
// THREE.Color: the digits are drawn into a 2D canvas by clueRenderer.js, which
// then uses it as a texture, so they are set as fillStyle/strokeStyle.
//
// A clue whose walls are all accounted for goes gray, leaving the black digits
// as the list of what is still to do. The gray has to stay legible against
// FACE_DEFAULT_COLOR (0xeeeeee) while reading as clearly quieter than black,
// which is what the same 50% gray as an unmarked edge does.
export const CLUE_COLORS = {
    unsatisfied: '#000000',
    satisfied: '#808080',
};


