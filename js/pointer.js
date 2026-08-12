/**
 * What the player is pointing with.
 *
 * A finger is a blunt instrument next to a mouse: its contact patch is several
 * millimetres across, it hides what it is touching, and it cannot hover to see
 * what it is about to hit. So the board is drawn with thicker edges and picked
 * with more slack on a touch screen -- see COARSE_POINTER_RADIUS_FACTOR.
 *
 * Asked as a media query rather than by sniffing the user agent, which answers
 * "what device is this" instead of the question that matters, and gets it wrong on
 * everything new. Sibling of motion.js, which asks the other environment question.
 */

/**
 * Is the player's PRIMARY pointing device a coarse one, i.e. a finger?
 *
 * `pointer`, not `any-pointer`: a touchscreen laptop being driven by its mouse
 * reports a fine primary pointer, and thickening its board for a touchscreen it
 * isn't using would be wrong. The cost of asking about the primary device is that
 * the same laptop used by hand keeps the thin board -- which is the better way round
 * to be wrong, since the drawn radius is baked into the geometry at load and cannot
 * follow which hand the player reaches with. Per-gesture decisions do not have that
 * limitation, and interaction.js makes them from event.pointerType instead.
 *
 * Read per call rather than cached: a tablet docked to a keyboard can change its
 * answer, and there is nothing to save.
 */
export function hasCoarsePointer() {
    return window.matchMedia('(pointer: coarse)').matches;
}
