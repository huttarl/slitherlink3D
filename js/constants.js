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

// Light intensities, as plain multipliers (see SceneManager.setupLighting for
// what each light is FOR). Grouped because they only make sense relative to each
// other: what matters is the ratio between the key and the fill, and how little
// of the total comes from the ambient floor.
//
// Measured rather than guessed. With the original 0.45/0.55/0.75 the brightest
// pixel anywhere on the solid was 182 of 255 and nothing clipped, so a third of
// the range was going unused -- which is why the solid read as gray. These raise
// the two directional lights hard and the ambient floor barely, since raising
// ambient is the one change that would brighten the solid by FLATTENING it:
// it lifts every face equally and so washes out the shading that reads as shape.
export const LIGHT_INTENSITIES = {
    ambient: 0.5,
    directional: 0.7,
    headlight: 1.15,
};

// The three palettes below are all THREE.Color objects keyed by state name, so
// they read alike and a color can be moved between them. Note that these are the
// colors as AUTHORED: what reaches the screen is lit, and the polyhedron's
// material is Phong, so a face's default near-white renders anywhere from white
// where the headlight strikes it square to a middling gray where it doesn't.

// Face color states
export const FACE_COLORS = {
    default: new THREE.Color(0xeeeeee), // almost white
    highlight: new THREE.Color(0x44ff44), // green; used for debugging
};

// Edge state machine configuration
export const EDGE_COLORS = {
    unknown: new THREE.Color(0x808080), // 50% gray
    filledIn: new THREE.Color(0x0000a0), // almost black
    ruledOut: new THREE.Color(0xf8f8f8), // almost white
    solution: new THREE.Color(0x66dd66), // green
    error: new THREE.Color(0xff8888), // red
};
export const EDGE_STATES = ['unknown', 'filledIn', 'ruledOut'];

// Clue digit colors. A clue whose walls are all accounted for goes gray, leaving
// the black digits as the list of what is still to do.
//
// These reach the screen by a longer route than the other two palettes: the
// digits are drawn into a 2D canvas, which becomes a texture (see
// clueRenderer.js), so each is converted to a CSS string with .getStyle(). Kept
// as THREE.Color anyway, so that all three palettes hold the same kind of thing
// and the conversion stays where the canvas is.
//
// The gray must read as quieter than black while staying DARKER than the face
// under it, which is why the digits are lit by the same lights as the faces:
// see makeDigitMaterials.
export const CLUE_COLORS = {
    unsatisfied: new THREE.Color(0x000000), // black
    satisfied: new THREE.Color(0x808080), // 50% gray, as an unmarked edge
};

// Celebrating a solve: a pulse of light running round the solution loop. See
// docs/celebration.md for why this and not confetti, and js/celebration.js for
// the sequence these drive.
export const CELEBRATION_COLORS = {
    // The travelling head. Near-white with a cyan cast, so it reads as light on
    // the loop rather than as another edge state.
    pulse: new THREE.Color(0xeaffff),
    // What the edges NOT in the loop fade to, so the loop is briefly the only
    // thing drawn. Dark rather than transparent: they still describe the solid's
    // shape, and losing them entirely makes it read as a different polyhedron.
    quiet: new THREE.Color(0x2a2a33),
};

export const CELEBRATION_TIMING = {
    // Beat 1: fading the non-loop edges down.
    clearSeconds: 0.3,
    // Beat 2: one circuit of the loop, head returning to where it started --
    // which is what shows the loop is closed. Slow enough for the eye to follow
    // round the back of the solid, which it cannot see.
    pulseSeconds: 1.2,
    // How much of the loop the pulse's trail covers, as a fraction of its length.
    // Long enough to read as motion, short enough that the head is distinct.
    trailFraction: 0.22,
    // Beat 3: the shimmer it settles into, and keeps up while the player looks
    // around. Low amplitude and slow, so it marks the board as solved without
    // asking for attention.
    shimmerAmplitude: 0.22,
    shimmerCyclesPerSecond: 0.3,
    // How long beat 2 takes to become beat 3 -- the pulse easing down to the
    // shimmer and the other edges coming back up. Long enough not to look like a
    // cut, short enough that it is over before the dialog opens.
    settleSeconds: 0.6,
    // How dimmed the non-loop edges stay once settled. Not 0: the loop should
    // still stand out afterwards. Not 1 either, or the solid would read as
    // permanently half-drawn.
    settleDimFraction: 0.35,
    // How much thicker the loop's edges get at the height of the pulse, easing
    // back to 1 as it settles. The cord pulled taut.
    thickenFactor: 2.0,
    // When the celebration dialog appears. The box is centered over the solid, so
    // anything played underneath it is half hidden; this lets the loop have the
    // stage first, and by the time it opens the sequence is in its quiet state.
    dialogSeconds: 2.0,
};


