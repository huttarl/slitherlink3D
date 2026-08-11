# Celebrating a solve

What happens when the player closes the right loop, and why it is that and not
confetti.

## The test every idea has to pass

Does it celebrate *what the player actually did*? They found **the single closed
loop**. An effect that could follow any puzzle in any game says nothing about
this one; an effect that puts the loop on stage says everything.

That test is what ranks the options below, ahead of how impressive each looks.

## The options, ranked

**1. Colouring the two regions — built, and the best of them.** The meaning is
exact and it is the only idea here that says something the player might not
already know: a closed curve on a closed surface *cuts it in two*, and those two
pieces are what their loop produced. Cheap, too — the regions are a flood fill
that refuses to cross a loop edge (`partitionFacesByLoop`), and per-face tinting
already existed for the debug highlight.

**2. Making the loop glow — built.** As `emissive` on the edges' existing
`MeshPhongMaterial`, which costs one property. The distinction that matters:
emissive **adds light of the loop's own colour**, where the first attempt mixed
the colour toward a near-white cyan and so *desaturated* it — the loop got paler
rather than brighter and faded into the pale board around it.

**3. Running lights chasing along the loop — built, then REMOVED.** Worth
recording, because it is an attractive idea that this geometry defeats. A
Slitherlink loop on a polyhedron turns 60–120° at nearly every vertex, so its
curvature is enormous relative to its segment length, and a light travelling such
a path never reads as linear motion. Two separate problems compounded it: each
edge was lit as one whole unit, making the "motion" a sequence of discrete
flashes; and pacing it by *circuits* per second rather than *edges* per second
made the speed differ 40-fold between the tetrahedron and `gp12`. The pacing was
fixable and was fixed. The curvature was not.

Sub-segmenting would have addressed the flashes — `CylinderGeometry(r, r, len, 8,
6)` gives seven rings on the *same* mesh, so per-vertex colours could carry a
smooth bright spot along each edge at no extra draw calls, and a shader with a
per-edge arc-length attribute would be smoother still. But that fixes
steppiness, not jaggedness: a smoothly moving bead on a zigzag wire is still a
bead changing direction constantly. Abandoned in favour of a shimmer that varies
in TIME and not along the loop, which has no direction to read.

**4. Split slightly along the seam, glowing from inside.** The meaning is as exact
as the partition colouring, and it would compose with it. Moderate cost —
translate each region's faces along a separation axis, show an emissive interior.
Not built.

**5. Tumble surge.** Cheap, since the tumble already has a speed factor with an
ease-in ramp. Not built as a *surge*, but the plain tumble earned a place in the
sequence once it had a job to do — see beat 3 below.

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

1. **The loop flares** (0 → 1.8s), pulsing **twice**, then subsides — thin again,
   and **black**, not the blue it is played in. Glow and swell ride one envelope (a
   half cycle of sine, so zero slope at both ends and no visible start or stop),
   repeated once per pulse; because the sine is 0 with zero slope where two humps
   meet, they join into continuous pulsing rather than showing a seam. The colour
   drains over the descent of the last pulse only, so the loop keeps its own blue
   while it beats and the darkening reads as part of the final subsidence.

   **Two pulses because the tune has two cycles** (beat 4 below). It flared once at
   first, which started in step with the music and then left the loop still while
   the phrase carried on — reading as though the animation had finished early.
   `swellSeconds` is therefore one cycle of the tune and `swellCycles` its number
   of repeats; the two sets of constants are kept apart on purpose, so that the
   visual still works when audio is blocked, and a test in
   `js/tests/celebration.test.js` holds them equal.

   It ends black on purpose. Two earlier versions got this wrong in opposite
   directions: one left the loop *breathing indefinitely*, which fought the
   partition colours for attention once they arrived, and the blue it rested at
   sat badly against the amber and teal. Black reads as a line drawn over them.

   Any brightness that varies **along** the loop rather than in time reads as
   motion, and motion along a path this jagged reads as twinkling (see option 3
   above) — so this varies in time only, every edge together.

   Meanwhile the non-loop edges fade toward `EDGE_COLORS.ruledOut`, the near-white
   they were heading for anyway — on a solved board they *are* ruled out — so they
   blend into the faces and leave the loop alone on the solid. Fading them DARK was
   tried first and was worse: it made every other edge look like the loop itself.
   The clue digits go gray over the same moment for free, since solving satisfies
   every clue.
