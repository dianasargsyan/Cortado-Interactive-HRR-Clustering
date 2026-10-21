from typing import Any

from cortado_core.eventually_follows_pattern_mining.local_process_models.clustering.edit_dist_aggl_with_preclustering import (
    EditDistanceAgglomerativeClustererWithPreclustering,
)
from cortado_core.eventually_follows_pattern_mining.local_process_models.discovery.inductive_miner import (
    InductiveMiner,
)
from cortado_core.eventually_follows_pattern_mining.local_process_models.lpm_discoverer import (
    LpmDiscoverer,
)
from cortado_core.eventually_follows_pattern_mining.local_process_models.metrics import (
    calculate_metrics,
)
from cortado_core.eventually_follows_pattern_mining.obj import group_to_ef_pattern
from cortado_core.utils.split_graph import Group
from fastapi import APIRouter
from pm4py.objects.log.obj import EventLog
from pydantic import BaseModel

import cache.cache
from api.routes.variants.subvariantMining import serialize_pattern
from backend_utilities.process_tree_conversion import (
    process_tree_to_dict,
    dict_to_process_tree,
)

router = APIRouter(tags=["lpmMiner"], prefix="/lpmMining")


class LpmMiningInput(BaseModel):
    patterns: list


class LpmStatisticsInput(BaseModel):
    lpm: Any = None


@router.post("/lpmMining")
def mineLocalProcessModels(config: LpmMiningInput):
    patterns = __deserialize_patterns(config.patterns)
    lpm_discoverer = LpmDiscoverer(
        EditDistanceAgglomerativeClustererWithPreclustering(
            max_distance=2,
            preclustering_type="label_vector",
            precalculated_distance_matrix=None,
        ),
        discoverer=InductiveMiner(),
    )
    local_process_models = lpm_discoverer.discover_lpms(patterns)

    res = []
    for lpm, patterns in local_process_models:
        res.append(
            {
                "lpm": process_tree_to_dict(lpm),
                "patterns": [serialize_pattern(p) for p in patterns],
            }
        )

    return res


@router.post("/lpmStatistics")
def mineLocalProcessModels(config: LpmStatisticsInput):
    tree, _ = dict_to_process_tree(config.lpm)
    log = []
    for _, traces, _, _ in cache.cache.variants.values():
        log += traces
    log = EventLog(log)
    (
        support_tax,
        support_trans,
        support_occ,
        confidence,
        precision,
        coverage,
        simplicity,
        n_transitions,
        skip_precision,
        mean_range,
        min_range,
        max_range,
    ) = calculate_metrics(tree, log, is_place_net_algorithm=False)

    res = {
        "support": support_tax,
        "supportTrans": support_trans,
        "supportOcc": support_occ,
        "confidence": confidence,
        "precision": precision,
        "coverage": coverage,
        "simplicity": simplicity,
        "skipPrecision": skip_precision,
        "meanRange": mean_range.item(),
        "minRange": min_range.item(),
        "maxRange": max_range.item(),
    }

    return res


def __deserialize_patterns(patterns):
    return [group_to_ef_pattern(Group.deserialize(p)) for p in patterns]
