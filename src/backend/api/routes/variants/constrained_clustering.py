"""
Constrained clustering post-processing for Cortado variant clustering.

This module does not replace Cortado's original clustering algorithms.
Instead, it takes the clusters produced by the existing clustering pipeline
and applies user-defined constraints afterwards.

Supported constraints:
- must-link: variants in a pair must be placed in the same cluster.
- cannot-link: variants in a pair must not remain in the same cluster.

Post-processing strategy:
1. Must-link constraints merge the clusters that contain linked variants.
2. Cannot-link conflicts are repaired by moving one conflicting variant
   or must-link component to the most similar legal cluster.
3. If both candidate components have the same size, the component that is
   less similar to the remaining source cluster is moved.
4. If no legal target cluster exists, the moved component becomes a new
   singleton cluster.
5. A repair iteration limit prevents non-termination in complex cases.

Similarity strategy:
- Structural Jaccard is used as a lightweight top-k prefilter.
- A neighborhood-tree-based approximate GED similarity is then used for
  reranking the selected candidates.
- Tie-breaking uses average GED similarity to the remaining source cluster.
- Target-cluster selection uses max GED similarity over the candidate cluster.
"""

from collections import Counter
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from cortado_core.utils.split_graph import Group
from cache import cache_util
from api.routes.variants.neighborhood_tree_similarity import (
    calculate_neighborhood_tree_group_list_similarity,
    get_pairwise_similarity_cache_stats,
)

ConstraintPair = Tuple[int, int]
USE_NEIGHBORHOOD_TREE_GED_SIMILARITY = True

# Use Structural Jaccard as a cheap prefilter before GED.
USE_JACCARD_TOP_K_PREFILTER_FOR_GED = True
TOP_K_PREFILTER = 3

# GED aggregation settings for the two repair decisions.
# True = max GED similarity over candidate right groups.
# False = average GED similarity over candidate right groups.
USE_MAX_GED_FOR_TIE_BREAK = False
USE_MAX_GED_FOR_TARGET_SELECTION = True

# Temporary evaluation switches.
# Keep them False for normal use.
DEBUG_SIMILARITY = False
COMPARE_JACCARD_AND_GED = False


class ConstraintError(ValueError):
    pass


class UnionFind:
    def __init__(self, elements: List[int]):
        self.parent: Dict[int, int] = {element: element for element in elements}

    def find(self, element: int) -> int:
        if element not in self.parent:
            raise ConstraintError(f"Unknown variant bid in constraint: {element}")

        if self.parent[element] != element:
            self.parent[element] = self.find(self.parent[element])

        return self.parent[element]

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)

        if root_left != root_right:
            self.parent[root_right] = root_left


def apply_constraints(
    clusters: List[List[Group]],
    must_link: Optional[List[ConstraintPair]] = None,
    cannot_link: Optional[List[ConstraintPair]] = None,
) -> List[List[Group]]:
    """
    Apply must-link and cannot-link constraints after normal clustering.

    Input and output format stay the same:
    List[List[Group]]
    """

    must_link = _normalize_constraints(must_link)
    cannot_link = _normalize_constraints(cannot_link)

    if not must_link and not cannot_link:
        return clusters

    bid_clusters = _convert_group_clusters_to_bid_clusters(clusters)
    all_bids = [bid for cluster in bid_clusters for bid in cluster]

    _validate_constraint_bids(all_bids, must_link + cannot_link)
    _validate_no_direct_conflict(must_link, cannot_link)

    must_link_components = _build_must_link_components(all_bids, must_link)

    _validate_no_must_link_cannot_link_conflict(
        must_link_components=must_link_components,
        cannot_link=cannot_link,
    )

    clusters_after_must_link = _merge_clusters_by_must_link(
        bid_clusters=bid_clusters,
        group_clusters=clusters,
        must_link=must_link,
    )

    clusters_after_cannot_link = _repair_cannot_link_conflicts(
        clusters=clusters_after_must_link,
        must_link_components=must_link_components,
        cannot_link=cannot_link,
    )

    return [cluster for cluster in clusters_after_cannot_link if len(cluster) > 0]


