import multiprocessing.pool
from typing import List

from cortado_core.models.infix_type import InfixType
from cortado_core.utils.trace import TypedTrace
from pm4py.objects.log.obj import EventLog

from backend_utilities.process_tree_conversion import (
    dict_to_process_tree,
    process_tree_to_dict,
)
from cortado_core.freezing.apply import add_trace_to_pt_language_with_freezing
from cortado_core.lca_approach import add_trace_to_pt_language
from pm4py.objects.process_tree.obj import ProcessTree
from tqdm import tqdm


def add_variants_to_process_model(
    pt_dict: dict,
    fitting_traces: List[TypedTrace],
    traces_to_be_added: List[TypedTrace],
    pool: multiprocessing.pool.Pool,
):
    pt: ProcessTree
    frozen_subtrees: List[ProcessTree]
    pt, frozen_subtrees = dict_to_process_tree(pt_dict)

    frozen_subtrees_are_present = len(frozen_subtrees) > 0

    description = "adding variants to process tree without frozen subtrees"
    if frozen_subtrees_are_present:
        description = "adding variants to process tree including frozen subtrees"

    for t in tqdm(traces_to_be_added, desc=description):
        if not frozen_subtrees_are_present:
            pt = add_trace_to_pt_language(
                pt, fitting_traces, t, try_pulling_lca_down=True, pool=pool
            )
        else:
            pt, frozen_subtrees = add_trace_to_pt_language_with_freezing(
                pt,
                frozen_subtrees,
                fitting_traces,
                t,
                try_pulling_lca_down=True,
                pool=pool,
            )
        fitting_traces.append(t)
    res = process_tree_to_dict(pt, frozen_subtrees)
    return res
