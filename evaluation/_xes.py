"""
A streaming XES reader that keeps only what concurrency variants need.

pm4py.read_xes loads every attribute of every event into a dataframe; for BPI Challenge 2018
(1.9 GB of XES) that does not fit in 8 GB of memory.  Cortado's variants use three event
attributes, the activity (concept:name), the timestamp (time:timestamp) and, when present, the
lifecycle transition (lifecycle:transition), so this reader streams the file and keeps those
three only.

While streaming it also collects facts about the raw log that the variants no longer show: which
lifecycle transitions occur, how often two events of one case carry the same timestamp (the
source of concurrency in a log that records only completions), and how many timestamps sit
exactly at midnight (a sign of day-level granularity).  evaluation/experiments/03_cache_variants.py --light uses
this reader; it was checked against caches built with pm4py.read_xes.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from lxml import etree
from pm4py.objects.log.obj import Event, EventLog, Trace

ACT, TS, LC = "concept:name", "time:timestamp", "lifecycle:transition"
_MIDNIGHT = re.compile(r"T00:00:00(\.0+)?(Z|[+-]\d\d:?\d\d)?$")


def _local(tag: str) -> str:
    """Tag name without the XES namespace, if the file declares one."""
    return tag.rsplit("}", 1)[-1]


def read_xes_light(path: Path) -> tuple[EventLog, dict]:
    """Stream *path*; return a minimal EventLog and the raw-log facts.

    The EventLog carries, per event, only activity, timestamp and (if the log
    has it) lifecycle transition, which is everything
    `cortado_core.utils.cvariants.get_concurrency_variants` reads.
    """
    traces_raw: list[tuple[str, list[tuple[str, str, str | None]]]] = []
    trace_attr_keys: Counter = Counter()
    lifecycle: Counter = Counter()
    n_events = same_ts = midnight = 0

    events: list[tuple[str, str, str | None]] = []
    case_id = ""
    intern = sys.intern

    for _, el in etree.iterparse(str(path), events=("end",), huge_tree=True):
        tag = _local(el.tag)
        if tag == "event":
            act = ts = lc = None
            for child in el:
                key = child.get("key")
                if key == ACT:
                    act = intern(child.get("value"))
                elif key == TS:
                    ts = child.get("value")
                elif key == LC:
                    lc = intern(child.get("value").lower())
            if act is not None and ts is not None:
                events.append((act, ts, lc))
            el.clear()
        elif tag == "trace":
            for child in el:
                if _local(child.tag) != "event":
                    key = child.get("key")
                    if key is not None:
                        trace_attr_keys[key] += 1
                        if key == ACT:
                            case_id = child.get("value")
            # raw-log facts, per case
            ts_count = Counter(ts for _, ts, _ in events)
            same_ts += sum(c for c in ts_count.values() if c > 1)
            for _, ts, lc in events:
                if _MIDNIGHT.search(ts):
                    midnight += 1
                lifecycle[lc] += 1
            n_events += len(events)
            traces_raw.append((case_id, events))
            events, case_id = [], ""
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]

    # Parse every timestamp in one vectorised call, as pandas does for pm4py.
    flat = [ts for _, evs in traces_raw for _, ts, _ in evs]
    parsed_s = pd.to_datetime(pd.Series(flat), format="ISO8601", utc=True)
    parsed = parsed_s.dt.to_pydatetime()

    has_lc = any(lc is not None for lc in lifecycle)
    traces = []
    i = 0
    for cid, evs in traces_raw:
        tr = []
        for act, _, lc in evs:
            e = {ACT: act, TS: parsed[i]}
            if has_lc:
                e[LC] = lc if lc is not None else "complete"
            tr.append(Event(e))
            i += 1
        traces.append(Trace(tr, attributes={ACT: cid}))
    log = EventLog(traces)

    lengths = [len(evs) for _, evs in traces_raw]
    facts = {
        "n_cases": len(traces_raw),
        "n_events": n_events,
        "n_activities": len({a for _, evs in traces_raw for a, _, _ in evs}),
        "events_per_case_mean": n_events / max(len(traces_raw), 1),
        "events_per_case_median": float(pd.Series(lengths).median()) if lengths else 0.0,
        "events_per_case_max": max(lengths, default=0),
        "lifecycle_values": ";".join(f"{k}:{v}" for k, v in lifecycle.most_common()),
        "has_start_events": lifecycle.get("start", 0) > 0,
        "same_timestamp_event_share": same_ts / max(n_events, 1),
        "midnight_timestamp_share": midnight / max(n_events, 1),
        "first_timestamp": str(parsed_s.min().date()) if len(flat) else "",
        "last_timestamp": str(parsed_s.max().date()) if len(flat) else "",
        "n_case_attributes": sum(1 for k in trace_attr_keys if k != ACT),
        "case_attributes": ";".join(sorted(k for k in trace_attr_keys if k != ACT)),
    }
    return log, facts
