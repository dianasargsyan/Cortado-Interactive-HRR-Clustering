from typing import Any, List

from cortado_core.models.infix_type import InfixType
from cortado_core.process_tree_utils.reduction import apply_reduction_rules
from cortado_core.utils.sequentializations import generate_sequentializations
from cortado_core.utils.split_graph import Group
from cortado_core.utils.trace import TypedTrace

from backend_utilities.configuration.repository import ConfigurationRepositoryFactory
from backend_utilities.multiprocessing.pool_factory import PoolFactory
from backend_utilities.process_tree_conversion import (
    dict_to_process_tree,
    process_tree_to_dict,
)
from backend_utilities.variant_trace_conversion import variant_to_trace
from cortado_core.utils.alignment_utils import typed_trace_fits_process_tree
from endpoints.add_variants_to_process_model import add_variants_to_process_model
from fastapi import APIRouter
from pm4py.discovery import discover_process_tree_inductive
from pm4py.objects.log.obj import Event, EventLog, Trace
from pm4py.objects.process_tree.obj import ProcessTree
from pydantic import BaseModel

router = APIRouter(tags=["discoverTree"], prefix="/discoverTree")


class InputDiscoverProcessModelFromVariants(BaseModel):
    variants: List[Any]


def discover_process_model_from_variants(traces):
    # TODO decide how to handle initial process discovery
    log = EventLog([t.trace for t in traces if t.infix_type == InfixType.NOT_AN_INFIX])
    pt: ProcessTree = discover_process_tree_inductive(log)
    apply_reduction_rules(pt)
    res = process_tree_to_dict(pt)
    return res


@router.post("/discoverProcessModelFromConcurrencyVariants")
async def discover_process_model_from_cvariants(
    d: InputDiscoverProcessModelFromVariants,
):
    all_traces = get_traces_from_variants(d.variants)
    print(f"nVariants: {len(all_traces)}")
    res = discover_process_model_from_variants(all_traces)
    return res


class InputAddVariantsToProcessModel(BaseModel):
    fitting_variants: List[Any]
    variants_to_add: List[Any]
    pt: dict


@router.post("/addConcurrencyVariantsToProcessModel")
async def add_cvariants_to_process_model(d: InputAddVariantsToProcessModel):
    fitting_variants = get_traces_from_variants(d.fitting_variants)
    to_add = get_traces_from_variants(d.variants_to_add)
    return add_variants_to_process_model(
        d.pt, fitting_variants, to_add, PoolFactory.instance().get_pool()
    )


class InputAddVariantsToProcessModelUnknownConformance(BaseModel):
    selected_variants: List[Any]
    pt: dict


@router.post("/addConcurrencyVariantsToProcessModelUnknownConformance")
async def add_cvariants_to_process_model_unknown_conformance(
    d: InputAddVariantsToProcessModelUnknownConformance,
):
    selected_variants = get_traces_from_variants(d.selected_variants)

    fitting_traces = set()
    traces_to_add = set()
    process_tree, _ = dict_to_process_tree(d.pt)
    for selected_variant in selected_variants:
        if typed_trace_fits_process_tree(selected_variant, process_tree):
            fitting_traces.add(selected_variant)
        else:
            traces_to_add.add(selected_variant)

    return add_variants_to_process_model(
        d.pt,
        list(fitting_traces),
        list(traces_to_add),
        PoolFactory.instance().get_pool(),
    )


def get_traces_from_variants(variants):
    config = (
        ConfigurationRepositoryFactory().get_config_repository().get_configuration()
    )
    n_sequentializations = (
        -1
        if not config.is_n_sequentialization_reduction_enabled
        else config.number_of_sequentializations_per_variant
    )
    traces = []

    for cvariant, infix_type in variants:
        sequentializations = generate_sequentializations(
            Group.deserialize(cvariant), n_sequentializations=n_sequentializations
        )
        traces += [
            TypedTrace(variant_to_trace(seq), InfixType(infix_type))
            for seq in sequentializations
        ]

    return traces