2. **The two sides colour in** (0.5 → 2.0s). Pale amber on one region, pale teal
   on the other, the whole surface fading together from its near-white. The
   smaller region takes the warm colour, since warm advances and cool recedes, so
   the minority side pops instead of hiding.

   **Animating this as a spreading front was built twice and dropped twice.**
   Ordering by distance from the loop collapses: on these solids nearly every face
   *touches* the loop, so distance is 0 for the great majority and almost the whole
   surface lands in one step — measured on a cube, one face coloured at the start
   and the other five together at the very end, after the tumble had begun.
   Ordering by distance from a seed face spreads properly, but it implies the seed
   is a meaningful place on the puzzle, and it is only wherever the fill began. A
   spreading fill would mean something if it started from the last edge the player
   filled — but that needs the solve detected the instant it happens, rather than
   when Check is pressed.
3. **The tumble** (2.1s). Not decoration here, which is why it moved: a partition
   of a closed surface cannot be seen from one side, so turning the solid is what
   shows the two colours carrying on round the back. It had no such job in an
   earlier version and merely made the running lights harder to follow.
4. **The dialog** (5s). Last, and **low on the screen** rather than centered,
   because a centered box covered exactly the two things worth looking at. It sits
   as low as there is room for: bottom-anchored, with a `max-height` cap so that
   on a short screen it grows upward and then scrolls inside itself instead of
   overflowing off the top, where a bottom-anchored flex item's overflow can't be
   reached. Only this overlay moves — the confirmation dialog is a question, and
   stays where the eye already is.

Beats 1 and 2 belong to `js/celebration.js`; 3 and 4 are scheduled by
`celebrateSolved` in `js/ui.js`. The tune covers beats 1 and 2 and its held note
resolves over the tumble.

## Constraints worth remembering

- **`prefers-reduced-motion` skips the whole sequence** and shows the dialog at
  once. A shimmering, turning board is exactly what that setting exists for.
- **Any board change cancels it**, restoring the ordinary edge and face colors and
  dropping the pending tumble and dialog. A "Congratulations" arriving three
  seconds after the player has already broken their loop would be nonsense.
- **Never mutate a color from `EDGE_COLORS` in place.** `applyEdgeState` *assigns*
  those shared constants to `material.color`, so after any state change many
  edges' materials point at the same `THREE.Color` object — and the constant
  itself. The celebration gives each edge it animates a private `Color` first;
  `clearEdgeHighlights` puts the sharing back.
- **The partition colors have three constraints**, which rule out most obvious
  pairs including the tempting red-vs-blue. Not red or green: this app already
  spends those on `error` and `solution`, and red faces at the moment of winning
  would read as a mistake. Not blue: that is the loop's own color, and a blue
  region would camouflage it. And both must stay **light**, because the black clue
  digits sit on these faces. Amber against teal is the warm/cool pair that
  survives color blindness, lying along the orange–blue axis that both red-green
  dichromacies leave intact; the slight lightness difference between the two is
  insurance for the rare blue-yellow case, and separates them in greyscale.
- **Stop painting once the partition is final.** The face tints go through the
  solid's single vertex-color attribute, so touching one face marks the whole
  attribute for re-upload. Beat 2 sets a flag when the fade completes, and after
  that the per-frame shimmer leaves the faces alone.
- **Face coloring needs `faceVertexRanges`, which used to arrive empty.**
  `GameState.setupScene` destructured `faceMap` and `faceVertexRanges` out of the
  polyhedron data and then dropped them, while `setupEdges` looked for them on the
  scene manager, which never had them — so `setupCrossReferences` got two empty
  Maps. Every face-coloring path then did nothing, silently, because a missing
  range is skipped rather than raised. That had also disabled `interaction.js`'s
  debug face highlight, which is presumably why nobody noticed. Fixed by holding
  them on the GameState between the two calls.
- The color-based effects all ride the existing render loop and cost almost
  nothing. The expensive-sounding ideas above are the ones that need new geometry,
  and a true bloom halo would need a render-pipeline change (an `EffectComposer`
  and half a dozen more vendored three addons) rather than a material property.
