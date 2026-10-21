from typing import Any
from cortado_core.utils.split_graph import (
    Group,
    SequenceGroup,
    ParallelGroup,
    FallthroughGroup,
    ChoiceGroup,
    LoopGroup,
    LeafGroup,
)
from collections import defaultdict

from cortado_core.subprocess_discovery.concurrency_trees.cTrees import cTreeOperator
from cortado_core.sequentializer.algorithm import apply_sequentializer_on_variants
from cortado_core.sequentializer.pattern import (
    parse_sequentializer_pattern,
    SequentializerPattern,
    WILDCARD_MATCH,
)
from cortado_core.sequentializer.two_plus_two_free_check import get_wildcard_node
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import cache.cache
from api.routes.variants.variants import VariantInformation

# from endpoints.alignments import InfixType
from cortado_core.models.infix_type import InfixType
from endpoints.load_event_log import (
    create_variant_object,
    compute_log_stats,
    variants_to_variant_objects,
)

from cortado_core.subprocess_discovery.concurrency_trees.cTrees import (
    ConcurrencyTree,
    cTreeOperator,
    cTreeFromcGroup,
)

router = APIRouter(tags=["Sequentializer"], prefix="/sequentializer")


class SequentializerPatterns(BaseModel):
    sourcePattern: Any = None
    targetPattern: Any = None


@router.post("/apply")
def apply_sequentializer(payload: SequentializerPatterns):
    source_pattern = parse_pattern_from_variant(
        Group.deserialize(payload.sourcePattern)
    )
    target_pattern = parse_pattern_from_variant(
        Group.deserialize(payload.targetPattern)
    )

    validate_patterns(source_pattern, target_pattern)

    variants = cache.cache.variants

    new_variants = {
        InfixType.NOT_AN_INFIX: defaultdict(list),
        InfixType.PROPER_INFIX: defaultdict(list),
        InfixType.PREFIX: defaultdict(list),
        InfixType.POSTFIX: defaultdict(list),
    }

    n_traces = 0
    for _, (variant, traces, _, info) in variants.items():
        new_variants[info.infix_type][variant] += traces
        n_traces += len(traces)

    print("SOURCE PATTERN:", str(source_pattern))
    print("TARGET PATTERN:", str(target_pattern))

    cache_variants = dict()
    cache_max_bid = 0
    res_variants = []

    for infix_type, var in new_variants.items():  # var: dict, key(variant) value(trace)
        new_variants = apply_sequentializer_on_variants(
            var, source_pattern, target_pattern
        )

        res_vars, new_cache_variants = variants_to_variant_objects(
            new_variants,
            cache.cache.parameters["cur_time_granularity"],
            n_traces,
            lambda ts: generate_variant_info(infix_type, ts),
        )
        res_variants += res_vars

        for bid, variant in new_cache_variants.items():
            cache_variants[bid + cache_max_bid] = variant

        cache_max_bid = max(cache_variants.keys())

    cache.cache.variants = cache_variants

    start_activities, end_activities, nActivities = compute_log_stats(
        cache.cache.variants
    )

    cache.cache.parameters["activites"] = set(nActivities.keys())

    res = {
        "startActivities": start_activities,
        "endActivities": end_activities,
        "activities": nActivities,
        "variants": res_variants,
        "performanceInfoAvailable": cache.cache.parameters["lifecycle_available"],
        "timeGranularity": cache.cache.parameters["cur_time_granularity"],
    }

    return res


def generate_variant_info(infix_type, traces):
    user_defined = len(traces) == 0

    return VariantInformation(infix_type=infix_type, is_user_defined=user_defined)


def validate_string_pattern(pattern: str) -> bool:
    return pattern.count("(") == pattern.count(")")


