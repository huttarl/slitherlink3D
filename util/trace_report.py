#!/usr/bin/env python3
"""Summarize a Chrome DevTools Performance trace: frame pacing, JS self time,
garbage collection, heap churn.

Usage:
    util/trace_report.py Trace-20260813T160353.json [--top=25]

Save the trace from DevTools' Performance panel with right-click -> "Save
profile...". Uncheck Screenshots and check Memory before recording: the
screenshots multiply the file size, and the memory counters are what make the
heap section below possible.

Why a script and not a read of the panel: the panel answers "what is slow" for
one frame at a time, and the question here is which frames were slow at all --
which needs every frame's interval, a percentile, and a comparison against the
display's refresh rate. A trace is also 25MB+ of JSON, too big to read directly.

What each section is for:

  FRAME PACING   the headline. A drag that feels smooth sits at the refresh
                 interval with a tight p99; jank is a p99 (or a max) well above
                 it. Measured between consecutive AnimationFrame::Render events,
                 so it is the interval the player actually saw, not the time the
                 render loop spent working.

                 DROPPED is the number that settles it, and it is Chrome's own
                 verdict rather than this script's arithmetic: a DroppedFrame
                 event per frame the compositor failed to present. Worth having
                 both, because the interval percentiles above MISS these -- a
                 frame that never presented leaves no gap to measure, so a
                 recording can show a flawless p99 and still have dropped
                 frames. Trust DROPPED over the percentiles when they disagree.
  SELF TIME      where the main thread's JS went, from the sampling profiler.
                 Folded by function, since the same function sampled under
                 several call paths would otherwise be split across rows. Note
                 (idle) is a row like any other: a high one means the frame
                 budget was never in danger.
  GC             pause time, split by kind. A minor GC (scavenge) is sub-
                 millisecond and invisible; a major one can drop a frame. Judge
                 by TOTAL pause against the recording's length, not by count.
  JS HEAP        how much garbage per second the running code makes. A sawtooth
                 is normal and healthy -- what matters is whether collecting it
                 costs anything, which is the GC section's business.

One caveat the numbers cannot show: the profiler's own start-up costs tens of
milliseconds and lands inside the recording, so the first long frame of every
trace is usually an artifact. This script flags it (see BEFORE/AFTER below)
rather than leaving it to be misread as a real stall.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Frames longer than this are worth listing individually. Two refresh intervals
# at 60Hz: one missed vsync is a visible hitch, and anything under it isn't.
LONG_FRAME_MS = 33.0

# Everything before this is the profiler starting up, not the page. Chrome's
# CpuProfiler::StartProfiling runs for 60-140ms INSIDE the recording and drops
# every frame it overlaps, which on two real traces accounted for 7 of 8 and 2 of
# 3 dropped frames. Reported separately rather than filtered out, so the number
# is still visible but can't be mistaken for a finding.
STARTUP_SECONDS = 0.5

# Trace timestamps are microseconds throughout, hence the /1000 and /1e6 below.


def load(path):
    """The trace's event list. Chrome writes either a bare list or an object
    with the list under 'traceEvents', depending on how it was exported."""
    data = json.loads(Path(path).read_text())
    return data['traceEvents'] if isinstance(data, dict) else data


def profile_tree(events):
    """The sampling profiler's nodes and samples, gathered from the ProfileChunk
    events the trace arrives in.

    @returns (labels by node id, parent id by node id, samples, time deltas)
    """
    labels = {}
    parent = {}
    samples = []
    deltas = []
    for event in events:
        if event.get('name') != 'ProfileChunk':
            continue
        data = event['args']['data']
        for node in data['cpuProfile'].get('nodes', []):
            frame = node['callFrame']
            name = frame.get('functionName') or '(anonymous)'
            file = frame.get('url', '').rsplit('/', 1)[-1]
            # lineNumber is 0-based in the trace; +1 to match an editor.
            labels[node['id']] = (f'{name}  [{file}:{frame.get("lineNumber", -1) + 1}]'
                                  if file else name)
            for child in node.get('children', []):
                parent[child] = node['id']
        samples.extend(data['cpuProfile'].get('samples', []))
        deltas.extend(data.get('timeDeltas', []))
    return (labels, parent, samples, deltas)


def report_frames(events, first_timestamp):
    """Frame pacing, which is the question "was there jank" stated numerically."""
    stamps = sorted(event['ts'] for event in events
                    if event.get('name') == 'AnimationFrame::Render'
                    and event.get('ph') != 'e')
    if len(stamps) < 3:
        print('\n=== FRAME PACING ===\n  no frames in this trace')
        return
    gaps = [((b - a) / 1000, (a - first_timestamp) / 1e6)
            for (a, b) in zip(stamps, stamps[1:])]
    intervals = sorted(gap for (gap, _when) in gaps)
    count = len(intervals)
    span = (stamps[-1] - stamps[0]) / 1e6
    print(f'\n=== FRAME PACING: {len(stamps)} frames over {span:.2f} s ===')
    print(f'  mean {sum(intervals) / count:6.2f} ms   '
          f'-> {count / span:.1f} fps')
    for percentile in (50, 90, 99):
        print(f'  p{percentile:<3} {intervals[int(count * percentile / 100)]:6.2f} ms')
    print(f'  max  {intervals[-1]:6.2f} ms')
    print(f'  frames over {LONG_FRAME_MS:.0f} ms: '
          f'{sum(1 for gap in intervals if gap > LONG_FRAME_MS)}')
    long_frames = sorted((g for g in gaps if g[0] > LONG_FRAME_MS), reverse=True)
    for (gap, when) in long_frames[:10]:
        # The profiler's own start-up lands in the first moments of every trace,
        # so say which side of it a stall is on rather than letting the artifact
        # be read as a finding.
        artifact = ('   <- profiler start-up, not your code'
                    if when < STARTUP_SECONDS else '')
        print(f'    {gap:7.2f} ms at t={when:6.3f}s{artifact}')


def report_dropped(events, first_timestamp):
    """Chrome's own count of frames it failed to present -- the number that
    settles whether a recording contains jank. See the note in the module
    docstring: the interval percentiles cannot see these."""
    drops = sorted((event['ts'] - first_timestamp) / 1e6
                   for event in events if event.get('name') == 'DroppedFrame')
    begins = sum(1 for event in events if event.get('name') == 'BeginFrame')
    startup = [t for t in drops if t < STARTUP_SECONDS]
    real = [t for t in drops if t >= STARTUP_SECONDS]
    print(f'  DROPPED {len(drops)} of {begins} frames'
          + (f'  ({len(startup)} of them in the first '
             f'{STARTUP_SECONDS:.1f}s = profiler start-up)' if startup else ''))
    if real:
        print('    after start-up, dropped at t = '
              + ', '.join(f'{t:.3f}s' for t in real[:12])
              + (' ...' if len(real) > 12 else ''))
    elif drops:
        print('    none after start-up: this recording has no real jank in it')


def report_self_time(labels, parent, samples, deltas, top):
    """Where the main thread's JS time went."""
    del parent  # The tree is kept for a future inclusive-time view.
    by_function = Counter()
    for (node, delta) in zip(samples, deltas):
        by_function[labels.get(node, '?')] += delta
    total = sum(by_function.values()) or 1
    print(f'\n=== JS SELF TIME (top {top} of {total / 1000:.0f} ms sampled) ===')
    for (name, microseconds) in by_function.most_common(top):
        print(f'  {microseconds / 1000:8.1f} ms  {100 * microseconds / total:5.1f}%  {name}')


