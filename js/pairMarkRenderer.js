/**
 * Drawing the player's pair marks: arcs across a face corner recording how that
 * corner's two edges are related. One arc for "exactly one", two concentric arcs
 * for "both or neither" -- the notation hand-solvers already use.
 *
 * The model is PuzzleGrid's (pairMarks, PAIR_RELATIONS); this only draws it, and
 * is driven by the onPairMarkChanged observer that ui.js registers. See
 * docs/edge-pair-constraints.md for why a mark lives on a corner at all, and why
 * only the two parity relations are offered.
 *
 * REAL GEOMETRY, not a texture, which is the one decision worth explaining. A
 * canvas-textured plane -- the way clueRenderer draws digits -- would have to bake
 * in one arc angle, and a corner's angle is whatever the solid makes it: 34
 * degrees on data/spiral10.json, 108 on a pentagon of data/tI.json. A fixed arc
 * would visibly fail to meet its two edges on most of them. THREE.RingGeometry
 * takes thetaStart and thetaLength, so an annulus sector of exactly the corner's
 * angle costs nothing extra.
 *
 * NO PER-FRAME WORK, and none needed. clueRenderer's digits are re-oriented and
 * culled every frame for two reasons that don't apply here: they roll to stay
 * upright toward the camera, while an arc is tied to two specific edges and must
 * stay put; and their material is `transparent`, so they can draw through the
 * solid and have to be hidden by hand on faces turned away. These arcs are opaque
 * geometry, so the depth buffer occludes the far side for free.
 */
import * as THREE from './three/three.module.min.js';
import {CLUE_LIFT, PAIR_ARC_GAP, PAIR_ARC_RADIUS_SHARP, PAIR_ARC_RADIUS_WIDE,
        PAIR_ARC_SHARP_DEGREES, PAIR_ARC_WIDE_DEGREES, PAIR_ARC_WIDTH,
        PAIR_MARK_COLOR} from './constants.js';
import {findCentroid, findFaceNormal, findFaceRise,
        freezeTransform} from './geometryUtils.js';
import {PuzzleGrid} from './PuzzleGrid.js';
import {debug} from './debug.js';

// Segments along an arc. A corner spans at most ~150 degrees on anything we ship,
// so 24 keeps the curve smooth without making a mark cost real geometry.
const ARC_SEGMENTS = 24;

/**
 * How far out to put the arc, given how wide the corner is: further on a sharp
 * corner, nearer on a wide one. See the note on PAIR_ARC_RADIUS_SHARP for why one
 * radius cannot serve both.
 *
 * @param {number} angle - the corner's angle, in radians
 * @returns {number} the radius, as a fraction of the corner's shorter edge
 */
function radiusForAngle(angle) {
    const degrees = THREE.MathUtils.radToDeg(angle);
    // Clamped, so a corner outside the named range gets the nearer endpoint's
    // radius rather than an extrapolation.
    const howWide = THREE.MathUtils.clamp(
        (degrees - PAIR_ARC_SHARP_DEGREES)
            / (PAIR_ARC_WIDE_DEGREES - PAIR_ARC_SHARP_DEGREES), 0, 1);
    return THREE.MathUtils.lerp(PAIR_ARC_RADIUS_SHARP, PAIR_ARC_RADIUS_WIDE, howWide);
}

/**
 * Creates the (initially empty) group the marks live in.
 *
 * The shared material and the index of drawn marks hang off the group's userData
 * rather than living as module state, for the reason clueRenderer gives about its
 * digit materials: module state would be shared across every board the page ever
 * builds, and there is no reason for one board's marks to know about another's.
 *
 * @returns {THREE.Group}
 */
export function createPairMarkGroup() {
    const group = new THREE.Group();
    // ONE material for every arc on the board. Lit, not unlit, for clueRenderer's
    // reason: an unlit mark keeps full brightness on a face turned away from the
    // light, and would then stand out more on the solid's dark side than on the
    // side being looked at. DoubleSide so a face whose winding is unexpected still
    // shows its marks rather than silently dropping them.
    group.userData.material = new THREE.MeshLambertMaterial({
        color: PAIR_MARK_COLOR,
        side: THREE.DoubleSide,
    });
    // pairKey -> the Object3D drawn for it, so a change can find and replace it.
    group.userData.drawn = new Map();
    freezeTransform(group);
    return group;
}

/**
 * Everything needed to place an arc in a corner: where the corner is, which way
 * its two edges run, and how the face it sits on is oriented.
 *
 * @param {PuzzleGrid} grid
 * @param {number} edgeA
 * @param {number} edgeB
 * @returns {Object|null} null if the two edges share no vertex or no face, which
 *     PuzzleGrid.pairProblem should already have prevented
 */