def _normalize_constraints(
    constraints: Optional[List[ConstraintPair]],
) -> List[ConstraintPair]:
    if constraints is None:
        return []

    normalized = []

    for pair in constraints:
        if len(pair) != 2:
            raise ConstraintError(
                f"Invalid constraint {pair}. "
                f"Each constraint must contain exactly two variant bids."
            )

        left, right = pair
        left = int(left)
        right = int(right)

        if left == right:
            continue

        normalized.append((left, right))

    return normalized


def _convert_group_clusters_to_bid_clusters(
    clusters: List[List[Group]],
) -> List[List[int]]:
    bid_clusters = []

    for cluster in clusters:
        bid_cluster = []

        for group in cluster:
            bid, _ = cache_util.map_group_to_cached_variant(group)

            if bid is None:
                raise ConstraintError(
                    "Could not map clustered group back to cached variant."
                )

            bid_cluster.append(bid)

        bid_clusters.append(bid_cluster)

    return bid_clusters


def _validate_constraint_bids(
    all_bids: List[int],
    constraints: List[ConstraintPair],
) -> None:
    known_bids = set(all_bids)

    for left, right in constraints:
        if left not in known_bids:
            raise ConstraintError(f"Unknown variant bid in constraint: {left}")
        if right not in known_bids:
            raise ConstraintError(f"Unknown variant bid in constraint: {right}")


def _validate_no_direct_conflict(
    must_link: List[ConstraintPair],
    cannot_link: List[ConstraintPair],
) -> None:
    normalized_must = {_as_unordered_pair(pair) for pair in must_link}
    normalized_cannot = {_as_unordered_pair(pair) for pair in cannot_link}

    conflicts = normalized_must.intersection(normalized_cannot)

    if conflicts:
        raise ConstraintError(
            f"Contradicting constraints found. "
            f"Same pair is both must-link and cannot-link: {conflicts}"
        )


def _build_must_link_components(
    all_bids: List[int],
    must_link: List[ConstraintPair],
) -> UnionFind:
    union_find = UnionFind(all_bids)

    for left, right in must_link:
        union_find.union(left, right)

    return union_find


def _validate_no_must_link_cannot_link_conflict(
    must_link_components: UnionFind,
    cannot_link: List[ConstraintPair],
) -> None:
    for left, right in cannot_link:
        if must_link_components.find(left) == must_link_components.find(right):
            raise ConstraintError(
                f"Contradicting constraints found. Variants {left} and {right} "
                f"are connected by must-link but also constrained by cannot-link."
            )


def _merge_clusters_by_must_link(
    bid_clusters: List[List[int]],
    group_clusters: List[List[Group]],
    must_link: List[ConstraintPair],
) -> List[List[Group]]:
    if not must_link:
        return group_clusters

    bid_to_cluster_index = {}

    for cluster_index, bid_cluster in enumerate(bid_clusters):
        for bid in bid_cluster:
            bid_to_cluster_index[bid] = cluster_index

    cluster_union_find = UnionFind(list(range(len(group_clusters))))

    for left_bid, right_bid in must_link:
        left_cluster_index = bid_to_cluster_index[left_bid]
        right_cluster_index = bid_to_cluster_index[right_bid]

        cluster_union_find.union(left_cluster_index, right_cluster_index)

    merged_clusters_by_root: Dict[int, List[Group]] = {}

    for cluster_index, group_cluster in enumerate(group_clusters):
        root = cluster_union_find.find(cluster_index)

        if root not in merged_clusters_by_root:
            merged_clusters_by_root[root] = []

        merged_clusters_by_root[root].extend(group_cluster)

    return list(merged_clusters_by_root.values())


