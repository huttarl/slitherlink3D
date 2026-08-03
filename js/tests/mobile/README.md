# Phone-shaped tests (opt-in)

These run the real app in a real browser at phone size, and assert **where
things land on screen** and **how touch input sequences**. Both are invisible to
the default `npm test` suite: jsdom has no layout engine, so every
`getBoundingClientRect()` there is zeros, and there is no touch model at all.

Every test in `mobile-ui.spec.js` stands for a bug this project shipped:

| Test | The bug it would have caught |
| --- | --- |
| check result on screen, container inflated | `#checkToast` was `position: absolute` inside a `100vh` container, so on a phone it sat ~110px below the fold: tapping Check looked like it did nothing |
| tap cycles forward / long press cycles backward | long press (the touch stand-in for shift+click) once did nothing at all, because `LONG_PRESS_MS` was never imported |
| holding while dragging marks nothing | a press that wanders is a camera rotation, not a mark |
| strip controls on screen, no overlap | the debug panel used to sit on top of the info panel at phone width |
| smoke: frames advance | a throw in the render loop leaves a black screen and an otherwise silent page |

## One-time install

Not installed by default: it adds a dev dependency and a browser download, and
the default suite is meant to stay instant and dependency-free.

```
npm install --save-dev @playwright/test
npx playwright install chromium
```

## Running

```
npm run test:mobile
```

Two projects run: `phone` (Pixel 7 metrics, touch input) and `desktop`, so a fix
for one shape can't quietly break the other. The config starts `util/serve.py`
on port 8123 by itself -- `serve.py` rather than `http.server` because it sends
`Cache-Control: no-cache`, so a run always tests the working tree instead of
something the browser cached. A hand-started server on 8000 is left alone.

Useful while writing tests:

```
npx playwright test --config=js/tests/mobile/playwright.config.js --headed --project=phone
npx playwright test --config=js/tests/mobile/playwright.config.js --ui
```

Failures keep a trace and a screenshot, which is worth much more than a stack
trace when the complaint is "this element is 110px too low".

## How these tests reach into the app

The app exposes no globals, but `GameState` is a singleton, so importing its
module inside the page returns the instance the app is already using -- scene,
camera and grid included. `helpers.js` uses that, so no test hooks are needed in
production code.

Two conventions worth keeping:

- **Assert geometry, not state.** An element can be present, styled and carrying
  the right text while sitting off screen. Checking `textContent` proved exactly
  nothing about the toast bug; `visibleWithinViewport` is the check that does.
- **Force the layout condition.** Device emulation gives viewport size and touch,
  but not browser toolbars, so it cannot reproduce the `100vh` overhang on its
  own. `inflateCanvasContainer` creates it deliberately.

## What this still cannot tell you

- Real browser chrome. Brave's bottom address bar overlaying a fixed element is
  not emulated; only a device shows that.
- Whether a target is big enough for a thumb. The pick tolerance is ~25px wide
  against a ~44px guideline; a test can measure it but not judge it.
- Real WebGL/GPU behaviour on phone hardware.

Device testing stays necessary for feel. These tests are for the regressions.
