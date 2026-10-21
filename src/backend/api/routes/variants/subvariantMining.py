import asyncio
from collections import defaultdict
from cortado_core.eventually_follows_pattern_mining.algorithm import (
    generate_eventually_follows_patterns_from_groups,
)
from cortado_core.eventually_follows_pattern_mining.blanket_mining.algorithm import (
    postprocess_closed_patterns,
    postprocess_maximal_patterns,
)
from cortado_core.eventually_follows_pattern_mining.obj import (
    EventuallyFollowsPattern,
    SubPattern,
)
from cortado_core.eventually_follows_pattern_mining.util.pattern import flatten_patterns
from cortado_core.variant_pattern_replications.repetition_mining import (
    create_pair,
    pair_unions,
)
from cortado_core.subprocess_discovery.concurrency_trees.cTrees import ConcurrencyTree
from cortado_core.utils.split_graph import (
    LeafGroup,
    LoopGroup,
    ParallelGroup,
    SequenceGroup,
    SkipGroup,
    Group,
)

from fastapi import APIRouter
from pydantic import BaseModel

from cortado_core.subprocess_discovery.subtree_mining.treebank import (
    create_treebank_from_cv_variants,
)
from cortado_core.subprocess_discovery.subtree_mining.right_most_path_extension.min_sub_mining import (
    min_sub_mining,
)
from cortado_core.subprocess_discovery.subtree_mining.obj import (
    FrequencyCountingStrategy,
)
from cortado_core.subprocess_discovery.subtree_mining.maximal_connected_components.maximal_connected_check import (
    set_maximaly_closed_patterns,
)
from cortado_core.subprocess_discovery.subtree_mining.output import (
    dataframe_from_k_patterns,
)
from cortado_core.subprocess_discovery.subtree_mining.blanket_mining.cm_grow import (
    cm_min_sub_mining,
)
from cortado_core.subprocess_discovery.subtree_mining.folding_label import fold_loops
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

import cache.cache as cache
import numpy as np

from cortado_core.variant_pattern_replications.repetition_mining import (
    generate_and_filter_patterns,
    filter_maximal_patterns,
)

from backend_utilities.configuration.repository import ConfigurationRepositoryFactory
from backend_utilities.multiprocessing.pool_factory import PoolFactory
from endpoints.transform_event_log import remove_activitiy_from_group

router = APIRouter(tags=["subvariantMining"], prefix="/subvariantMining")


class VariantMinerConfig(BaseModel):
    size: int
    min_sup: int
    strat: int
    algo: int
    loop: int
    algo_type: int
    artifical_start: bool


class FilterParams(BaseModel):
    activitiesToInclude: list[str] = []


class RepetitionsMiningConfig(BaseModel):
    bids: list[int]
    filters: FilterParams


freq_strat_mapping = {
    1: FrequencyCountingStrategy.TraceTransaction,
    2: FrequencyCountingStrategy.VariantTransaction,
    3: FrequencyCountingStrategy.TraceOccurence,
    4: FrequencyCountingStrategy.VariantOccurence,
}


def postProcessFrequentTrees(k_patterns: defaultdict[any, set]):
    set_maximaly_closed_patterns(k_patterns)

    df = dataframe_from_k_patterns(k_patterns)

    if not df.empty:
        df = df[df.valid]

        df["bids"] = df.obj.apply(lambda x: set(x.rmo.keys()))

        df.obj = df.obj.apply(
            lambda x: replace_loops_by_loop_group(x.to_concurrency_group()).serialize(
                include_performance=False
            )
        )
        df = df.replace({np.nan: None})

        df_dict = df.to_dict(orient="records")

    else:
        df_dict = False
    return df_dict


@router.post("/frequentSubtreeMining")
def mineFrequentSubtrees(config: VariantMinerConfig):
    print(config)

    print("K:", config.size)
    print("min_sup:", config.min_sup)
    print("Strat:", freq_strat_mapping[config.strat])
    print("Mining Algo:", config.algo)
    print("Loop", config.loop)
    print("Artif. Start", config.artifical_start)

    variants = {
        v: ts
        for _, (v, ts, _, info) in cache.variants.items()
        if not info.is_user_defined
    }

    if config.algo == 3:
        return get_eventually_follows_patterns(
            variants, config.min_sup, freq_strat_mapping[config.strat], config.size
        )

    treeBank = create_treebank_from_cv_variants(variants, config.artifical_start)

    if config.loop:
        print("Folding Loops...")
        fold_loops(treeBank, config.loop)

    print()

    if config.algo == 1:
        print("Mining K Patterns...")
        k_patterns, _ = min_sub_mining(
            treeBank,
            frequency_counting_strat=freq_strat_mapping[config.strat],
            k_it=config.size,
            min_sup=config.min_sup,
        )

    else:
        print("Mining CM K Patterns...")
        k_patterns = cm_min_sub_mining(
            treeBank,
            frequency_counting_strat=freq_strat_mapping[config.strat],
            k_it=config.size,
            min_sup=config.min_sup,
        )

    print()
    print("Post-Processing...")
    return postProcessFrequentTrees(k_patterns)