def validate_patterns(
    source_pattern: SequentializerPattern, target_pattern: SequentializerPattern
):
    activities = cache.cache.parameters["activites"]
    source_activities = get_activities_in_pattern(source_pattern)
    target_activities = get_activities_in_pattern(target_pattern)

    for source_activity in source_activities:
        if source_activity not in activities:
            raise HTTPException(
                status_code=400,
                detail=f"Source pattern contains invalid activity '{source_activity}'",
            )

    for target_activity in target_activities:
        if target_activity not in activities:
            raise HTTPException(
                status_code=400,
                detail=f"Target pattern contains invalid activity '{target_activity}'",
            )

    source_labeled_nodes = [
        set(p.labels) for p in get_activity_nodes_in_pattern(source_pattern)
    ]
    target_labeled_nodes = [
        set(p.labels) for p in get_activity_nodes_in_pattern(target_pattern)
    ]

    for source_labeled_node in source_labeled_nodes:
        try:
            target_labeled_nodes.remove(source_labeled_node)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Node with labels {source_labeled_node} is present in source pattern, but not in target pattern",
            )

    if len(target_labeled_nodes) > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Node with labels {target_labeled_nodes[0]} is present in target pattern, but not in source pattern",
        )

    source_wc_node = get_wildcard_node(source_pattern)
    target_wc_node = get_wildcard_node(target_pattern)

    if source_wc_node is None and target_wc_node is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Target pattern has wildcard (...), which is not present in source pattern",
        )

    if source_wc_node is not None and target_wc_node is None:
        raise HTTPException(
            status_code=400,
            detail=f"Source pattern has wildcard (...), which is not present in target pattern",
        )

    if source_pattern.operator != cTreeOperator.Concurrent:
        raise HTTPException(
            status_code=400,
            detail=f"Source pattern without concurrent operator at highest level",
        )

    for child in source_pattern.children:
        if child.operator is not None and child.operator != WILDCARD_MATCH:
            raise HTTPException(
                status_code=400, detail=f"Source pattern cannot have nested operators"
            )


def get_activities_in_pattern(pattern: SequentializerPattern):
    activities = set(pattern.labels)

    for child in pattern.children:
        activities = activities.union(get_activities_in_pattern(child))

    return activities


def get_activity_nodes_in_pattern(pattern: SequentializerPattern):
    nodes = set()

    if len(pattern.labels) > 0:
        nodes.add(pattern)

    for child in pattern.children:
        nodes = nodes.union(get_activity_nodes_in_pattern(child))

    return nodes


def parse_pattern_from_variant(variant):
    root_node = parse_pattern_from_variant_recursive(variant, None)
    if (
        len(root_node.children) == 1
        and root_node.children[0].operator == cTreeOperator.Concurrent
    ):
        return root_node.children[0]
    else:
        return root_node


def parse_pattern_from_variant_recursive(variant, parent):
    operator = None
    node = None
    if isinstance(variant, SequenceGroup):
        operator = cTreeOperator.Sequential
    elif isinstance(variant, ParallelGroup):
        operator = cTreeOperator.Concurrent

    elif isinstance(variant, FallthroughGroup):
        operator = cTreeOperator.Fallthrough

    elif isinstance(variant, LeafGroup) and sorted([activity for activity in variant])[
        0
    ].startswith("..."):
        operator = WILDCARD_MATCH

    if operator is not None and operator != WILDCARD_MATCH:
        node = SequentializerPattern(operator=operator, parent=parent, children=None)
        if parent is not None:
            parent.children.append(node)
        if operator != cTreeOperator.Fallthrough:
            for child in variant:
                parse_pattern_from_variant_recursive(child, node)
        else:
            fallthrough_leaf = LeafGroup(
                [[activity for activity in leaf][0] for leaf in variant]
            )
            parse_pattern_from_variant_recursive(fallthrough_leaf, node)
    elif operator is not None and operator == WILDCARD_MATCH:
        node = SequentializerPattern(operator=operator, parent=parent, children=None)
        if parent is not None:
            parent.children.append(node)
    else:
        labels = []
        if isinstance(variant, ChoiceGroup):
            labels = [[activity for activity in leaf][0] for leaf in variant]
            match_multiple = True
        else:
            labels = [activity for activity in variant]
            match_multiple = False

        node = SequentializerPattern(
            labels=labels, parent=parent, match_multiple=match_multiple
        )
        if parent is not None:
            parent.children.append(node)

    return node
