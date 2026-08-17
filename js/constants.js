import * as THREE from './three/three.module.min.js';

// Shared constants for Slitherlink 3D

// Visual parameters for edge and vertex rendering. These are MAXIMA, used as-is
// on the solid with the longest edges and scaled down on the rest; see
// radiusScale in geometryUtils.js.
export const EDGE_RADIUS = 0.03;
export const VERTEX_RADIUS = 0.04;

// How the edge and vertex radii follow the length of a grid's edges.
//
// Every solid is drawn to the same size, so its edges get shorter as it gains
// faces -- across data/ the median rendered edge runs from 1.633 on the
// tetrahedron down to 0.227 on etI, a factor of seven -- and a single radius for
// all of them looks fat on the crowded solids and spindly on the sparse ones.
//
// The exponent is a dial between the two things that don't work: 0 is one
// constant radius for every grid (what this used to do), and 1 is a radius
// proportional to edge length, which draws etI as hairlines. A third of the way
// along shrinks etI's radius to 54% of the maximum while leaving the cube's at
// 89%, which is the "a little thinner, and only a little" that was wanted.
//
// The reference is the longest edge anywhere in data/, the tetrahedron's, so that
// grid keeps the full radius and no grid can exceed it. A grid with longer edges
// than that would simply be clamped (see radiusScale).
export const RADIUS_LENGTH_EXPONENT = 1 / 4;
export const RADIUS_REFERENCE_EDGE = 1.633;

// How much thicker the edges and vertices are drawn for a finger (see
// hasCoarsePointer in pointer.js). The radii above suit a mouse: at the phone's
// scale a dense grid's tube comes out about 7 CSS pixels wide, which is fiddly to
// hit and hard to see under the finger covering it.
//
// The click target grows with it and stays twice the drawn tube, since radiusScale
// carries both -- so this widens what the player can see and what they can hit by
// the same factor, and the promise the constants make about the two stays true.
// Half again is the largest step that still looks like a wireframe on the dense
// solids, where 1.5 takes the tube to about a fifth of an edge's length. If a
// finger still wants more room, the honest next move is to let touch have a wider
// PICK_RADIUS_FACTOR than a mouse rather than to keep fattening the drawing.
export const COARSE_POINTER_RADIUS_FACTOR = 1.5;

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

// The board's opening move: the camera begins this multiple of CAMERA_DISTANCE
// out and closes in over CAMERA_INTRO_SECONDS, so the solid arrives rather than
// merely being there. A factor rather than a distance of its own, so retuning
// CAMERA_DISTANCE carries it along.
//
// It has to stay within CAMERA_MAX_ZOOM: the controls clamp the distance, so a
// start beyond their limit would be hauled back in on the first frame and the
// zoom would begin from the wrong place. 6 x 1.5 = 9 against a limit of 10, and
// a test in cameraIntro.test.js holds the two together.
export const CAMERA_INTRO_FACTOR = 1.5;
export const CAMERA_INTRO_SECONDS = 1.2;

// The longest single frame the opening zoom will believe in. Beyond this it runs
// in slow motion rather than skipping ahead, because a zoom the player never saw
// is worse than one that takes a moment longer than it meant to.
//
// It needs this and the render loop's re-baselined timer both. The board's first
// frames are its most expensive -- shaders compile, geometry uploads -- and on a
// phone one of them can cost a good fraction of a second. Against a whole
// animation of only CAMERA_INTRO_SECONDS, a single unclamped frame like that is
// most of the zoom, so the solid would already be sitting at its resting distance
// by the time anything was painted. 1/10 s is four frames' grace at 60fps: long
// enough to pass ordinary jitter through untouched, short enough that the worst
// stall costs the zoom a twelfth of its length instead of half.
export const CAMERA_INTRO_MAX_FRAME_SECONDS = 0.1;

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

