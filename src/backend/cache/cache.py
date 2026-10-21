from typing import List, Mapping, Tuple
from pm4py.objects.log.obj import EventLog, Trace
from cortado_core.utils.split_graph import ConcurrencyGroup

# raw event log
from api.routes.variants.models import VariantInformation

# raw event log
event_log: EventLog = None
# performance statistics
pcache: Mapping = {}

parameters: Mapping = {}

variants: Mapping[int, Tuple[ConcurrencyGroup, Trace, List, VariantInformation]] = {}
