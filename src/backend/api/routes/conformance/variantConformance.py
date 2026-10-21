import asyncio
from collections import Counter
from cortado_core.utils.sequentializations import generate_sequentializations
from cortado_core.utils.split_graph import Group
from cortado_core.utils.process_tree import LabelWithIndex
from starlette.websockets import WebSocketState

from backend_utilities.configuration.repository import ConfigurationRepositoryFactory
from backend_utilities.timeout.helper_functions import (
    TimeoutException,
    execute_with_timeout,
)
from backend_utilities.process_tree_conversion import dict_to_process_tree
from endpoints.alignments import InfixType
from endpoints.alignments import calculate_alignment as calculate_alignment_endpoint
from fastapi import WebSocket


def calculate_alignment_intern_with_timeout(
    pt: dict, c_variant: dict, infix_type: InfixType, timeout: int
):
    try:
        return execute_with_timeout(
            calculate_alignment_intern, timeout, args=(pt, c_variant, infix_type)
        )
    except TimeoutException:
        return {"isTimeout": True}


def calculate_alignment_intern(pt: dict, c_variant: dict, infix_type: InfixType):
    def index_leafs(variant, indices=None):
        if indices is None:
            indices = Counter()
        if "follows" in variant:
            res = {"follows": []}
            for v in variant["follows"]:
                childs = index_leafs(v, indices)
                res["follows"].append(childs)
            return res
        elif "parallel" in variant:
            res = {"parallel": []}
            for v in variant["parallel"]:
                childs = index_leafs(v, indices)
                res["parallel"].append(childs)
            return res
        else:
            leafs = []
            for activity in variant["leaf"]:
                leafs.append(LabelWithIndex(activity, indices[activity]))
                indices[activity] += 1
            return {"leaf": leafs}

    c_variant_indexed = index_leafs(c_variant)

    config = (
        ConfigurationRepositoryFactory().get_config_repository().get_configuration()
    )
    n_sequentializations = (
        -1
        if not config.is_n_sequentialization_reduction_enabled
        else config.number_of_sequentializations_per_variant
    )
    all_variants = generate_sequentializations(
        Group.deserialize(c_variant_indexed), n_sequentializations=n_sequentializations
    )
    index_alignments_mapping = Counter()
    total_cost = 0
    deviations = 0
    for variant in all_variants:
        alignment = calculate_alignment_endpoint(
            variant, dict_to_process_tree(pt)[0], infix_type
        )
        total_cost += alignment["cost"]
        deviations += alignment["deviation"]
        for log_move, model_move in alignment["alignment"]:
            if log_move == ">>":
                continue
            index_alignments_mapping[log_move.full] += str(log_move) == str(model_move)

    if len(all_variants) > 1:
        index_alignments_mapping = {
            k: v / len(all_variants) for k, v in index_alignments_mapping.items()
        }

    return {
        "cost": total_cost / len(all_variants),
        "deviations": deviations / len(all_variants),
        "alignment": project_alignments_on_cvariant(
            index_alignments_mapping, c_variant_indexed
        ),
        "pt": pt,
    }


def project_alignments_on_cvariant(mapping, variant):
    if "follows" in variant:
        res = {"follows": []}
        for v in variant["follows"]:
            childs = project_alignments_on_cvariant(mapping, v)
            res["follows"].append(childs)
        return res
    elif "parallel" in variant:
        res = {"parallel": []}
        for v in variant["parallel"]:
            childs = project_alignments_on_cvariant(mapping, v)
            res["parallel"].append(childs)
        return res
    else:
        return {"leaf": [(str(act), mapping[act.full]) for act in variant["leaf"]]}


def get_alignment_callback(idx: str, alignType, websocket: WebSocket):
    def callback(result):
        data = {
            "id": idx,
            "isTimeout": False,
            "cost": 0,
            "type": alignType,
            "deviation": False,
        }
        for key, value in result.items():
            data[key] = value

        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                asyncio.run(websocket.send_json(data))
        except:
            print("Error while sending conformance result")

    return callback
