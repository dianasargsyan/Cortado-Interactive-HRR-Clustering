from pm4py.objects.log.obj import Trace, Event
import datetime

from pm4py.util.xes_constants import (
    DEFAULT_START_TIMESTAMP_KEY,
    DEFAULT_TIMESTAMP_KEY,
    DEFAULT_NAME_KEY,
)


def variant_to_trace(variant: any) -> Trace:
    t = Trace()
    trace_starttime = datetime.datetime.fromtimestamp(0)
    for i, e in enumerate(variant):
        assert type(e) == str
        event = Event()
        event[DEFAULT_NAME_KEY] = e
        event[DEFAULT_START_TIMESTAMP_KEY] = trace_starttime + datetime.timedelta(
            seconds=i
        )
        event[DEFAULT_TIMESTAMP_KEY] = trace_starttime + datetime.timedelta(seconds=i)
        t.append(event)

    return t
