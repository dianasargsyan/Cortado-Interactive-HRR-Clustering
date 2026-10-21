import itertools
from typing import List

import cache.cache as cache
from backend_utilities.process_tree_conversion import dict_to_process_tree
from backend_utilities.variant_trace_conversion import variant_to_trace
from fastapi import APIRouter, Response
from pm4py.objects.bpmn.exporter.variants.etree import (
    get_xml_string as generate_bpmn_xml,
)
from pm4py.objects.conversion.process_tree.converter import (
    Variants as ptConverterVariant,
)
from pm4py.objects.conversion.process_tree.converter import apply as convert_pt
from pm4py.objects.log.exporter.xes.variants.etree_xes_exp import (
    export_log_as_string as generate_xes_xml,
)
from pm4py.objects.log.obj import EventLog
from pm4py.objects.petri_net.exporter.variants.pnml import (
    export_petri_as_string as generate_pnml_xml,
)
from pm4py.objects.process_tree.exporter.variants.ptml import (
    export_tree_as_string as generate_ptml_xml,
)
from pm4py.objects.process_tree.obj import ProcessTree
from pm4py.objects.log.util.interval_lifecycle import to_lifecycle
from cortado_core.utils.sequentializations import generate_sequentializations
from cortado_core.utils.split_graph import Group
from pydantic import BaseModel

router = APIRouter(tags=["exporting"], prefix="/exporting")


class ConvertPtToX(BaseModel):
    pt: dict


@router.post("/convertPtToBPMN")
async def download_ptml(d: ConvertPtToX):
    pt: ProcessTree
    pt, _ = dict_to_process_tree(d.pt)
    bpmn = convert_pt(pt, variant=ptConverterVariant.TO_BPMN)

    return Response(content=generate_bpmn_xml(bpmn), media_type="application/xml")


@router.post("/convertPtToPTML")
async def download_ptml(d: ConvertPtToX):
    pt: ProcessTree
    pt, _ = dict_to_process_tree(d.pt)

    return Response(content=generate_ptml_xml(pt), media_type="application/xml")


@router.post("/convertPtToPNML")
async def download_pnml(d: ConvertPtToX):
    pt: ProcessTree
    pt, _ = dict_to_process_tree(d.pt)
    net, im, fm = convert_pt(pt)
    return Response(
        content=generate_pnml_xml(net, im, fm), media_type="application/xml"
    )


class ExportLogXes(BaseModel):
    bids: list
    sequentializeVariants: bool
    exportAsIntervalLog: bool
    includeOriginalLogInfo: bool


@router.post("/exportLogVariants")
async def download_xes(d: ExportLogXes):
    variants_to_traces = {
        variant: traces
        for bid, (variant, traces, _, _) in cache.variants.items()
        if bid in d.bids
    }

    exported_traces = []
    for cvariant, traces in variants_to_traces.items():
        if d.sequentializeVariants or len(traces) == 0:
            sequentializations = generate_sequentializations(cvariant)
            traces = [variant_to_trace(seq) for seq in sequentializations]
        exported_traces += traces

    log = EventLog(
        exported_traces,
        **cache.parameters["log_info"] if d.includeOriginalLogInfo else {}
    )

    if not d.exportAsIntervalLog:
        log = to_lifecycle(log)

    # TODO Perserve the Loaded Log Attributes via Variables
    return Response(content=generate_xes_xml(log), media_type="application/xml")
