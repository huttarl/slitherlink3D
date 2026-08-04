/**
 * Playwright config for the phone-shaped tests. Opt-in: see the README in this
 * directory for the one-time install, and run with `npm run test:mobile`.
 *
 * These tests need a real browser because they assert LAYOUT -- where things
 * land on screen. jsdom cannot do that at all (no layout engine, so every
 * getBoundingClientRect is zeros), which is why the default suite can't cover
 * this and why every phone bug so far got through it.
 */
import { defineConfig, devices } from '@playwright/test';

// Its own port, so a hand-started server on 8000 is left alone.
const PORT = 8123;

export default defineConfig({
    testDir: '.',
    // The assertions are cheap, but getting to them isn't: each test loads a
    // page that builds a polyhedron and starts WebGL, under device emulation,
    // with several workers competing for the CPU. The truncated icosahedron took
    // 13.8s on one run and blew a 15s budget on the next -- flakiness, not a
    // hang -- so there's room here now.
    timeout: 45_000,
    expect: {timeout: 5_000},
    fullyParallel: true,
    // Two workers, not the default (half the cores). Every test builds a
    // polyhedron and a WebGL context under device emulation, and past about two
    // at once they starve each other enough to make the timing-sensitive tests
    // -- the taps, the long press, anything that computes a screen position and
    // then aims at it -- fail intermittently. Measured over five runs at five
    // workers: three of them had a failure, a different test each time, none of
    // which reproduced when run alone. Two workers costs about 1m instead of
    // 45s, which is cheaper than re-running the suite to find out whether a
    // failure was real.
    workers: 2,
    reporter: process.env.CI ? 'line' : 'list',
    use: {
        baseURL: `http://localhost:${PORT}`,
        // A trace of the failing run is worth far more than a stack trace when
        // the complaint is "this element is 110px too low".
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
    },
    projects: [
        // The shape that matters: a phone, with touch input rather than a mouse.
        {name: 'phone', use: {...devices['Pixel 7']}},
        // A desktop run too, so a fix for one doesn't quietly break the other.
        {name: 'desktop', use: {...devices['Desktop Chrome']}},
    ],
    webServer: {
        // util/serve.py, not http.server: it sends Cache-Control: no-cache, so
        // a run always tests the working tree rather than something cached.
        command: `python3 util/serve.py ${PORT}`,
        url: `http://localhost:${PORT}/main.html`,
        cwd: '../../..',
        reuseExistingServer: !process.env.CI,
        stdout: 'ignore',
        // Also ignore stderr: http.server logs every single request there, and
        // a module graph is ~25 requests per page load, so piping it buries the
        // test results under hundreds of [WebServer] lines. A server that fails
        // to start still fails the run, via the url check above.
        stderr: 'ignore',
    },
});