// How far a clue digit is lifted clear of the surface it is painted on, BEYOND
// whatever the face's own curvature demands (see findFaceRise in geometryUtils.js
// and createTextMeshForFace in clueRenderer.js). Just enough to settle z-fighting
// between two surfaces that would otherwise be exactly coincident on a flat face.
//
// It used to be the whole story, at the same value, which was enough for as long as
// every face was flat. It is not enough for a bowed one: the fullerene cages have
// faces curved by about 2% of the radius -- twenty times this -- and their digits
// came out sliced in half by their own faces. The truncated icosahedron was already
// over the line at 0.0012, just invisibly.
export const CLUE_LIFT = 0.001;

// Mouse interaction threshold (pixels moved before considering it a drag)
export const DRAG_THRESHOLD_PIXELS = 5;

// The same threshold for a finger, which cannot hold as still as a mouse: a
// fingertip rolls as it presses, and its reported position is the centre of a
// contact patch that changes shape while it lands. 5 pixels of that is easy, and
// crossing the line doesn't merely widen the target -- it cancels the tap
// outright, and cancels a long press with it, so the board looks like it ignored
// the player. Double is enough for a settled press while staying far below the
// travel of a deliberate drag.
//
// Chosen per gesture from event.pointerType rather than per device, so a
// touchscreen laptop gets the tight threshold from its mouse and the loose one
// from its hand. That is a distinction the drawn radius cannot make (see
// pointer.js), which is why only this one is per gesture.
export const TOUCH_DRAG_THRESHOLD_PIXELS = 10;

// How near an edge a click has to land to count, as a radius around the edge's
// centre line: the drawn cylinders are thin enough that hitting one exactly is
// fiddly, especially on a phone. Twice the drawn radius, so the target is
// effectively twice as wide.
//
// TWICE THE DRAWN RADIUS IS THE POINT, so this follows radiusScale along with the
// radius itself -- see pickTolerances in geometryUtils.js, and PICK_RADIUS here is
// the maximum, reached where the edges are longest. Left absolute at first, on the
// reasoning that a thinner edge should be no harder to hit; that was wrong in
// practice. On etI the edges are a quarter the length of a tetrahedron's, so a
// fixed 0.06 of slack reached a fifth of the way along one, and picks near a
// vertex or between two edges resolved unpredictably -- the tolerance was wider
// than the gaps it had to distinguish.
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

// What a player can record about a PAIR of edges meeting at a vertex, as an index
// into this array -- the same shape as EDGE_STATES above, and 'none' is index 0 so
// that an unmarked pair is falsy and a cycle starts and ends there.
//
// The names and the logic are the solver's, not new ones: see
// docs/edge-pair-constraints.md and EdgePairing in util/slisolver.py, which
// already reasons with all four.
//
//     exactlyOne      a XOR b    the two edges disagree      -- one arc
//     bothOrNeither   a XNOR b   the two edges agree         -- two arcs
//
// Only the two PARITY relations are offered. The solver's other two ('at least
// one', 'at most one') are clauses rather than equivalences, have no established
// notation to draw, and are the weaker deductions of the four; adding them means
// inventing glyphs, which is a decision to postpone rather than guess at.
export const PAIR_RELATIONS = ['none', 'exactlyOne', 'bothOrNeither'];