def _repair_cannot_link_conflicts(
    clusters: List[List[Group]],
    must_link_components: UnionFind,
    cannot_link: List[ConstraintPair],
) -> List[List[Group]]:
    """
    Repair cannot-link violations by moving a conflicting must-link component
    to the most similar legal cluster.

    If no legal target cluster exists, the component becomes a new singleton
    cluster.
    """

    if not cannot_link:
        return clusters
    
    repair_start_time = time.perf_counter()

    repaired_clusters = [list(cluster) for cluster in clusters]

    total_bids = len(_get_all_bids_from_clusters(repaired_clusters))
    max_iterations = max(1, len(cannot_link) * max(1, total_bids) * 2)
    iteration_count = 0

    changed = True

    while changed:
        iteration_count += 1

        if iteration_count > max_iterations:
            raise ConstraintError(
                "Could not repair all cannot-link constraints within the "
                "iteration limit. The constraints may be too complex for the "
                "current post-processing heuristic."
            )

        changed = False

        for source_cluster_index, source_cluster in enumerate(repaired_clusters):
            if not source_cluster:
                continue

            bid_to_group = _get_bid_to_group_mapping(source_cluster)
            source_bids = set(bid_to_group.keys())

            violation = _find_cannot_link_violation(source_bids, cannot_link)

            if violation is None:
                continue

            left_bid, right_bid = violation

            moving_bids = _choose_moving_component(
                left_bid=left_bid,
                right_bid=right_bid,
                cluster_bids=source_bids,
                bid_to_group=bid_to_group,
                must_link_components=must_link_components,
            )

            moving_groups = [bid_to_group[bid] for bid in moving_bids]

            for group in moving_groups:
                source_cluster.remove(group)

            target_cluster_index = _find_best_legal_target_cluster(
                moving_bids=moving_bids,
                moving_groups=moving_groups,
                clusters=repaired_clusters,
                source_cluster_index=source_cluster_index,
                cannot_link=cannot_link,
            )

            if target_cluster_index is None:
                repaired_clusters.append(moving_groups)
            else:
                repaired_clusters[target_cluster_index].extend(moving_groups)

            changed = True
            break

    result_clusters = [cluster for cluster in repaired_clusters if len(cluster) > 0]

    if DEBUG_SIMILARITY:
        repair_runtime_ms = (time.perf_counter() - repair_start_time) * 1000
        print(
            "[cannot-link-repair-runtime] "
            f"cannot_link_count={len(cannot_link)} "
            f"result_cluster_count={len(result_clusters)} "
            f"runtime_ms={repair_runtime_ms:.2f}"
        )

    return result_clusters


def _get_all_bids_from_clusters(clusters: List[List[Group]]) -> Set[int]:
    all_bids: Set[int] = set()

    for cluster in clusters:
        if not cluster:
            continue

        all_bids.update(_get_bid_to_group_mapping(cluster).keys())

    return all_bids


def _find_cannot_link_violation(
    cluster_bids: Set[int],
    cannot_link: List[ConstraintPair],
) -> Optional[ConstraintPair]:
    for left_bid, right_bid in cannot_link:
        if left_bid in cluster_bids and right_bid in cluster_bids:
            return left_bid, right_bid

    return None


def _choose_moving_component(
    left_bid: int,
    right_bid: int,
    cluster_bids: Set[int],
    bid_to_group: Dict[int, Group],
    must_link_components: UnionFind,
) -> Set[int]:
    """
    Choose which side of a cannot-link conflict should be moved.

    Primary rule:
    - Move the smaller must-link component to minimize changes to the original
      clustering result.

    Tie-break rule:
    - If both components have the same size, move the component that is less
      similar to the remaining variants in the source cluster.
    """

    left_component = _get_component_bids(
        bid=left_bid,
        cluster_bids=cluster_bids,
        must_link_components=must_link_components,
    )

    right_component = _get_component_bids(
        bid=right_bid,
        cluster_bids=cluster_bids,
        must_link_components=must_link_components,
    )

    if len(left_component) < len(right_component):
        return left_component

    if len(right_component) < len(left_component):
        return right_component

    left_similarity = _calculate_component_similarity_to_remaining_cluster(
        component_bids=left_component,
        bid_to_group=bid_to_group,
    )

    right_similarity = _calculate_component_similarity_to_remaining_cluster(
        component_bids=right_component,
        bid_to_group=bid_to_group,
    )

    if DEBUG_SIMILARITY:
        print(
            "[moving-component-tiebreak] "
            f"left_component={sorted(left_component)} "
            f"left_similarity={left_similarity:.4f} "
            f"right_component={sorted(right_component)} "
            f"right_similarity={right_similarity:.4f}"
        )

    if left_similarity < right_similarity:
        return left_component

    if right_similarity < left_similarity:
        return right_component

    # Deterministic fallback for fully equal cases.
    # This avoids depending on set iteration order.
    if min(left_component) > min(right_component):
        return left_component

    return right_component


