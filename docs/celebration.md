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

**4. Sound — built.** A rapid run up and down the scale, twice, then a held
tonic: `C D E F G F E D C B A B` twice over, ending on `C`. Synthesized with the
Web Audio API rather than loaded (see `js/celebrationSound.js`), so there is
nothing to fetch and the tune is editable as letters in `js/constants.js`. It
starts with beat 1 and its held note lands as the dialog opens.

It can never be the primary celebration, since plenty of players have the tab
muted — and note **there is no mute setting yet**, which is the obvious next thing
this wants.

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

1. **Clear the clutter** (0 → 0.3s). The non-loop edges fade toward
   `EDGE_COLORS.ruledOut`, the near-white they were heading for anyway — on a
   solved board they *are* ruled out. Being near-white they blend into the faces,
   so the loop is briefly the only dark thing on the solid and the answer
   *emerges*. Fading them DARK was tried first and was worse: it made every other
   edge look like the dark blue of the loop itself. The clue digits go gray over
   the same moment for free, since solving satisfies every clue.
2. **Running lights** (0.3 → 1.5s). Bright heads about three edges apart chase
   round the loop, twice over, each trailing a falloff and bulging the edges it
   passes — a cord pulled taut. Three edges apart rather than two on purpose:
   alternating bright and dark is symmetric and so says nothing about which way
   the lights are moving, while bright/medium/dark does. Going round more than
   once is what shows the loop is closed.
3. **Settle** (1.5s on). The chase eases to a slow shimmer at low amplitude, the
   thickening relaxes, and the other edges come most of the way back so the solid
   reads normally again. This continues while the player looks around.

**The dialog and the tumble both wait 2 seconds.** This is the part that made the
whole thing possible. The celebration box is centered over the solid, so anything
played underneath it is half-hidden; and a turning solid makes the running lights
much harder to follow. So the board stays still and unobstructed until the
sequence has settled, and then both arrive at once.

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
