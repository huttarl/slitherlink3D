- Performance baseline, so it doesn't have to be re-derived from scratch next time the
  app feels slow. From Chrome traces read with util/trace_report.py, on a big grid (etI):
  - Desktop holds 59.5-59.8 fps, p99 frame interval about 17.8 ms, GC around 0.1% of the
    time. No jank to find. The jankiness that prompted the investigation was never
    reproduced, and was most likely other load on the machine.
  - The phone runs at 90 fps with about 8 ms of work in an 11.1 ms budget. Thin headroom,
    but not fill-rate bound -- which is what ruled out device pixel ratio as the culprit.
  - Two traps in the method, both written up in util/trace_report.py: DroppedFrame is the
    authoritative jank signal and frame-interval percentiles cannot see it, and Chrome's
    profiler start-up costs 60-140 ms INSIDE the recording, dropping frames of its own.
  - [ ] Re-measure rather than trusting the numbers above if the hardware or the scene
    changes; they're a starting point, not a spec.