def _calculate_component_similarity_to_remaining_cluster(
    component_bids: Set[int],
    bid_to_group: Dict[int, Group],
) -> float:
    component_groups = [
        group for bid, group in bid_to_group.items() if bid in component_bids
    ]

    remaining_groups = [
        group for bid, group in bid_to_group.items() if bid not in component_bids
    ]

    if not remaining_groups:
        return 0.0

    return _calculate_group_list_similarity(
        left_groups=component_groups,
        right_groups=remaining_groups,
        use_max_over_right_groups=USE_MAX_GED_FOR_TIE_BREAK,
    )


def _get_component_bids(
    bid: int,
    cluster_bids: Set[int],
    must_link_components: UnionFind,
) -> Set[int]:
    component_root = must_link_components.find(bid)

    return {
        other_bid
        for other_bid in cluster_bids
        if must_link_components.find(other_bid) == component_root
    }


def _find_best_legal_target_cluster(
    moving_bids: Set[int],
    moving_groups: List[Group],
    clusters: List[List[Group]],
    source_cluster_index: int,
    cannot_link: List[ConstraintPair],
) -> Optional[int]:
    best_cluster_index = None
    best_similarity = -1.0

    for candidate_cluster_index, candidate_cluster in enumerate(clusters):
        if candidate_cluster_index == source_cluster_index:
            continue

        if not candidate_cluster:
            continue

        candidate_bids = set(_get_bid_to_group_mapping(candidate_cluster).keys())

        if not _is_legal_target_cluster(
            moving_bids=moving_bids,
            target_bids=candidate_bids,
            cannot_link=cannot_link,
        ):
            continue

        similarity = _calculate_group_list_similarity(
            left_groups=moving_groups,
            right_groups=candidate_cluster,
            use_max_over_right_groups=USE_MAX_GED_FOR_TARGET_SELECTION,
        )

        if DEBUG_SIMILARITY:
            print(
                "[target-selection] "
                f"moving_bids={sorted(moving_bids)} "
                f"candidate_cluster_index={candidate_cluster_index} "
                f"candidate_cluster_size={len(candidate_cluster)} "
                f"similarity={similarity:.4f}"
            )

        if similarity > best_similarity:
            best_similarity = similarity
            best_cluster_index = candidate_cluster_index

    if DEBUG_SIMILARITY:
        print(
            "[target-selection-result] "
            f"moving_bids={sorted(moving_bids)} "
            f"chosen_cluster_index={best_cluster_index} "
            f"best_similarity={best_similarity:.4f}"
    )
        
    return best_cluster_index


def _is_legal_target_cluster(
    moving_bids: Set[int],
    target_bids: Set[int],
    cannot_link: List[ConstraintPair],
) -> bool:
    for left_bid, right_bid in cannot_link:
        if left_bid in moving_bids and right_bid in target_bids:
            return False

        if right_bid in moving_bids and left_bid in target_bids:
            return False

    return True


def _calculate_ged_group_list_similarity(
    left_groups: List[Group],
    right_groups: List[Group],
    use_max_over_right_groups: bool,
) -> float:
    if USE_JACCARD_TOP_K_PREFILTER_FOR_GED:
        return calculate_neighborhood_tree_group_list_similarity(
            left_groups=left_groups,
            right_groups=right_groups,
            prefilter_similarity_fn=_calculate_structural_jaccard_group_list_similarity,
            top_k_prefilter=TOP_K_PREFILTER,
            use_max_over_right_groups=use_max_over_right_groups,
        )

    return calculate_neighborhood_tree_group_list_similarity(
        left_groups=left_groups,
        right_groups=right_groups,
        use_max_over_right_groups=use_max_over_right_groups,
    )