function cornerFrame(grid, edgeA, edgeB) {
    const a = grid.edges.get(edgeA);
    const b = grid.edges.get(edgeB);
    if (!a || !b) return null;
    const vertexId = a.vertexIDs.find(v => b.vertexIDs.includes(v));
    const faceId = [...a.faceIDs].find(f => b.faceIDs.has(f));
    if (vertexId === undefined || faceId === undefined) return null;

    const here = grid.vertices.get(vertexId).position;
    const endOf = edge => grid.vertices.get(
        edge.vertexIDs.find(v => v !== vertexId)).position;

    const faceVertices = grid.getFaceVertices(grid.faces.get(faceId));
    // From the winding, which grid_checks and grid_quality both verify is
    // outward. Deliberately NOT corrected against the solid's centre the way
    // interaction.js does: that correction assumes the solid encloses the origin,
    // which is true of everything we ship and false of the first toroidal grid
    // (see ideas/genus-1-objects.md).
    const normal = findFaceNormal(faceVertices);
    const middle = findCentroid(faceVertices);

    let alongA = new THREE.Vector3().subVectors(endOf(a), here);
    let alongB = new THREE.Vector3().subVectors(endOf(b), here);
    // Everything is sized from the SHORTER edge, so both ends of the arc land on an
    // edge whichever of the two is stubbier.
    const shorterEdge = Math.min(alongA.length(), alongB.length());
    alongA.normalize();
    alongB.normalize();
    // A RingGeometry sweeps from its +X toward its +Y, so alongA has to be the
    // start of the turn. If the turn from A to B runs the other way about the
    // normal, swap them; otherwise the arc would sweep the long way round, across
    // the whole face instead of over the corner.
    if (new THREE.Vector3().crossVectors(alongA, alongB).dot(normal) < 0) {
        [alongA, alongB] = [alongB, alongA];
    }

    const angle = alongA.angleTo(alongB);
    return {
        here,
        normal,
        alongA,
        angle,
        // The radius answers to the ANGLE, the stroke and the spacing don't: see the
        // notes on PAIR_ARC_RADIUS_SHARP and PAIR_ARC_WIDTH for both halves of that.
        radius: radiusForAngle(angle) * shorterEdge,
        width: PAIR_ARC_WIDTH * shorterEdge,
        gap: PAIR_ARC_GAP * shorterEdge,
        // Clear of the surface, as the clue digits are: past whatever this face's
        // curvature raises under the arc, then CLUE_LIFT to settle the z-fighting.
        // A flat face gives a rise of 0.
        lift: findFaceRise(faceVertices, normal, here.distanceTo(middle)) + CLUE_LIFT,
    };
}

/**
 * One arc of a mark: an annulus sector spanning the corner, at `spacing` times the
 * frame's radius.
 *
 * @param {Object} frame - from cornerFrame
 * @param {THREE.Material} material
 * @param {number} ring - 0 for the inner arc, 1 for the outer one
 * @returns {THREE.Mesh}
 */
function arcMesh(frame, material, ring) {
    const middle = frame.radius + ring * frame.gap;
    const half = frame.width / 2;
    const mesh = new THREE.Mesh(
        new THREE.RingGeometry(middle - half, middle + half, ARC_SEGMENTS, 1,
                               0, frame.angle),
        material);
    mesh.position.copy(frame.here).addScaledVector(frame.normal, frame.lift);
    // Basis (X, Y, Z) = (along the first edge, the turn's direction, the face
    // normal). Right-handed, since alongA is perpendicular to the normal, so the
    // arc is rotated into the corner rather than mirrored.
    const turn = new THREE.Vector3().crossVectors(frame.normal, frame.alongA);
    mesh.quaternion.setFromRotationMatrix(
        new THREE.Matrix4().makeBasis(frame.alongA, turn, frame.normal));
    // The solid never moves; see freezeTransform.
    freezeTransform(mesh);
    return mesh;
}

/**
 * Draws, redraws or removes the mark on one pair. Safe to call before the group
 * exists (during scene setup), when it does nothing.
 *
 * @param {GameState} gameState
 * @param {string} pairKey - PuzzleGrid.pairKey
 * @param {number} relation - index into PAIR_RELATIONS; 0 removes the mark
 */
export function updatePairMark(gameState, pairKey, relation) {
    const group = gameState.sceneManager.pairMarkGroup;
    if (!group) return;

    // Out with the old, whichever relation it was: a mark's geometry depends on
    // the relation, so changing one is a rebuild rather than an edit. Geometries
    // are disposed because each is built for this one corner; the material is
    // shared by every arc on the board and must not be.
    const previous = group.userData.drawn.get(pairKey);
    if (previous) {
        group.remove(previous);
        previous.traverse(item => {
            if (item.geometry) item.geometry.dispose();
        });
        group.userData.drawn.delete(pairKey);
    }
    if (!relation) return;

    const [edgeA, edgeB] = PuzzleGrid.pairEdges(pairKey);
    const frame = cornerFrame(gameState.getPuzzleGrid(), edgeA, edgeB);
    if (!frame) {
        console.warn(`Can't draw a pair mark on ${pairKey}: no shared corner.`);
        return;
    }

    // One arc for 'exactly one', two for 'both or neither' -- so the relation
    // index doubles as the number of arcs, which is why PAIR_RELATIONS is in that
    // order and not some other.
    const mark = new THREE.Group();
    for (let arc = 0; arc < relation; arc++) {
        mark.add(arcMesh(frame, group.userData.material, arc));
    }
    freezeTransform(mark);
    group.add(mark);
    group.userData.drawn.set(pairKey, mark);
    debug(`pair mark ${pairKey}: ${relation} arc(s) at radius `
          + `${frame.radius.toFixed(3)}, corner ${THREE.MathUtils.radToDeg(frame.angle).toFixed(1)} deg`);
}

/**
 * Redraws every mark from scratch. For whoever needs to rebuild the view without
 * replaying the history -- nothing does yet, but the alternative is that the only
 * way to get the arcs on screen is one change at a time.
 *
 * @param {GameState} gameState
 */
export function redrawPairMarks(gameState) {
    const group = gameState.sceneManager.pairMarkGroup;
    if (!group) return;
    for (const pairKey of [...group.userData.drawn.keys()]) {
        updatePairMark(gameState, pairKey, 0);
    }
    for (const [pairKey, relation] of gameState.getPuzzleGrid().pairMarks) {
        updatePairMark(gameState, pairKey, relation);
    }
}
