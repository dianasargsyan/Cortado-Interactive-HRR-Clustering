import random
import time
from collections import Counter
from typing import Dict, List, Optional

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.stats import fisher_exact

from rotation_hrr.domain_knowledge import DomainKnowledge
from evaluation.edited import EditedLog
from rotation_hrr.tree_utils import tree_to_sequence
from rotation_hrr.tree_rewrites import groups_to_trees

from api.routes.variants.cop_kmeans import NoFeasibleCluster, cop_kmeans
from api.routes.variants.models import HRRClusteringParameters
from cache import cache

N_STARTS = 10
WHY_ACTIVITIES = 3
WHY_CANDIDATES = 10
SIGNIFICANCE = 0.05

_log = {"variants": None, "bids": None, "trees": None, "frequency": None}
_edited = {"key": None, "log": None, "activities": None, "presence": None}
_vectors = {"key": None, "vectors": None}


class HRRClusteringError(Exception):
    pass


def calculate_hrr_clusters(params: HRRClusteringParameters):
    start = time.perf_counter()
    bids, trees = get_trees()
    canonical = get_canonical_names(params.sameActivities)
    edited = get_edited_log(trees, canonical, params.ignoredActivities)
    vectors = get_vectors(edited, params.order, params.nesting)
    encoded = time.perf_counter()

    kept = np.flatnonzero(edited.has_vector())
    if len(kept) == 0:
        raise HRRClusteringError("No activity is left after the edits.")
    X = vectors if len(kept) == len(bids) else vectors[kept]
    kept_bids = [bids[i] for i in kept]

    k = params.nClusters
    n_distinct = len({repr(edited.trees[i]) for i in kept})
    if not 1 <= k <= n_distinct:
        raise HRRClusteringError(
            f"{n_distinct} different variants are left after the edits; "
            f"choose between 1 and {n_distinct} clusters."
        )

    row = {bid: n for n, bid in enumerate(kept_bids)}
    must_link, cannot_link, set_aside = to_rows(params, row)
    previous = [params.previousClusters.get(bid) for bid in kept_bids]
    labels, centers, from_scratch = run_cop_kmeans(
        X, k, must_link, cannot_link, previous, params.fromScratch, kept_bids
    )
    labels, centers = number_clusters(labels, centers, previous, from_scratch)
    clustered = time.perf_counter()

    similarities = X @ centers.T
    clusters = []
    for c in range(k):
        members = np.flatnonzero(labels == c)
        members = members[np.argsort(-similarities[members, c], kind="stable")]
        clusters.append([kept_bids[i] for i in members])
    info = describe_clusters(labels, k, kept)
    moved = None
    if not from_scratch:
        moved = sum(1 for p, l in zip(previous, labels) if p is not None and p != l)
    end = time.perf_counter()

    return {
        "clusters": clusters,
        "noActivities": [bids[i] for i in np.flatnonzero(~edited.has_vector())],
        "info": info,
        "canonical": canonical,
        "setAside": set_aside,
        "fromScratch": from_scratch,
        "moved": moved,
        "seconds": {
            "encode": round(encoded - start, 3),
            "cluster": round(clustered - encoded, 3),
            "describe": round(end - clustered, 3),
            "total": round(end - start, 3),
        },
    }


def get_trees():
    variants = list(cache.variants.items())
    cached = _log["variants"]
    if (
        cached is None
        or len(cached) != len(variants)
        or any(
            bid != old_bid or v[0] is not old[0]
            for (bid, v), (old_bid, old) in zip(variants, cached)
        )
    ):
        _log["variants"] = variants
        _log["bids"] = [bid for bid, _ in variants]
        _log["trees"] = groups_to_trees([v[0] for _, v in variants])
        _log["frequency"] = Counter(
            a for t in _log["trees"] for a in set(tree_to_sequence(t))
        )
        _edited["key"] = None
        _vectors["key"] = None
    return _log["bids"], _log["trees"]


def get_canonical_names(same_activities: List[List[str]]) -> Dict[str, str]:
    groups = []
    for group in same_activities:
        group = set(group)
        for other in [g for g in groups if g & group]:
            group |= other
            groups.remove(other)
        groups.append(group)

    canonical = {}
    for group in groups:
        name = max(sorted(group), key=lambda a: _log["frequency"][a])
        canonical.update({a: name for a in group if a != name})
    return canonical