def _calculate_group_list_similarity(
    left_groups: List[Group],
    right_groups: List[Group],
    use_max_over_right_groups: bool,
) -> float:
    """
    Dispatch similarity calculation.

    In evaluation mode, compute both Structural Jaccard and GED-based
    similarity so that we can compare score differences and runtime.

    In normal mode, return only the selected similarity method.
    """

    if COMPARE_JACCARD_AND_GED:
        jaccard_start = time.perf_counter()
        jaccard_similarity = _calculate_structural_jaccard_group_list_similarity(
            left_groups=left_groups,
            right_groups=right_groups,
        )
        jaccard_runtime_ms = (time.perf_counter() - jaccard_start) * 1000

        ged_start = time.perf_counter()
        ged_similarity = _calculate_ged_group_list_similarity(
            left_groups=left_groups,
            right_groups=right_groups,
            use_max_over_right_groups=use_max_over_right_groups,
        )
        ged_runtime_ms = (time.perf_counter() - ged_start) * 1000

        if DEBUG_SIMILARITY:
            cache_stats = get_pairwise_similarity_cache_stats()

            print(
                "[similarity-comparison] "
                f"left_size={len(left_groups)} "
                f"right_size={len(right_groups)} "
                f"aggregation={'max' if use_max_over_right_groups else 'avg'} "
                f"jaccard={jaccard_similarity:.4f} "
                f"jaccard_ms={jaccard_runtime_ms:.2f} "
                f"ged={ged_similarity:.4f} "
                f"ged_ms={ged_runtime_ms:.2f} "
                f"cache_size={cache_stats['size']} "
                f"cache_hits={cache_stats['hits']} "
                f"cache_misses={cache_stats['misses']} "
                f"sdted_cache_size={cache_stats['sdted_cache_size']} "
                f"sdted_cache_hits={cache_stats['sdted_cache_hits']} "
                f"sdted_cache_misses={cache_stats['sdted_cache_misses']}"
            )

        if USE_NEIGHBORHOOD_TREE_GED_SIMILARITY:
            return ged_similarity

        return jaccard_similarity

    if USE_NEIGHBORHOOD_TREE_GED_SIMILARITY:
        if DEBUG_SIMILARITY:
            print("[similarity] using GED-based similarity")

        return _calculate_ged_group_list_similarity(
            left_groups=left_groups,
            right_groups=right_groups,
            use_max_over_right_groups=use_max_over_right_groups,
        )

    if DEBUG_SIMILARITY:
        print("[similarity] using Structural Jaccard similarity")

    return _calculate_structural_jaccard_group_list_similarity(
        left_groups=left_groups,
        right_groups=right_groups,
    )


ACTIVITY_SIMILARITY_WEIGHT = 0.5
DIRECT_FOLLOW_SIMILARITY_WEIGHT = 0.3
PARALLEL_SIMILARITY_WEIGHT = 0.2


def _calculate_structural_jaccard_group_list_similarity(
    left_groups: List[Group],
    right_groups: List[Group],
) -> float:
    """
    Calculate a lightweight structural similarity score between two groups of
    variants.

    The baseline combines three feature types:
    1. activity-label counts
    2. direct-follow relations
    3. parallel relations

    This is inspired by graph/neighborhood-based similarity, but intentionally
    remains much simpler than full GED or neighborhood-tree matching.

    The score is only used as a local heuristic for reassignment during
    cannot-link post-processing.
    """

    (
        left_activity_counts,
        left_direct_follow_counts,
        left_parallel_counts,
    ) = _extract_structural_features_from_groups(left_groups)

    (
        right_activity_counts,
        right_direct_follow_counts,
        right_parallel_counts,
    ) = _extract_structural_features_from_groups(right_groups)

    weighted_similarity_sum = 0.0
    active_weight_sum = 0.0

    # Activity counts are the stable base signal.
    if left_activity_counts or right_activity_counts:
        activity_similarity = _weighted_jaccard_counter(
            left_activity_counts,
            right_activity_counts,
        )
        weighted_similarity_sum += (
            ACTIVITY_SIMILARITY_WEIGHT * activity_similarity
        )
        active_weight_sum += ACTIVITY_SIMILARITY_WEIGHT

    # Direct-follow relations capture sequential structure.
    if left_direct_follow_counts or right_direct_follow_counts:
        direct_follow_similarity = _weighted_jaccard_counter(
            left_direct_follow_counts,
            right_direct_follow_counts,
        )
        weighted_similarity_sum += (
            DIRECT_FOLLOW_SIMILARITY_WEIGHT * direct_follow_similarity
        )
        active_weight_sum += DIRECT_FOLLOW_SIMILARITY_WEIGHT

    # Parallel relations capture concurrency structure.
    if left_parallel_counts or right_parallel_counts:
        parallel_similarity = _weighted_jaccard_counter(
            left_parallel_counts,
            right_parallel_counts,
        )
        weighted_similarity_sum += (
            PARALLEL_SIMILARITY_WEIGHT * parallel_similarity
        )
        active_weight_sum += PARALLEL_SIMILARITY_WEIGHT

    if active_weight_sum == 0:
        return 0.0

    return weighted_similarity_sum / active_weight_sum


