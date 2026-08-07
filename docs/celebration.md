# Celebrating a solve

What happens when the player closes the right loop, and why it is that and not
confetti.

## The test every idea has to pass

Does it celebrate *what the player actually did*? They found **the single closed
loop**. An effect that could follow any puzzle in any game says nothing about
this one; an effect that puts the loop on stage says everything.

That test is what ranks the options below, ahead of how impressive each looks.

## The options, ranked

**1. Running lights along the loop.** The strongest, and what the current
implementation is built around. It draws the eye along precisely the thing the
player made, and it is a *visual proof of the win condition*: a pulse that
travels and returns to where it began demonstrates "one loop, closed" better than
any wording could. Nearly free, too — every edge already owns its own material,
and the stored solution is an ordered vertex list, so each edge's position along
the loop is already known. No particles, no new geometry. It also survives
repetition, since it can settle into a slow shimmer rather than a one-shot bang.

**2. Split slightly along the seam, glowing from inside.** The meaning is exact:
the loop *is* the boundary between the two face regions, so parting it says "your
loop cut the ball in two." Moderate cost — translate each region's faces along a
separation axis, show an emissive interior. Not built.

**3. Tumble surge.** Cheap, since the tumble already has a speed factor with an
ease-in ramp, and it reads as "ta-da". But it is generic, and a fast spin makes
the loop *harder* to study, so it works against option 1. Not built; if it ever
is, keep it mild.

**4. Sound.** A real payoff but a different kind of work: assets, a mute setting
that persists, and taste. Short and tonal if so — a rising two-note figure, not
trumpets. It can never be the primary celebration, since plenty of players have
the tab muted.

**Rejected.** *Rays emanating* say nothing about the loop and fight the skybox.
*Birds swirling* need models and flocking, and read as whimsy bolted onto a
mathematical toy — the charm here is that the beauty IS the geometry.

**Deferred as a project, not a flourish: unfolding into two nets.** The most
beautiful idea of the lot and the most specific to the domain, but it needs a
spanning tree of each region's dual graph, per-face hinge transforms, and a story
for self-overlap; on `dbD`'s 120 triangles the two regions are wildly irregular.
It would make more sense as its own "unfold this solid" toy than as a two-second
reward.

**Confetti** is fine as a supplement rather than the main event. If it is ever
added, tint the particles with the two region colors, so even the generic thing
points at this puzzle.

## The sequence, as built

Driven by `js/celebration.js`, advanced once per frame from the render loop in
`js/main.js`, with timings and colors in `js/constants.js` (`CELEBRATION_TIMING`,
`CELEBRATION_COLORS`).

1. **Clear the clutter** (0 → 0.3s). Ruled-out and unknown edges fade toward a
   dark quiet color, so the loop is briefly the only thing drawn on the solid.
   The answer *emerges*. The clue digits go gray over the same moment for free:
   solving satisfies every clue, and satisfied clues were already gray (see
   `docs`-worthy note in `clueRenderer.js`).
2. **One pulse round the loop** (0.3 → 1.5s). A bright head travels the loop
   exactly once and returns to its start, trailing a falloff behind it, while the
   loop's edges thicken slightly — like a cord pulled taut.
3. **Settle** (1.5s on). The pulse becomes a slow travelling shimmer at low
   amplitude and the thickening eases back off. This continues while the player
   looks around, and marks the board as solved without demanding attention.

**The dialog waits 2 seconds.** This is the part that made the whole thing
possible: the celebration box is centered over the solid, so anything played
underneath it is half-hidden. Delaying it lets the loop have the stage, and by the
time the box appears the sequence has reached its quiet state.

## Constraints worth remembering

- **`prefers-reduced-motion` skips the whole sequence** and shows the dialog at
  once. A surging, shimmering board is exactly what that setting exists for.
- **Any board change cancels it**, restoring the ordinary edge colors and
  dropping the pending dialog. A "Congratulations" arriving two seconds after the
  player has already broken their loop would be nonsense.
- **Never mutate a color from `EDGE_COLORS` in place.** `applyEdgeState` *assigns*
  those shared constants to `material.color`, so after any state change many
  edges' materials point at the same `THREE.Color` object — and the constant
  itself. The celebration gives each edge it animates a private `Color` first;
  `clearEdgeHighlights` puts the sharing back.
- The color-based options all ride the existing render loop and cost almost
  nothing. The expensive-sounding ideas above are the ones that need new geometry.