def get_edited_log(trees, canonical: Dict[str, str], ignored: List[str]):
    key = (tuple(sorted(canonical.items())), tuple(sorted(set(ignored))))
    if _edited["key"] != key:
        equivalences = {}
        for alias, name in canonical.items():
            equivalences.setdefault(name, []).append(alias)
        edited = EditedLog(
            trees,
            DomainKnowledge(
                activity_equivalences=equivalences, ignored_activities=set(ignored)
            ),
        )
        activities = sorted(
            {a for t in edited.trees if t is not None for a in tree_to_sequence(t)}
        )
        column = {a: j for j, a in enumerate(activities)}
        presence = np.zeros((len(trees), len(activities)), dtype=bool)
        for i, t in enumerate(edited.trees):
            if t is not None:
                presence[i, [column[a] for a in set(tree_to_sequence(t))]] = True

        _edited.update(key=key, log=edited, activities=activities, presence=presence)
        _vectors["key"] = None
    return _edited["log"]


def get_vectors(edited, order: float, nesting: float):
    key = (order, nesting)
    if _vectors["key"] != key:
        vectors = edited.vectors(order, nesting)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors /= np.where(norms == 0, 1.0, norms)
        _vectors.update(key=key, vectors=vectors)
    return _vectors["vectors"]


def to_rows(params: HRRClusteringParameters, row: Dict[int, int]):
    set_aside = []

    def convert(pairs):
        converted = []
        for a, b in pairs:
            if a in row and b in row:
                converted.append((row[a], row[b]))
            else:
                set_aside.append([a, b])
        return converted

    return convert(params.mustLink), convert(params.cannotLink), set_aside


def run_cop_kmeans(X, k, must_link, cannot_link, previous, from_scratch, bids):
    failed = Counter()
    start = None if from_scratch else previous_centers(X, k, previous)
    if start is not None:
        try:
            labels, centers = cop_kmeans(X, k, must_link, cannot_link, start)
            return labels, centers, False
        except NoFeasibleCluster as error:
            failed[error.index] += 1

    best = None
    for seed in range(N_STARTS):
        try:
            labels, centers = cop_kmeans(
                X, k, must_link, cannot_link, rng=random.Random(seed)
            )
        except NoFeasibleCluster as error:
            failed[error.index] += 1
            continue
        similarities = (X @ centers.T)[np.arange(len(X)), labels]
        inertia = len(X) - 2 * similarities.sum() + (centers[labels] ** 2).sum()
        if best is None or inertia < best[0]:
            best = (inertia, labels, centers)

    if best is None:
        variant = bids[failed.most_common(1)[0][0]] + 1
        raise HRRClusteringError(
            f"The constraints cannot all be met with {k} clusters: variant #{variant} "
            f"cannot be placed in any cluster without breaking one. "
            f"Remove a constraint or raise the number of clusters."
        )
    return best[1], best[2], True


def previous_centers(X, k, previous: List[Optional[int]]):
    present = {p for p in previous if p is not None}
    if present != set(range(k)):
        return None
    labels = np.array([-1 if p is None else p for p in previous])
    return np.stack([X[labels == c].mean(axis=0) for c in range(k)])


def number_clusters(labels, centers, previous, from_scratch):
    k = len(centers)
    if from_scratch:
        sizes = np.bincount(labels, minlength=k)
        order = np.argsort(-sizes, kind="stable")
    else:
        overlap = np.zeros((k, k))
        for p, l in zip(previous, labels):
            if p is not None:
                overlap[p, l] += 1
        _, order = linear_sum_assignment(-overlap)
    new_number = np.empty(k, dtype=int)
    new_number[order] = np.arange(k)
    return new_number[labels], centers[order]


def describe_clusters(labels, k, kept):
    activities = _edited["activities"]
    presence = _edited["presence"][kept].astype(float)
    members = np.zeros((k, len(labels)))
    members[labels, np.arange(len(labels))] = 1.0
    here = (members @ presence).astype(int)
    total = presence.sum(axis=0).astype(int)
    sizes = members.sum(axis=1).astype(int)

    info = []
    for c in range(k):
        size, rest = int(sizes[c]), int(len(labels) - sizes[c])
        elsewhere = total - here[c]
        counts = {
            activities[j]: [int(here[c, j]), int(elsewhere[j])]
            for j in np.flatnonzero(here[c] + elsewhere)
        }
        why = []
        if rest > 0:
            difference = here[c] / size - elsewhere / rest
            more = [
                j for j in np.argsort(-difference, kind="stable") if difference[j] > 0
            ]
            less = [
                j for j in np.argsort(difference, kind="stable") if difference[j] < 0
            ]
            for j in (more + less)[:WHY_CANDIDATES]:
                table = [
                    [here[c, j], size - here[c, j]],
                    [elsewhere[j], rest - elsewhere[j]],
                ]
                if fisher_exact(table)[1] < SIGNIFICANCE:
                    why.append(
                        {
                            "activity": activities[j],
                            "here": int(here[c, j]),
                            "elsewhere": int(elsewhere[j]),
                            "moreCommonHere": bool(difference[j] > 0),
                        }
                    )
                if len(why) == WHY_ACTIVITIES:
                    break
        info.append({"size": size, "rest": rest, "why": why, "counts": counts})
    return info