def _weighted_jaccard_counter(
    left_counts: Counter,
    right_counts: Counter,
) -> float:
    """
    Weighted Jaccard similarity for Counter-like feature vectors.

    sum(min(count_left(feature), count_right(feature)))
    /
    sum(max(count_left(feature), count_right(feature)))
    """

    all_features = set(left_counts.keys()).union(right_counts.keys())

    if not all_features:
        return 0.0

    intersection_size = sum(
        min(left_counts[feature], right_counts[feature])
        for feature in all_features
    )

    union_size = sum(
        max(left_counts[feature], right_counts[feature])
        for feature in all_features
    )

    if union_size == 0:
        return 0.0

    return intersection_size / union_size


def _extract_structural_features_from_groups(
    groups: List[Group],
) -> Tuple[Counter, Counter, Counter]:
    """
    Extract structural features from a list of Cortado variant groups.

    Returns:
    - activity-label counts
    - direct-follow relation counts
    - parallel relation counts
    """

    activity_counts = Counter()
    direct_follow_counts = Counter()
    parallel_counts = Counter()

    for group in groups:
        try:
            serialized_group = group.serialize()

            (
                group_activity_counts,
                group_direct_follow_counts,
                group_parallel_counts,
                _,
                _,
                _,
            ) = _extract_structural_features_from_serialized(serialized_group)

            activity_counts.update(group_activity_counts)
            direct_follow_counts.update(group_direct_follow_counts)
            parallel_counts.update(group_parallel_counts)

        except Exception:
            # Fallback: keep the heuristic robust even if serialization changes.
            activity_counts.update([str(group)])

    return activity_counts, direct_follow_counts, parallel_counts


