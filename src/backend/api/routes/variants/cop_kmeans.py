# Adapted from COP-Kmeans 1.5 by Behrouz Babaki
# (https://github.com/Behrouz-Babaki/COP-Kmeans, commit 2cd2aab, doi:10.5281/zenodo.831850),
# an implementation of COP-KMeans (Wagstaff et al., 2001). Changes: numpy for the arithmetic,
# initialization can be an array of starting centers, random draws can come from a given
# random.Random, and NoFeasibleCluster names the point that has no allowed cluster.
#
# The MIT License (MIT)
#
# Copyright (c) 2015
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import random

import numpy as np


class NoFeasibleCluster(Exception):
    def __init__(self, index: int):
        super().__init__(f"no cluster satisfies the constraints of point {index}")
        self.index = index


def cop_kmeans(
    dataset,
    k,
    ml=[],
    cl=[],
    initialization="kmpp",
    max_iter=300,
    tol=1e-4,
    rng=random,
):
    dataset = np.asarray(dataset, dtype=float)
    norms = np.einsum("ij,ij->i", dataset, dataset)
    ml, cl = transitive_closure(ml, cl, len(dataset))
    ml_info = get_ml_info(ml, dataset)
    tol = tolerance(tol, dataset)

    centers = initialize_centers(dataset, k, initialization, rng, norms)
    constrained = [i for i in range(len(dataset)) if ml[i] or cl[i]]

    for _ in range(max_iter):
        distances = squared_distances(dataset, centers, norms)
        clusters_ = np.argmin(distances, axis=1)
        clusters_[constrained] = -1
        for i in constrained:
            if clusters_[i] != -1:
                continue
            for index in np.argsort(distances[i], kind="stable"):
                if not violate_constraints(i, index, clusters_, ml, cl):
                    clusters_[i] = index
                    for j in ml[i]:
                        clusters_[j] = index
                    break
            else:
                raise NoFeasibleCluster(i)

        clusters_, centers_ = compute_centers(clusters_, dataset, k, ml_info, norms)
        shift = ((centers - centers_) ** 2).sum()
        if shift <= tol:
            break

        centers = centers_

    return clusters_, centers_


def squared_distances(dataset, centers, norms):
    distances = (
        norms[:, None] - 2 * dataset @ centers.T + (centers**2).sum(axis=1)[None, :]
    )
    return np.maximum(distances, 0.0)


# taken from scikit-learn (https://goo.gl/1RYPP5)
def tolerance(tol, dataset):
    return tol * dataset.var(axis=0).mean()


def initialize_centers(dataset, k, method, rng, norms):
    if not isinstance(method, str):
        return np.array(method, dtype=float)

    if method == "random":
        ids = list(range(len(dataset)))
        rng.shuffle(ids)
        return dataset[ids[:k]].copy()

    elif method == "kmpp":
        chances = np.ones(len(dataset))
        closest = np.full(len(dataset), np.inf)
        centers = []

        for _ in range(k):
            total = np.cumsum(chances)[-1]
            if total == 0:
                raise ValueError("fewer distinct points than clusters")
            chances = chances / total
            r = rng.random()
            reached = np.flatnonzero(np.cumsum(chances) >= r)
            index = reached[0] if len(reached) else len(dataset) - 1
            centers.append(dataset[index])

            distances = squared_distances(dataset, dataset[index][None, :], norms)
            closest = np.minimum(closest, distances[:, 0])
            chances = closest

        return np.array(centers)


def violate_constraints(data_index, cluster_index, clusters, ml, cl):
    for i in ml[data_index]:
        if clusters[i] != -1 and clusters[i] != cluster_index:
            return True

    for i in cl[data_index]:
        if clusters[i] == cluster_index:
            return True

    return False


def compute_centers(clusters, dataset, k, ml_info, norms):
    cluster_ids = set(clusters.tolist())
    k_new = len(cluster_ids)
    id_map = dict(zip(cluster_ids, range(k_new)))
    clusters = np.array([id_map[x] for x in clusters.tolist()])

    members = np.zeros((k_new, len(dataset)))
    members[clusters, np.arange(len(dataset))] = 1.0
    counts = members.sum(axis=1)
    centers = np.zeros((k, dataset.shape[1]))
    centers[:k_new] = (members @ dataset) / counts[:, None]

    if k_new < k:
        ml_groups, ml_scores, group_of = ml_info
        point_scores = squared_distances(dataset, centers[:k_new], norms)[
            np.arange(len(dataset)), clusters
        ]
        current_scores = np.bincount(
            group_of, weights=point_scores, minlength=len(ml_groups)
        )
        group_ids = np.argsort(-(current_scores - ml_scores), kind="stable")

        for j in range(k - k_new):
            gid = group_ids[j]
            cid = k_new + j
            centers[cid] = dataset[ml_groups[gid]].mean(axis=0)
            for i in ml_groups[gid]:
                clusters[i] = cid

    return clusters, centers


def get_ml_info(ml, dataset):
    flags = [True] * len(dataset)
    groups = []
    group_of = np.zeros(len(dataset), dtype=int)
    for i in range(len(dataset)):
        if not flags[i]:
            continue
        group = list(ml[i] | {i})
        for j in group:
            flags[j] = False
            group_of[j] = len(groups)
        groups.append(group)

    scores = np.zeros(len(groups))
    for j, group in enumerate(groups):
        if len(group) > 1:
            members = dataset[group]
            scores[j] = ((members - members.mean(axis=0)) ** 2).sum()

    return groups, scores, group_of


def transitive_closure(ml, cl, n):
    ml_graph = dict()
    cl_graph = dict()
    for i in range(n):
        ml_graph[i] = set()
        cl_graph[i] = set()

    def add_both(d, i, j):
        d[i].add(j)
        d[j].add(i)

    for i, j in ml:
        add_both(ml_graph, i, j)

    def dfs(i, graph, visited, component):
        visited[i] = True
        for j in graph[i]:
            if not visited[j]:
                dfs(j, graph, visited, component)
        component.append(i)

    visited = [False] * n
    for i in range(n):
        if not visited[i]:
            component = []
            dfs(i, ml_graph, visited, component)
            for x1 in component:
                for x2 in component:
                    if x1 != x2:
                        ml_graph[x1].add(x2)
    for i, j in cl:
        add_both(cl_graph, i, j)
        for y in ml_graph[j]:
            add_both(cl_graph, i, y)
        for x in ml_graph[i]:
            add_both(cl_graph, x, j)
            for y in ml_graph[j]:
                add_both(cl_graph, x, y)

    for i in ml_graph:
        for j in ml_graph[i]:
            if j != i and j in cl_graph[i]:
                raise Exception("inconsistent constraints between %d and %d" % (i, j))

    return ml_graph, cl_graph