// The arcs that draw a pair mark across a face corner (see js/pairMarkRenderer.js).
//
// Teal: it has to be told apart at a glance from everything else already on a face
// -- the near-white surface, the black and gray clue digits, and the gray, blue and
// white edge states -- so a saturated hue no other element uses.
export const PAIR_MARK_COLOR = new THREE.Color(0x1a86a8);
// How far from the corner the arc sits, as a fraction of the SHORTER of its two
// edges -- a fraction of the EDGES rather than of the face, so the arc's ends always
// land on both of them however oddly shaped the face is, which is what makes it read
// as joining those two and not some other pair.
//
// TWO radii, chosen by the corner's ANGLE and interpolated between, because one
// radius cannot serve both ends of the range. An arc of angular span t at radius r
// draws a line of length r*t, so at a single radius a 30-degree corner shows barely a
// quarter the ink of a 120-degree one: the sharp corners were too small to read while
// the obtuse ones sprawled over most of the face.
//
// Holding the arc LENGTH constant instead is the tidier idea and over-corrects badly:
// matched to 0.32 at 30 degrees it wants 0.107 at 90, which lands the arc almost on
// the vertex sphere. This ramp is the partial correction that measurement and the eye
// agreed on -- it leaves 90-degree corners at 0.227, near the 0.22 that looked right
// before any of this, and only pulls the genuinely wide ones in.
//
// Angles outside the two named ones are clamped, not extrapolated: 34.6 degrees
// (data/spiral10.json's sharpest) and 120 (a hexagon of data/tI.json) are close to
// the real range, and a 150-degree corner wanting a still smaller arc is not a case
// worth guessing at.
export const PAIR_ARC_RADIUS_SHARP = 0.28;
export const PAIR_ARC_SHARP_DEGREES = 30;
export const PAIR_ARC_RADIUS_WIDE = 0.12;
export const PAIR_ARC_WIDE_DEGREES = 120;

// The stroke's width, and the gap between the two arcs of a double. Fractions of the
// shorter edge, NOT of the radius above: now that the radius varies with the angle, a
// stroke defined against it would thin out on exactly the wide corners where the
// radius is smallest. A pen doesn't change width with the size of the arc.
//
// Both are deliberately finer than the first attempt, which set them against the
// radius at 0.22 and 0.30 -- 0.048 and 0.066 of an edge as drawn. They stay legible
// smaller, and every bit saved here is headroom for the radius: two corners at the
// ends of one edge collide when 2 * (radius + gap + width / 2) passes 1, which these
// put at a radius of 0.436 rather than the 0.355 of the version before.
//
// Note the gap affects BOTH relations, not just the double: arcs fill inward from a
// fixed outermost slot at radius + gap, so a single arc is drawn there too. See
// OUTERMOST_SLOT in pairMarkRenderer.js.
export const PAIR_ARC_WIDTH = 0.032;
export const PAIR_ARC_GAP = 0.048;

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
    // What the loop GLOWS, as emissive light added to its own dark blue rather
    // than a colour mixed into it. That distinction is the whole reason it works:
    // the first version brightened the loop by mixing toward a near-white cyan,
    // which desaturated it until it faded into the pale board around it. Emissive
    // blue gets brighter while staying blue.
    glow: new THREE.Color(0x2244ff),
    // Where the loop's own colour ends up once the glow has subsided: black, not
    // the blue it is played in. That blue sat badly against the amber and teal the
    // faces take during the same beat; black reads as a line drawn over them.
    loopSettled: new THREE.Color(0x000000),
    // What the edges NOT in the loop fade to. EDGE_COLORS.ruledOut, which is
    // where they were heading anyway: a solved board's non-loop edges ARE ruled
    // out. Being near-white they also blend into the faces, so the loop stands
    // alone. A DARK fade was tried first and was worse -- it made every other
    // edge look like the dark blue of the loop itself.
    quiet: EDGE_COLORS.ruledOut,
    // The two sides of the loop, for the partition fade -- the beat that shows
    // what the loop actually DID: a closed curve on a closed surface cuts it in
    // two, and these are the two pieces.
    //
    // Chosen against three constraints, which rule out most obvious pairs. Not
    // red or green, which this app already spends on "error" and "solution" -- red
    // faces at the moment of winning would read as a mistake. Not blue, which is
    // the loop's own colour and would camouflage it. And both must stay LIGHT,
    // because the black clue digits sit on these faces and have to stay readable.
    //
    // Amber against teal is the warm/cool pair that survives colour blindness:
    // it lies along the orange-blue axis, which both red-green dichromacies leave
    // intact. The slight lightness difference between them is insurance for the
    // rare blue-yellow case, and means they separate in greyscale too.
    partitionWarm: new THREE.Color(0xf0d3a0), // pale amber, the deeper of the two
    partitionCool: new THREE.Color(0xa9d8e0), // pale teal, clear of the loop's navy
};