def report_gc(events, span):
    """GC pause time. Only the phases that actually stop the main thread are
    worth a line, so this keeps the summary events (MinorGC/MajorGC) and the
    V8.GC_* breakdown out of each other's way by reporting the former."""
    pauses = defaultdict(list)
    for event in events:
        if event.get('ph') == 'X' and event.get('name') in (
                'MinorGC', 'MajorGC', 'V8.GCScavenger', 'V8.GCFinalizeMC'):
            pauses[event['name']].append(event.get('dur', 0))
    print('\n=== GC PAUSES ===')
    if not pauses:
        print('  none')
        return
    for (name, durations) in sorted(pauses.items(), key=lambda kv: -sum(kv[1])):
        total = sum(durations) / 1000
        print(f'  {total:7.1f} ms  x{len(durations):<4} '
              f'max {max(durations) / 1000:6.2f} ms  {name}'
              + (f'   ({100 * total / (span * 1000):.2f}% of the recording)'
                 if span else ''))


def report_heap(events):
    """Allocation rate, from the memory counters. Needs the Memory checkbox."""
    heap = sorted((event['ts'], event['args']['data']['jsHeapSizeUsed'])
                  for event in events if event.get('name') == 'UpdateCounters'
                  and 'jsHeapSizeUsed' in event.get('args', {}).get('data', {}))
    if len(heap) < 3:
        print('\n=== JS HEAP ===\n  no memory counters '
              '(check "Memory" in the Performance panel before recording)')
        return
    span = (heap[-1][0] - heap[0][0]) / 1e6
    climb = sum(max(0, b - a) for ((_, a), (_, b)) in zip(heap, heap[1:]))
    print(f'\n=== JS HEAP over {span:.2f} s ===')
    print(f'  {min(h[1] for h in heap) / 1e6:.1f} MB low, '
          f'{max(h[1] for h in heap) / 1e6:.1f} MB high')
    print(f'  allocated {climb / 1e6:.1f} MB -> {climb / 1e6 / span:.1f} MB/s')


def main():
    arguments = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not arguments:
        print(__doc__.strip().split('\n\n')[1], file=sys.stderr)
        sys.exit(1)
    top = next((int(a.split('=')[1]) for a in sys.argv[1:]
                if a.startswith('--top=')), 25)

    events = load(arguments[0])
    first_timestamp = min((e['ts'] for e in events if e.get('ts', 0) > 0),
                          default=0)
    stamps = [e['ts'] for e in events if e.get('ts', 0) > 0]
    span = (max(stamps) - min(stamps)) / 1e6 if stamps else 0
    print(f'{Path(arguments[0]).name}: {len(events)} events over {span:.2f} s')

    report_frames(events, first_timestamp)
    report_dropped(events, first_timestamp)
    (labels, parent, samples, deltas) = profile_tree(events)
    if samples:
        report_self_time(labels, parent, samples, deltas, top)
    else:
        print('\n=== JS SELF TIME ===\n  no profiler samples in this trace')
    report_gc(events, span)
    report_heap(events)


if __name__ == '__main__':
    main()
