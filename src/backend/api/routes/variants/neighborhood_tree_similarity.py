"""
Neighborhood-tree-based GED approximation for Cortado variants.

This module implements a Python version inspired by:
Bause, Permann & Kriege (2024):
"Approximating the Graph Edit Distance with Compact Neighborhood Representations"

Important:
- This is not exact GED.
- It is an approximate, neighborhood-tree-based graph similarity.
- It is adapted to Cortado concurrency variants.
- It uses compressed k-redundant neighborhood trees, canonical tree keys,
  subtree-level SDTED caching, and pairwise GED similarity caching.
- It is intended for constrained clustering post-processing only.
- The public entry point is:
  calculate_neighborhood_tree_group_list_similarity(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple

from cortado_core.utils.split_graph import Group


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NEIGHBORHOOD_TREE_HEIGHT = 2

VERTEX_INSERT_DELETE_COST = 1.0
VERTEX_RELABEL_COST = 1.0

EDGE_INSERT_DELETE_COST = 1.0
EDGE_RELABEL_COST = 1.0

TREE_NODE_INSERT_DELETE_COST = 1.0
TREE_NODE_RELABEL_COST = 1.0
TREE_EDGE_RELABEL_COST = 0.5

# Smaller values reduce the influence of deeper neighborhood levels.
DEPTH_DECAY = 0.5

# Whether SDTED(left, right) and SDTED(right, left) should share cache entries.
# This is valid because the current tree edit costs are symmetric.
USE_SYMMETRIC_SDTED_CACHE_KEY = True

# For group-list similarity:
# For each left group, compare it to the best matching right group.
# Then average over all left groups.
USE_MAX_OVER_TARGET_CLUSTER = True

ENABLE_PAIRWISE_SIMILARITY_CACHE = True
ENABLE_CANONICAL_TREE_ENCODING = True
ENABLE_SUBTREE_SDTED_CACHE = True

# Compressed k-redundant neighborhood trees.
# This keeps the tree compact by merging repeated original graph vertices
# that occur at the same depth during BFS expansion.
USE_COMPRESSED_NEIGHBORHOOD_TREES = True

# k = 0 corresponds to a compact shortest-path-like neighborhood tree.
# Larger k allows repeated vertices in nearby deeper layers.
NEIGHBORHOOD_TREE_REDUNDANCY_K = 0

# Avoid immediately going back to the parent vertex, which reduces tottering.
AVOID_IMMEDIATE_BACKTRACKING = True

_PAIRWISE_SIMILARITY_CACHE: Dict[Tuple[int, int], float] = {}
_PAIRWISE_CACHE_HITS = 0
_PAIRWISE_CACHE_MISSES = 0


# ---------------------------------------------------------------------------
# Basic graph and tree structures
# ---------------------------------------------------------------------------

VertexId = int
Edge = Tuple[VertexId, VertexId, str]


@dataclass
class ProcessGraph:
    """
    Simplified graph representation for a Cortado variant.

    Vertices are activity occurrences.
    The vertex label is the activity label.

    Edges are:
    - directed sequence edges: (source, target, "sequence")
    - normalized parallel edges: (min_id, max_id, "parallel")

    For neighborhood expansion, sequence edges are treated as traversable
    in both directions, but the local edge label keeps direction information:
    - "sequence_out" when moving source -> target
    - "sequence_in" when moving target -> source
    - "parallel" for parallel edges
    """

    labels: Dict[VertexId, str] = field(default_factory=dict)
    edges: Set[Edge] = field(default_factory=set)
    adjacency: Dict[VertexId, List[Tuple[VertexId, str]]] = field(
        default_factory=dict
    )

    def add_vertex(self, label: str) -> VertexId:
        vertex_id = len(self.labels)
        self.labels[vertex_id] = str(label)
        self.adjacency[vertex_id] = []
        return vertex_id

    def add_sequence_edge(self, source: VertexId, target: VertexId) -> None:
        self.edges.add((source, target, "sequence"))
        self.adjacency[source].append((target, "sequence_out"))
        self.adjacency[target].append((source, "sequence_in"))

    def add_parallel_edge(self, left: VertexId, right: VertexId) -> None:
        if left == right:
            return

        a, b = sorted((left, right))
        self.edges.add((a, b, "parallel"))
        self.adjacency[a].append((b, "parallel"))
        self.adjacency[b].append((a, "parallel"))


@dataclass(frozen=True)
class NeighborhoodTree:
    label: str
    incoming_edge_label: Optional[str]
    children: Tuple["NeighborhoodTree", ...] = ()


@dataclass
class BuildResult:
    graph: ProcessGraph
    start_vertices: Set[VertexId]
    end_vertices: Set[VertexId]
    all_vertices: Set[VertexId]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def calculate_neighborhood_tree_group_list_similarity(
    left_groups: List[Group],
    right_groups: List[Group],
    prefilter_similarity_fn: Optional[Callable[[List[Group], List[Group]], float]] = None,
    top_k_prefilter: Optional[int] = None,
    use_max_over_right_groups: bool = USE_MAX_OVER_TARGET_CLUSTER,
) -> float:
    """
    Compare a moving component with a candidate cluster.

    This function keeps the same interface as the current Jaccard-based
    group-list similarity.

    If prefilter_similarity_fn and top_k_prefilter are provided, the function
    first selects the top-k right groups using the cheap prefilter similarity
    and only computes GED against these candidates.

    use_max_over_right_groups controls how multiple GED scores against the
    right-side candidate groups are aggregated:
    - True: use max similarity
    - False: use average similarity

    For GED, we should not merge a whole cluster into one artificial graph.
    Instead, we compare variant graph vs. variant graph and aggregate:

    Sim(left_groups, right_groups)
      = average over left_group of max similarity(left_group, right_group)

    This is suitable for:
    - moving component vs. candidate cluster
    - component vs. remaining source cluster
    """

    if not left_groups or not right_groups:
        return 0.0

    best_scores: List[float] = []

    for left_group in left_groups:
        candidate_right_groups = _select_top_k_prefilter_candidates(
            left_group=left_group,
            right_groups=right_groups,
            prefilter_similarity_fn=prefilter_similarity_fn,
            top_k_prefilter=top_k_prefilter,
        )

        similarities = [
            _calculate_cached_neighborhood_tree_pair_similarity(left_group, right_group)
            for right_group in candidate_right_groups
        ]

        if not similarities:
            best_scores.append(0.0)
        elif use_max_over_right_groups:
            best_scores.append(max(similarities))
        else:
            best_scores.append(sum(similarities) / len(similarities))

    return sum(best_scores) / len(best_scores)


def _select_top_k_prefilter_candidates(
    left_group: Group,
    right_groups: List[Group],
    prefilter_similarity_fn: Optional[Callable[[List[Group], List[Group]], float]],
    top_k_prefilter: Optional[int],
) -> List[Group]:
    """
    Select the top-k most promising right groups using a cheap prefilter
    similarity, e.g. Structural Jaccard.

    If no prefilter is configured, all right groups are returned.
    """

    if (
        prefilter_similarity_fn is None
        or top_k_prefilter is None
        or top_k_prefilter <= 0
        or len(right_groups) <= top_k_prefilter
    ):
        return right_groups

    scored_candidates: List[Tuple[float, int, Group]] = []

    for index, right_group in enumerate(right_groups):
        similarity = prefilter_similarity_fn(
            [left_group],
            [right_group],
        )
        scored_candidates.append((similarity, index, right_group))

    scored_candidates.sort(
        key=lambda item: (item[0], -item[1]),
        reverse=True,
    )

    return [
        right_group
        for _, _, right_group in scored_candidates[:top_k_prefilter]
    ]


def clear_pairwise_similarity_cache() -> None:
    """
    Clear the pairwise GED similarity cache.

    This is useful when a new event log is loaded or when we want to run
    clean runtime measurements.
    """

    global _PAIRWISE_CACHE_HITS
    global _PAIRWISE_CACHE_MISSES

    _PAIRWISE_SIMILARITY_CACHE.clear()
    _PAIRWISE_CACHE_HITS = 0
    _PAIRWISE_CACHE_MISSES = 0
    _sdted_cached.cache_clear()


def get_pairwise_similarity_cache_stats() -> Dict[str, int]:
    sdted_cache_info = _sdted_cached.cache_info()

    return {
        "size": len(_PAIRWISE_SIMILARITY_CACHE),
        "hits": _PAIRWISE_CACHE_HITS,
        "misses": _PAIRWISE_CACHE_MISSES,
        "sdted_cache_hits": sdted_cache_info.hits,
        "sdted_cache_misses": sdted_cache_info.misses,
        "sdted_cache_size": sdted_cache_info.currsize,
    }


def _get_group_cache_key(group: Group) -> int:
    """
    Use the Cortado Group hash as a stable key for cached variants.

    This matches the existing backend mapping logic, which maps clustered
    groups back to cached variants via hash(group).
    """

    return hash(group)


def _calculate_cached_neighborhood_tree_pair_similarity(
    left_group: Group,
    right_group: Group,
) -> float:
    global _PAIRWISE_CACHE_HITS
    global _PAIRWISE_CACHE_MISSES

    if not ENABLE_PAIRWISE_SIMILARITY_CACHE:
        return calculate_neighborhood_tree_pair_similarity(left_group, right_group)

    left_key = _get_group_cache_key(left_group)
    right_key = _get_group_cache_key(right_group)

    # Similarity is symmetric, so normalize the cache key.
    cache_key = tuple(sorted((left_key, right_key)))

    if cache_key in _PAIRWISE_SIMILARITY_CACHE:
        _PAIRWISE_CACHE_HITS += 1
        return _PAIRWISE_SIMILARITY_CACHE[cache_key]

    _PAIRWISE_CACHE_MISSES += 1
    similarity = calculate_neighborhood_tree_pair_similarity(left_group, right_group)
    _PAIRWISE_SIMILARITY_CACHE[cache_key] = similarity
    return similarity


def calculate_neighborhood_tree_pair_similarity(
    left_group: Group,
    right_group: Group,
) -> float:
    """
    Compute a similarity score in [0, 1] for two Cortado Groups.

    Internally:
    Group -> ProcessGraph -> approximate GED distance -> normalized similarity.
    """

    left_graph = group_to_process_graph(left_group)
    right_graph = group_to_process_graph(right_group)

    distance = approximate_graph_edit_distance(left_graph, right_graph)

    normalizer = max(
        1,
        len(left_graph.labels)
        + len(right_graph.labels)
        + len(left_graph.edges)
        + len(right_graph.edges),
    )

    normalized_distance = distance / normalizer

    return 1.0 / (1.0 + normalized_distance)


# ---------------------------------------------------------------------------
# Cortado Group -> ProcessGraph
# ---------------------------------------------------------------------------

def group_to_process_graph(group: Group) -> ProcessGraph:
    graph = ProcessGraph()
    serialized = _safe_serialize_group(group)
    _build_graph_from_serialized(serialized, graph)
    return graph


def _safe_serialize_group(group: Group) -> Any:
    """
    Serialize a Cortado Group robustly.

    Some clustered Group objects may not have DFS ids assigned yet.
    Cortado's serialize() can fail in that case with:
    'LeafGroup' object has no attribute 'id'

    Assigning DFS ids before serialization makes the graph conversion more
    robust for groups returned by different clustering algorithms.
    """

    try:
        if hasattr(group, "assign_dfs_ids"):
            group.assign_dfs_ids()

        return group.serialize()

    except Exception as error:
        raise RuntimeError(
            f"Could not serialize group for GED similarity: {error}"
        ) from error


def _build_graph_from_serialized(
    serialized: Any,
    graph: ProcessGraph,
) -> BuildResult:
    """
    Recursively convert a serialized Cortado variant into a process graph.

    Minimal semantics:
    - leaf -> activity occurrence vertex
    - follows -> sequence edges from previous end vertices to next start vertices
    - parallel -> parallel edges between vertices from different branches
    """

    if isinstance(serialized, dict):
        if "leaf" in serialized:
            labels = _normalize_leaf_labels(serialized["leaf"])
            vertices = {graph.add_vertex(label) for label in labels}

            return BuildResult(
                graph=graph,
                start_vertices=set(vertices),
                end_vertices=set(vertices),
                all_vertices=set(vertices),
            )

        if "follows" in serialized:
            children = _normalize_children(serialized["follows"])

            sequence_start_vertices: Set[VertexId] = set()
            sequence_end_vertices: Set[VertexId] = set()
            sequence_all_vertices: Set[VertexId] = set()

            previous_end_vertices: Set[VertexId] = set()

            for child in children:
                child_result = _build_graph_from_serialized(child, graph)

                if previous_end_vertices and child_result.start_vertices:
                    for left in previous_end_vertices:
                        for right in child_result.start_vertices:
                            graph.add_sequence_edge(left, right)

                if not sequence_start_vertices:
                    sequence_start_vertices = set(child_result.start_vertices)

                if child_result.end_vertices:
                    sequence_end_vertices = set(child_result.end_vertices)

                sequence_all_vertices.update(child_result.all_vertices)
                previous_end_vertices = set(child_result.end_vertices)

            return BuildResult(
                graph=graph,
                start_vertices=sequence_start_vertices,
                end_vertices=sequence_end_vertices,
                all_vertices=sequence_all_vertices,
            )

        if "parallel" in serialized:
            children = _normalize_children(serialized["parallel"])

            parallel_start_vertices: Set[VertexId] = set()
            parallel_end_vertices: Set[VertexId] = set()
            parallel_all_vertices: Set[VertexId] = set()
            branch_vertex_sets: List[Set[VertexId]] = []

            for child in children:
                child_result = _build_graph_from_serialized(child, graph)

                parallel_start_vertices.update(child_result.start_vertices)
                parallel_end_vertices.update(child_result.end_vertices)
                parallel_all_vertices.update(child_result.all_vertices)

                if child_result.all_vertices:
                    branch_vertex_sets.append(set(child_result.all_vertices))

            for i in range(len(branch_vertex_sets)):
                for j in range(i + 1, len(branch_vertex_sets)):
                    for left in branch_vertex_sets[i]:
                        for right in branch_vertex_sets[j]:
                            graph.add_parallel_edge(left, right)

            return BuildResult(
                graph=graph,
                start_vertices=parallel_start_vertices,
                end_vertices=parallel_end_vertices,
                all_vertices=parallel_all_vertices,
            )

        # Generic fallback for unexpected wrappers.
        generic_start_vertices: Set[VertexId] = set()
        generic_end_vertices: Set[VertexId] = set()
        generic_all_vertices: Set[VertexId] = set()

        for value in serialized.values():
            child_result = _build_graph_from_serialized(value, graph)
            generic_start_vertices.update(child_result.start_vertices)
            generic_end_vertices.update(child_result.end_vertices)
            generic_all_vertices.update(child_result.all_vertices)

        return BuildResult(
            graph=graph,
            start_vertices=generic_start_vertices,
            end_vertices=generic_end_vertices,
            all_vertices=generic_all_vertices,
        )

    if isinstance(serialized, list):
        list_start_vertices: Set[VertexId] = set()
        list_end_vertices: Set[VertexId] = set()
        list_all_vertices: Set[VertexId] = set()

        for element in serialized:
            child_result = _build_graph_from_serialized(element, graph)
            list_start_vertices.update(child_result.start_vertices)
            list_end_vertices.update(child_result.end_vertices)
            list_all_vertices.update(child_result.all_vertices)

        return BuildResult(
            graph=graph,
            start_vertices=list_start_vertices,
            end_vertices=list_end_vertices,
            all_vertices=list_all_vertices,
        )

    return BuildResult(graph=graph, start_vertices=set(), end_vertices=set(), all_vertices=set())


def _normalize_leaf_labels(leaf: Any) -> List[str]:
    if isinstance(leaf, list):
        return [str(label) for label in leaf]
    return [str(leaf)]


def _normalize_children(children: Any) -> List[Any]:
    if isinstance(children, list):
        return children
    return [children]


# ---------------------------------------------------------------------------
# Neighborhood tree construction
# ---------------------------------------------------------------------------
def _build_simple_neighborhood_tree(
    graph: ProcessGraph,
    root: VertexId,
    height: int = NEIGHBORHOOD_TREE_HEIGHT,
) -> NeighborhoodTree:
    """
    Build a height-limited neighborhood tree for a vertex.

    This first version uses path-pruning to avoid cycles.
    It captures the core paper idea but does not yet implement the full
    compressed k-redundant neighborhood tree optimization.
    """

    return _build_neighborhood_tree_recursive(
        graph=graph,
        current=root,
        remaining_height=height,
        visited=frozenset({root}),
        incoming_edge_label=None,
    )


def build_neighborhood_tree(
    graph: ProcessGraph,
    root: VertexId,
    height: int = NEIGHBORHOOD_TREE_HEIGHT,
) -> NeighborhoodTree:
    """
    Build a neighborhood tree for one graph vertex.

    By default, this uses a compressed k-redundant construction inspired by
    the paper. The old path-pruning version is kept as a fallback.
    """

    if USE_COMPRESSED_NEIGHBORHOOD_TREES:
        return _build_compressed_neighborhood_tree(
            graph=graph,
            root=root,
            height=height,
            redundancy_k=NEIGHBORHOOD_TREE_REDUNDANCY_K,
        )

    return _build_simple_neighborhood_tree(
        graph=graph,
        root=root,
        height=height,
    )


def _get_neighbor_edges(
    graph: ProcessGraph,
    vertex_id: VertexId,
) -> List[Tuple[VertexId, str]]:
    """
    Return traversable neighbor edges for one process graph vertex.

    ProcessGraph stores sequence and parallel traversal information in
    graph.adjacency:
    - sequence_out
    - sequence_in
    - parallel
    """

    return graph.adjacency.get(vertex_id, [])


def _build_compressed_neighborhood_tree(
    graph: ProcessGraph,
    root: VertexId,
    height: int,
    redundancy_k: int,
) -> NeighborhoodTree:
    """
    Build a compressed k-redundant neighborhood tree.

    This is a practical Cortado-specific approximation of the compressed
    neighborhood tree idea from the paper.

    Compared to the simple version, this version:
    - expands the neighborhood with bounded height;
    - avoids immediate backtracking;
    - limits repeated occurrences of the same original graph vertex by k;
    - compresses duplicate child subtrees using canonical keys.
    """

    first_depth_by_vertex: Dict[VertexId, int] = {root: 0}

    return _build_compressed_neighborhood_tree_recursive(
        graph=graph,
        current=root,
        remaining_height=height,
        current_depth=0,
        parent=None,
        incoming_edge_label=None,
        first_depth_by_vertex=first_depth_by_vertex,
        redundancy_k=redundancy_k,
    )


def _build_compressed_neighborhood_tree_recursive(
    graph: ProcessGraph,
    current: VertexId,
    remaining_height: int,
    current_depth: int,
    parent: Optional[VertexId],
    incoming_edge_label: Optional[str],
    first_depth_by_vertex: Dict[VertexId, int],
    redundancy_k: int,
) -> NeighborhoodTree:
    if remaining_height == 0:
        return NeighborhoodTree(
            label=graph.labels[current],
            incoming_edge_label=incoming_edge_label,
            children=(),
        )

    children_by_key: Dict[Tuple, NeighborhoodTree] = {}

    for neighbor, edge_label in _get_neighbor_edges(graph, current):
        if (
            AVOID_IMMEDIATE_BACKTRACKING
            and parent is not None
            and neighbor == parent
        ):
            continue

        next_depth = current_depth + 1

        if neighbor not in first_depth_by_vertex:
            first_depth_by_vertex[neighbor] = next_depth

        # k-redundancy rule:
        # Allow repeated vertices only if they occur within k levels after
        # their first discovery depth.
        if first_depth_by_vertex[neighbor] + redundancy_k < next_depth:
            continue

        child = _build_compressed_neighborhood_tree_recursive(
            graph=graph,
            current=neighbor,
            remaining_height=remaining_height - 1,
            current_depth=next_depth,
            parent=current,
            incoming_edge_label=edge_label,
            first_depth_by_vertex=dict(first_depth_by_vertex),
            redundancy_k=redundancy_k,
        )

        # Compress duplicate children. The incoming edge label is part of the
        # canonical key, so sequence/parallel semantics are preserved.
        child_key = _tree_key(child)
        children_by_key[child_key] = child

    children = tuple(
        sorted(children_by_key.values(), key=_tree_sort_key)
    )

    return NeighborhoodTree(
        label=graph.labels[current],
        incoming_edge_label=incoming_edge_label,
        children=children,
    )


def _build_neighborhood_tree_recursive(
    graph: ProcessGraph,
    current: VertexId,
    remaining_height: int,
    visited: FrozenSet[VertexId],
    incoming_edge_label: Optional[str],
) -> NeighborhoodTree:
    if remaining_height == 0:
        return NeighborhoodTree(
            label=graph.labels[current],
            incoming_edge_label=incoming_edge_label,
            children=(),
        )

    children: List[NeighborhoodTree] = []

    for neighbor, edge_label in graph.adjacency.get(current, []):
        if neighbor in visited:
            continue

        child = _build_neighborhood_tree_recursive(
            graph=graph,
            current=neighbor,
            remaining_height=remaining_height - 1,
            visited=frozenset(set(visited) | {neighbor}),
            incoming_edge_label=edge_label,
        )
        children.append(child)

    # Deterministic ordering helps caching and reproducibility.
    children.sort(key=_tree_sort_key)

    return NeighborhoodTree(
        label=graph.labels[current],
        incoming_edge_label=incoming_edge_label,
        children=tuple(children),
    )


def _tree_sort_key(tree: NeighborhoodTree) -> Tuple:
    return (
        tree.label,
        tree.incoming_edge_label or "",
        tuple(_tree_sort_key(child) for child in tree.children),
    )


def _canonical_tree_key(tree: NeighborhoodTree) -> Tuple:
    """
    Return a canonical tuple representation of a neighborhood tree.

    The key is independent of the original child order. This makes SDTED
    caching more stable and closer to the canonical tree representation idea
    used in compressed neighborhood-tree implementations.
    """

    child_keys = tuple(
        sorted(_canonical_tree_key(child) for child in tree.children)
    )

    return (
        tree.label,
        tree.incoming_edge_label or "",
        child_keys,
    )

# ---------------------------------------------------------------------------
# SDTED for neighborhood trees
# ---------------------------------------------------------------------------

def sdted(left_tree: NeighborhoodTree, right_tree: NeighborhoodTree) -> float:
    left_key = _tree_key(left_tree)
    right_key = _tree_key(right_tree)

    if ENABLE_SUBTREE_SDTED_CACHE:
        cache_key = _sdted_cache_key(left_key, right_key)
        return _sdted_cached(cache_key[0], cache_key[1])

    left_tree_from_key = _tree_from_key(left_key)
    right_tree_from_key = _tree_from_key(right_key)
    return _sdted_uncached(left_tree_from_key, right_tree_from_key)


def _sdted_cache_key(left_key: Tuple, right_key: Tuple) -> Tuple[Tuple, Tuple]:
    """
    Normalize SDTED cache keys.

    Since the current SDTED cost model is symmetric, we can reuse cached
    results for both SDTED(A, B) and SDTED(B, A).
    """

    if not USE_SYMMETRIC_SDTED_CACHE_KEY:
        return left_key, right_key

    if repr(left_key) <= repr(right_key):
        return left_key, right_key

    return right_key, left_key


@lru_cache(maxsize=50000)
def _sdted_cached(left_key: Tuple, right_key: Tuple) -> float:
    left_tree = _tree_from_key(left_key)
    right_tree = _tree_from_key(right_key)
    return _sdted_uncached(left_tree, right_tree)


def _sdted_uncached(left_tree: NeighborhoodTree, right_tree: NeighborhoodTree) -> float:
    root_cost = _tree_root_relabel_cost(left_tree, right_tree, depth=0)

    left_children = list(left_tree.children)
    right_children = list(right_tree.children)

    child_cost = _minimum_child_assignment_cost(
        left_children=left_children,
        right_children=right_children,
        depth=1,
    )

    return root_cost + child_cost


def _sdted_at_depth(
    left_tree: NeighborhoodTree,
    right_tree: NeighborhoodTree,
    depth: int,
) -> float:
    root_cost = _tree_root_relabel_cost(left_tree, right_tree, depth)

    child_cost = _minimum_child_assignment_cost(
        left_children=list(left_tree.children),
        right_children=list(right_tree.children),
        depth=depth + 1,
    )

    return root_cost + child_cost


def _minimum_child_assignment_cost(
    left_children: List[NeighborhoodTree],
    right_children: List[NeighborhoodTree],
    depth: int,
) -> float:
    if not left_children and not right_children:
        return 0.0

    size = max(len(left_children), len(right_children))
    cost_matrix: List[List[float]] = []

    for i in range(size):
        row: List[float] = []
        for j in range(size):
            if i < len(left_children) and j < len(right_children):
                row.append(_sdted_at_depth(left_children[i], right_children[j], depth))
            elif i < len(left_children):
                row.append(_tree_insert_delete_cost(left_children[i], depth))
            elif j < len(right_children):
                row.append(_tree_insert_delete_cost(right_children[j], depth))
            else:
                row.append(0.0)
        cost_matrix.append(row)

    return _solve_min_assignment(cost_matrix)


def _depth_weight(depth: int) -> float:
    """
    Weight applied to tree edit costs at a given depth.

    This follows the paper idea that differences further away from the root
    should have less influence on the vertex assignment cost.
    """

    return DEPTH_DECAY ** depth


def _node_relabel_cost(left_label: str, right_label: str) -> float:
    if left_label == right_label:
        return 0.0

    return TREE_NODE_RELABEL_COST


def _edge_relabel_cost(
    left_edge_label: Optional[str],
    right_edge_label: Optional[str],
) -> float:
    if left_edge_label == right_edge_label:
        return 0.0

    return TREE_EDGE_RELABEL_COST


def _tree_root_relabel_cost(
    left_tree: NeighborhoodTree,
    right_tree: NeighborhoodTree,
    depth: int,
) -> float:
    cost = (
        _node_relabel_cost(left_tree.label, right_tree.label)
        + _edge_relabel_cost(
            left_tree.incoming_edge_label,
            right_tree.incoming_edge_label,
        )
    )

    return _depth_weight(depth) * cost

def _tree_insert_delete_cost(tree: NeighborhoodTree, depth: int) -> float:
    """
    Cost for inserting or deleting a whole subtree.

    The root of the subtree receives the depth-weighted node insertion/deletion
    cost. All descendants are included recursively with increased depth.
    """

    cost = _depth_weight(depth) * TREE_NODE_INSERT_DELETE_COST

    for child in tree.children:
        cost += _tree_insert_delete_cost(child, depth + 1)

    return cost

def _tree_key(tree: NeighborhoodTree) -> Tuple:
    if ENABLE_CANONICAL_TREE_ENCODING:
        return _canonical_tree_key(tree)

    return (
        tree.label,
        tree.incoming_edge_label or "",
        tuple(_tree_key(child) for child in tree.children),
    )


def _tree_from_key(key: Tuple) -> NeighborhoodTree:
    label, incoming_edge_label, child_keys = key
    return NeighborhoodTree(
        label=label,
        incoming_edge_label=incoming_edge_label,
        children=tuple(_tree_from_key(child_key) for child_key in child_keys),
    )


# ---------------------------------------------------------------------------
# Approximate GED
# ---------------------------------------------------------------------------

def approximate_graph_edit_distance(
    left_graph: ProcessGraph,
    right_graph: ProcessGraph,
) -> float:
    """
    Approximate graph edit distance using:
    - neighborhood-tree SDTED as vertex assignment cost
    - optimal assignment between vertices
    - edit-path cost derived from the assignment

    This follows the high-level BGM logic from the paper.
    """

    left_vertices = list(left_graph.labels.keys())
    right_vertices = list(right_graph.labels.keys())

    if not left_vertices and not right_vertices:
        return 0.0

    if not left_vertices:
        return (
            len(right_graph.labels) * VERTEX_INSERT_DELETE_COST
            + len(right_graph.edges) * EDGE_INSERT_DELETE_COST
        )

    if not right_vertices:
        return (
            len(left_graph.labels) * VERTEX_INSERT_DELETE_COST
            + len(left_graph.edges) * EDGE_INSERT_DELETE_COST
        )

    left_trees = {
        vertex: build_neighborhood_tree(left_graph, vertex)
        for vertex in left_vertices
    }

    right_trees = {
        vertex: build_neighborhood_tree(right_graph, vertex)
        for vertex in right_vertices
    }

    assignment = _compute_vertex_assignment(
        left_vertices=left_vertices,
        right_vertices=right_vertices,
        left_trees=left_trees,
        right_trees=right_trees,
    )

    return _derive_edit_path_cost(
        left_graph=left_graph,
        right_graph=right_graph,
        assignment=assignment,
    )


def _compute_vertex_assignment(
    left_vertices: List[VertexId],
    right_vertices: List[VertexId],
    left_trees: Dict[VertexId, NeighborhoodTree],
    right_trees: Dict[VertexId, NeighborhoodTree],
) -> Dict[Optional[VertexId], Optional[VertexId]]:
    """
    Return a mapping from left vertex to right vertex.
    None on one side means deletion/insertion.
    """

    n_left = len(left_vertices)
    n_right = len(right_vertices)
    size = max(n_left, n_right)

    cost_matrix: List[List[float]] = []

    for i in range(size):
        row: List[float] = []
        for j in range(size):
            if i < n_left and j < n_right:
                row.append(sdted(left_trees[left_vertices[i]], right_trees[right_vertices[j]]))
            elif i < n_left:
                row.append(VERTEX_INSERT_DELETE_COST)
            elif j < n_right:
                row.append(VERTEX_INSERT_DELETE_COST)
            else:
                row.append(0.0)
        cost_matrix.append(row)

    assignment_pairs = _solve_min_assignment_pairs(cost_matrix)

    assignment: Dict[Optional[VertexId], Optional[VertexId]] = {}

    for row_index, col_index in assignment_pairs:
        left_vertex: Optional[VertexId] = (
            left_vertices[row_index] if row_index < n_left else None
        )
        right_vertex: Optional[VertexId] = (
            right_vertices[col_index] if col_index < n_right else None
        )

        if left_vertex is not None or right_vertex is not None:
            assignment[left_vertex] = right_vertex

    return assignment


def _derive_edit_path_cost(
    left_graph: ProcessGraph,
    right_graph: ProcessGraph,
    assignment: Dict[Optional[VertexId], Optional[VertexId]],
) -> float:
    cost = 0.0

    left_to_right: Dict[VertexId, VertexId] = {}
    inserted_right_vertices: Set[VertexId] = set()

    for left_vertex, right_vertex in assignment.items():
        if left_vertex is not None and right_vertex is not None:
            left_to_right[left_vertex] = right_vertex

            if left_graph.labels[left_vertex] != right_graph.labels[right_vertex]:
                cost += VERTEX_RELABEL_COST

        elif left_vertex is not None and right_vertex is None:
            cost += VERTEX_INSERT_DELETE_COST

        elif left_vertex is None and right_vertex is not None:
            inserted_right_vertices.add(right_vertex)
            cost += VERTEX_INSERT_DELETE_COST

    mapped_right_vertices = set(left_to_right.values())
    all_right_vertices = set(right_graph.labels.keys())

    for right_vertex in all_right_vertices - mapped_right_vertices - inserted_right_vertices:
        cost += VERTEX_INSERT_DELETE_COST

    mapped_left_edges: Set[Edge] = set()
    right_edges_accounted_for: Set[Edge] = set()

    for source, target, label in left_graph.edges:
        if source not in left_to_right or target not in left_to_right:
            cost += EDGE_INSERT_DELETE_COST
            continue

        mapped_source = left_to_right[source]
        mapped_target = left_to_right[target]

        if label == "parallel":
            a, b = sorted((mapped_source, mapped_target))
            mapped_edge = (a, b, "parallel")
        else:
            mapped_edge = (mapped_source, mapped_target, "sequence")

        mapped_left_edges.add(mapped_edge)

        if mapped_edge in right_graph.edges:
            right_edges_accounted_for.add(mapped_edge)
            continue

        # Same endpoints but different edge label?
        alternative_edge = _find_edge_with_same_endpoints(
            edge=mapped_edge,
            edge_set=right_graph.edges,
        )

        if alternative_edge is not None:
            cost += EDGE_RELABEL_COST
            right_edges_accounted_for.add(alternative_edge)
        else:
            cost += EDGE_INSERT_DELETE_COST

    for edge in right_graph.edges:
        if edge not in right_edges_accounted_for and edge not in mapped_left_edges:
            cost += EDGE_INSERT_DELETE_COST

    return cost


def _find_edge_with_same_endpoints(edge: Edge, edge_set: Set[Edge]) -> Optional[Edge]:
    source, target, label = edge

    for candidate_source, candidate_target, candidate_label in edge_set:
        if label == "parallel":
            if candidate_label == "parallel" and {
                candidate_source,
                candidate_target,
            } == {source, target}:
                return candidate_source, candidate_target, candidate_label
        else:
            if candidate_source == source and candidate_target == target:
                return candidate_source, candidate_target, candidate_label

    return None


# ---------------------------------------------------------------------------
# Assignment solver
# ---------------------------------------------------------------------------

def _solve_min_assignment(cost_matrix: List[List[float]]) -> float:
    pairs = _solve_min_assignment_pairs(cost_matrix)
    return sum(cost_matrix[i][j] for i, j in pairs)


def _solve_min_assignment_pairs(cost_matrix: List[List[float]]) -> List[Tuple[int, int]]:
    """
    Solve a square linear assignment problem.

    Uses scipy if available. Falls back to a DP solver for small matrices.
    """

    size = len(cost_matrix)

    if size == 0:
        return []

    try:
        from scipy.optimize import linear_sum_assignment

        rows, cols = linear_sum_assignment(cost_matrix)
        return list(zip(rows.tolist(), cols.tolist()))
    except Exception:
        pass

    if size <= 14:
        return _solve_assignment_dp(cost_matrix)

    return _solve_assignment_greedy(cost_matrix)


def _solve_assignment_dp(cost_matrix: List[List[float]]) -> List[Tuple[int, int]]:
    size = len(cost_matrix)

    @lru_cache(maxsize=None)
    def dp(row: int, used_columns_mask: int) -> Tuple[float, Tuple[int, ...]]:
        if row == size:
            return 0.0, ()

        best_cost = float("inf")
        best_cols: Tuple[int, ...] = ()

        for col in range(size):
            if used_columns_mask & (1 << col):
                continue

            sub_cost, sub_cols = dp(row + 1, used_columns_mask | (1 << col))
            total_cost = cost_matrix[row][col] + sub_cost

            if total_cost < best_cost:
                best_cost = total_cost
                best_cols = (col,) + sub_cols

        return best_cost, best_cols

    _, cols = dp(0, 0)
    return [(row, col) for row, col in enumerate(cols)]


def _solve_assignment_greedy(cost_matrix: List[List[float]]) -> List[Tuple[int, int]]:
    """
    Fallback for large matrices when scipy is unavailable.

    This is not optimal, but prevents the backend from failing.
    In normal setups scipy should be available and this should not be used.
    """

    size = len(cost_matrix)
    remaining_cols = set(range(size))
    result: List[Tuple[int, int]] = []

    for row in range(size):
        best_col = min(remaining_cols, key=lambda col: cost_matrix[row][col])
        result.append((row, best_col))
        remaining_cols.remove(best_col)

    return result