export const CELEBRATION_TIMING = {
    // Beat 1: the loop takes up its glow and thickens, and the other edges fade
    // toward the ruled-out near-white, leaving the loop alone on the solid.
    clearSeconds: 0.4,
    // How dimmed the non-loop edges stay. Not 0: the loop should keep standing
    // out. Not 1 either, or the solid would read as permanently half-drawn.
    settleDimFraction: 0.35,
    // The loop's edges swell and then return to their normal size, all together.
    // A swell that STAYED read as the loop having been permanently redrawn
    // thicker, rather than as something happening to it. thickenFactor is the
    // size at the peak, swellSeconds ONE whole there-and-back.
    thickenFactor: 1.5,
    swellSeconds: 0.9,
    // How many of those, back to back: one per cycle of the tune, so the loop
    // pulses with the music rather than under it. With a single swell against the
    // tune's two cycles, the two started together and then the loop went still
    // while the music carried on -- which read as the animation having finished
    // early. swellSeconds * swellCycles is therefore the tune's short notes,
    // 12 * 0.075 * 2 = 1.8s; a test in celebration.test.js keeps them equal, since
    // they live apart on purpose (the visual has to stand alone when audio is
    // blocked or, one day, muted).
    swellCycles: 2,

    // The glow at its peak, as emissive intensity. It rides the same envelope as
    // the swell -- up together, down together -- and ends at nothing, the loop
    // going black as it subsides. So this is a flash, not a resting state: an
    // earlier version left the loop breathing indefinitely, which fought the
    // partition colours for attention once they arrived.
    glowPeak: 0.8,

    // Beat 2: the two sides of the loop take their colours -- the whole surface
    // at once, fading from its near-white. Animating this as a spreading front
    // was tried twice and dropped both times; see faceColors in celebration.js
    // for why neither ordering meant anything.
    partitionStartSeconds: 0.5,
    partitionSeconds: 1.5,

    // Beat 3: the tumble, which now has a job rather than being a flourish -- you
    // cannot see a partition of a closed surface from one side, so this is what
    // shows the two regions carrying on round the back.
    tumbleSeconds: 2.1,
    // Beat 4: the dialog last of all, since the box (at least partially)
    // hides the very thing it congratulates.
    dialogSeconds: 5,
};

// The little tune that plays over the celebration: up the scale and back, twice,
// then a held note. Letters are scale degrees around middle C -- A and B are the
// two BELOW it, so "C B A B C" dips under the tonic and returns, which is what
// makes the phrase settle rather than just stop. See js/celebrationSound.js.
//
// The phrase and how many times it goes round are named rather than written out
// twice, because the loop's swell is paced to them: one swell per repeat (see
// swellCycles above, and the test that holds the two together).
const TUNE_PHRASE = 'C D E F G F E D C B A B'.split(' ');
const TUNE_REPEATS = 2;

const TUNE_NOTES = [];
for (let repeat = 0; repeat < TUNE_REPEATS; repeat++) {
    TUNE_NOTES.push(...TUNE_PHRASE);
}
TUNE_NOTES.push('C');       // the held tonic, which ends the phrase

export const CELEBRATION_TUNE = {
    phrase: TUNE_PHRASE,
    repeats: TUNE_REPEATS,
    notes: TUNE_NOTES,
    // Rapid: at this length the 24 short notes run just under two seconds, so the
    // phrase tracks beats 1 and 2 and the held note lands as the dialog opens.
    noteSeconds: 0.075,
    holdSeconds: 1.0,
    // Quiet enough to be a flourish rather than an event. A triangle wave for a
    // soft electronic tone -- a square wave at this speed is a machine alarm.
    peakGain: 0.14,
    waveform: 'sine',
};