def replace_loops_by_loop_group(group):
    result = group
    if isinstance(group, LeafGroup):
        if group.number_of_activities() == 1 and group[0].endswith("_LOOP"):
            result = LoopGroup([LeafGroup([group[0][:-5]])])

        return result

    if isinstance(group, ParallelGroup):
        return ParallelGroup([replace_loops_by_loop_group(g) for g in group])

    if isinstance(group, SequenceGroup):
        return SequenceGroup([replace_loops_by_loop_group(g) for g in group])

    raise Exception("Group type is unknown")


def get_eventually_follows_patterns(
    variants, min_support, frequency_counting_strategy, max_size
):
    patterns = generate_eventually_follows_patterns_from_groups(
        variants, min_support, frequency_counting_strategy, max_size=max_size
    )
    flat_patterns = set(flatten_patterns(patterns))
    closed = postprocess_closed_patterns(flat_patterns)
    maximal = postprocess_maximal_patterns(flat_patterns)

    result = []
    for pattern in flat_patterns:
        result.append(
            {
                "bids": [],
                "k": sum([len(sp) for sp in pattern.sub_patterns]),
                "obj": serialize_pattern(pattern),
                "sup": pattern.support,
                "child_parent_confidence": None,
                "subpattern_confidence": None,
                "cross_support_confidence": None,
                "valid": True,
                "maximal": pattern in maximal,
                "closed": pattern in closed,
            }
        )

    return result


def serialize_pattern(pattern: EventuallyFollowsPattern):
    return SkipGroup(
        [sub_pattern_to_ctree(sp).to_concurrency_group() for sp in pattern.sub_patterns]
    ).serialize()


def sub_pattern_to_ctree(pattern: SubPattern, parent=None):
    t = ConcurrencyTree(parent=parent, op=pattern.operator, label=pattern.label)
    t.children = [sub_pattern_to_ctree(child, t) for child in pattern.children]
    return t


def serialize_result(data):
    result = {}
    for key, value in data.items():
        if key == "pairs":
            result[key] = {k: [p.serialize() for p in v] for k, v in value.items()}
        else:
            result[key] = value
    return result


def mine_repetition_patterns_with_timeout(
    config: RepetitionsMiningConfig, cached_variants, cached_activities, timeout: int
):
    result = {}

    filter_activities = len(config.filters.activitiesToInclude) > 0 and len(
        config.filters.activitiesToInclude
    ) != len(cached_activities)

    activities_to_exclude = []

    if filter_activities:
        activities_to_exclude = list(
            filter(
                lambda x: x not in config.filters.activitiesToInclude,
                cached_activities,
            )
        )

    maximal_size, maximal_length = 1, 1

    for bid in config.bids:
        if bid in cached_variants:
            v, ts, _, _ = cached_variants[bid]
        else:
            continue

        if filter_activities:
            v = remove_activitiy_from_group(
                v, activities_to_exclude, replace_with_random=True
            )
            v.assign_dfs_ids()

        tree_bank = create_treebank_from_cv_variants({v: ts}, False)

        (
            pairs_filtered,
            kpatterns_filtered,
            ks,
            single_act_pairs,
        ) = generate_and_filter_patterns(tree_bank)

        pairs_from_kpatterns, maximal_size, maximal_length = filter_maximal_patterns(
            kpatterns_filtered, pairs_filtered, ks, tree_bank[0]
        )

        combined_pairs = pair_unions(pairs_from_kpatterns, single_act_pairs)

        result.update(
            {
                bid: sorted(
                    combined_pairs,
                    key=lambda x: x.positions.bfs[1] - x.positions.bfs[0],
                    reverse=True,
                )
            }
        )

    return {
        "pairs": result,
        "maximal_values": {"size": maximal_size, "length": maximal_length},
    }


def get_repetition_mining_callback(websocket: WebSocket):
    def send_response(data):
        result = serialize_result(data)

        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                asyncio.run(websocket.send_json(result))

        except Exception as e:
            print("Error while sending arc diagrams computation result: ", e)

    return send_response