def _extract_structural_features_from_serialized(
    serialized: Any,
) -> Tuple[Counter, Counter, Counter, Set[str], Set[str], Set[str]]:
    """
    Recursively extract structural features from a serialized Cortado group.

    Returns:
    - activity counts
    - direct-follow counts
    - parallel counts
    - start labels
    - end labels
    - all labels
    """

    activity_counts = Counter()
    direct_follow_counts = Counter()
    parallel_counts = Counter()

    if isinstance(serialized, dict):
        if "leaf" in serialized:
            labels = _normalize_leaf_labels(serialized["leaf"])
            activity_counts.update(labels)

            label_set = set(labels)
            return (
                activity_counts,
                direct_follow_counts,
                parallel_counts,
                label_set,
                label_set,
                label_set,
            )

        if "follows" in serialized:
            children = _normalize_children(serialized["follows"])

            sequence_start_labels: Set[str] = set()
            sequence_end_labels: Set[str] = set()
            sequence_all_labels: Set[str] = set()

            previous_end_labels: Set[str] = set()

            for child in children:
                (
                    child_activity_counts,
                    child_direct_follow_counts,
                    child_parallel_counts,
                    child_start_labels,
                    child_end_labels,
                    child_all_labels,
                ) = _extract_structural_features_from_serialized(child)

                activity_counts.update(child_activity_counts)
                direct_follow_counts.update(child_direct_follow_counts)
                parallel_counts.update(child_parallel_counts)

                if previous_end_labels and child_start_labels:
                    for left_label in previous_end_labels:
                        for right_label in child_start_labels:
                            direct_follow_counts.update(
                                [(left_label, right_label)]
                            )

                if not sequence_start_labels:
                    sequence_start_labels = set(child_start_labels)

                if child_end_labels:
                    sequence_end_labels = set(child_end_labels)

                sequence_all_labels.update(child_all_labels)
                previous_end_labels = set(child_end_labels)

            return (
                activity_counts,
                direct_follow_counts,
                parallel_counts,
                sequence_start_labels,
                sequence_end_labels,
                sequence_all_labels,
            )

        if "parallel" in serialized:
            children = _normalize_children(serialized["parallel"])

            parallel_start_labels: Set[str] = set()
            parallel_end_labels: Set[str] = set()
            parallel_all_labels: Set[str] = set()
            child_label_sets: List[Set[str]] = []

            for child in children:
                (
                    child_activity_counts,
                    child_direct_follow_counts,
                    child_parallel_counts,
                    child_start_labels,
                    child_end_labels,
                    child_all_labels,
                ) = _extract_structural_features_from_serialized(child)

                activity_counts.update(child_activity_counts)
                direct_follow_counts.update(child_direct_follow_counts)
                parallel_counts.update(child_parallel_counts)

                parallel_start_labels.update(child_start_labels)
                parallel_end_labels.update(child_end_labels)
                parallel_all_labels.update(child_all_labels)

                if child_all_labels:
                    child_label_sets.append(set(child_all_labels))

            # Add unordered parallel relations between labels in different
            # parallel branches.
            for i in range(len(child_label_sets)):
                for j in range(i + 1, len(child_label_sets)):
                    for left_label in child_label_sets[i]:
                        for right_label in child_label_sets[j]:
                            parallel_counts.update(
                                [_as_unordered_label_pair(left_label, right_label)]
                            )

            return (
                activity_counts,
                direct_follow_counts,
                parallel_counts,
                parallel_start_labels,
                parallel_end_labels,
                parallel_all_labels,
            )

        # Generic fallback for other possible serialized group structures.
        generic_start_labels: Set[str] = set()
        generic_end_labels: Set[str] = set()
        generic_all_labels: Set[str] = set()

        for value in serialized.values():
            (
                child_activity_counts,
                child_direct_follow_counts,
                child_parallel_counts,
                child_start_labels,
                child_end_labels,
                child_all_labels,
            ) = _extract_structural_features_from_serialized(value)

            activity_counts.update(child_activity_counts)
            direct_follow_counts.update(child_direct_follow_counts)
            parallel_counts.update(child_parallel_counts)

            generic_start_labels.update(child_start_labels)
            generic_end_labels.update(child_end_labels)
            generic_all_labels.update(child_all_labels)

        return (
            activity_counts,
            direct_follow_counts,
            parallel_counts,
            generic_start_labels,
            generic_end_labels,
            generic_all_labels,
        )

    if isinstance(serialized, list):
        list_start_labels: Set[str] = set()
        list_end_labels: Set[str] = set()
        list_all_labels: Set[str] = set()

        for element in serialized:
            (
                child_activity_counts,
                child_direct_follow_counts,
                child_parallel_counts,
                child_start_labels,
                child_end_labels,
                child_all_labels,
            ) = _extract_structural_features_from_serialized(element)

            activity_counts.update(child_activity_counts)
            direct_follow_counts.update(child_direct_follow_counts)
            parallel_counts.update(child_parallel_counts)

            list_start_labels.update(child_start_labels)
            list_end_labels.update(child_end_labels)
            list_all_labels.update(child_all_labels)

        return (
            activity_counts,
            direct_follow_counts,
            parallel_counts,
            list_start_labels,
            list_end_labels,
            list_all_labels,
        )

    return (
        activity_counts,
        direct_follow_counts,
        parallel_counts,
        set(),
        set(),
        set(),
    )


def _normalize_leaf_labels(leaf: Any) -> List[str]:
    if isinstance(leaf, list):
        return [str(label) for label in leaf]

    return [str(leaf)]


def _normalize_children(children: Any) -> List[Any]:
    if isinstance(children, list):
        return children

    return [children]


def _as_unordered_label_pair(left_label: str, right_label: str) -> Tuple[str, str]:
    return tuple(sorted((left_label, right_label)))


def _get_bid_to_group_mapping(cluster: List[Group]) -> Dict[int, Group]:
    bid_to_group = {}

    for group in cluster:
        bid, _ = cache_util.map_group_to_cached_variant(group)

        if bid is None:
            raise ConstraintError(
                "Could not map clustered group back to cached variant."
            )

        bid_to_group[bid] = group

    return bid_to_group


def _as_unordered_pair(pair: ConstraintPair) -> Tuple[int, int]:
    left, right = pair
    return tuple(sorted((left, right)))