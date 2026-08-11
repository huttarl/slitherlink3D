/**
 * Whether the player wants animation at all.
 *
 * One question with three askers -- the solve celebration, the board's opening
 * zoom, and the tumble -- so it lives here rather than in whichever of them
 * happened to need it first. Two copies of a media-query string are two chances to
 * fix a bug in one of them.
 *
 * The asking is done where the motion STARTS, not where the caller decides to ask
 * for it: startTumble and startIntroZoom decline for themselves, so a caller added
 * later inherits the behaviour instead of having to remember it. That matters here
 * because it was forgotten once already -- the celebration's fallback path started
 * a tumble precisely when the celebration had declined to animate.
 */

/** Does the player's system ask for less motion? Read per call rather than
 *  cached: the setting can change while the page is open. */
export function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
