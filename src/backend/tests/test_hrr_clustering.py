import unittest

import numpy as np
from cortado_core.models.infix_type import InfixType
from cortado_core.utils.split_graph import Group

from api.routes.variants.hrr_clustering import (
    HRRClusteringError,
    calculate_hrr_clusters,
    get_canonical_names,
    get_edited_log,
    get_trees,
    get_vectors,
)
from api.routes.variants.models import HRRClusteringParameters, VariantInformation
from cache import cache

LOG = [
    ("a", "b", "c", "d"),
    ("a", "c", "b", "d"),
    ("a", ("b", "c"), "d"),
    ("a", "b", "c", "d", "d"),
    ("e", "f", "g"),
    ("e", "g", "f"),
    ("e", ("f", "g")),
    ("e", "f", "g", "g"),
    ("a", "x", "b", "c", "d"),
    ("e", "x", "f", "g"),
    ("z",),
    ("a", "b", "y"),
]


def variant(steps):
    children = []
    for step in steps:
        if isinstance(step, tuple):
            children.append({"parallel": [{"leaf": [a]} for a in step]})
        else:
            children.append({"leaf": [step]})
    return Group.deserialize({"follows": children})


def contains(bid, activity):
    return any(
        activity in step if isinstance(step, tuple) else activity == step
        for step in LOG[bid]
    )


class HRRClusteringTest(unittest.TestCase):
    def setUp(self):
        info = VariantInformation(InfixType.NOT_AN_INFIX, False)
        cache.variants = {
            bid: (variant(steps), [], [], info) for bid, steps in enumerate(LOG)
        }

    def cluster(self, **params):
        return calculate_hrr_clusters(
            HRRClusteringParameters(**{"nClusters": 2, **params})
        )

    def test_every_variant_is_in_one_of_k_clusters(self):
        result = self.cluster(nClusters=3)
        self.assertEqual(len(result["clusters"]), 3)
        bids = sorted(bid for members in result["clusters"] for bid in members)
        self.assertEqual(bids, list(range(len(LOG))))

    def test_constraints_hold(self):
        result = self.cluster(nClusters=3, mustLink=[[0, 4]], cannotLink=[[0, 1]])
        cluster_of = {
            bid: c for c, members in enumerate(result["clusters"]) for bid in members
        }
        self.assertEqual(cluster_of[0], cluster_of[4])
        self.assertNotEqual(cluster_of[0], cluster_of[1])

    def test_reclustering_from_its_own_clusters_moves_nothing(self):
        first = self.cluster(nClusters=3)
        previous = {
            bid: c for c, members in enumerate(first["clusters"]) for bid in members
        }
        again = self.cluster(nClusters=3, previousClusters=previous)
        self.assertFalse(again["fromScratch"])
        self.assertEqual(again["moved"], 0)
        self.assertEqual(again["clusters"], first["clusters"])

    def test_removing_an_edit_restores_every_vector(self):
        _, trees = get_trees()
        before = get_vectors(get_edited_log(trees, {}, []), 1.0, 1.0).copy()
        edited = get_vectors(get_edited_log(trees, {}, ["x"]), 1.0, 1.0).copy()
        after = get_vectors(get_edited_log(trees, {}, []), 1.0, 1.0)
        np.testing.assert_array_equal(after, before)
        for bid in range(len(LOG)):
            if not contains(bid, "x"):
                np.testing.assert_array_equal(edited[bid], before[bid])

    def test_variant_without_activities_is_set_apart(self):
        result = self.cluster(ignoredActivities=["z"], mustLink=[[10, 0]])
        self.assertEqual(result["noActivities"], [10])
        self.assertEqual(result["setAside"], [[10, 0]])
        self.assertNotIn(10, [bid for members in result["clusters"] for bid in members])

    def test_constraints_that_cannot_be_met_name_a_variant(self):
        with self.assertRaises(HRRClusteringError) as raised:
            self.cluster(cannotLink=[[0, 4], [4, 10], [0, 10]])
        self.assertIn("variant #", str(raised.exception))

    def test_more_clusters_than_variants_left_are_refused(self):
        with self.assertRaises(HRRClusteringError):
            self.cluster(nClusters=len(LOG) + 1)

    def test_same_activities_sharing_an_activity_are_joined(self):
        get_trees()
        canonical = get_canonical_names([["a", "e"], ["e", "x"]])
        names = {canonical.get(a, a) for a in ("a", "e", "x")}
        self.assertEqual(len(names), 1)
        self.assertNotIn(names.pop(), canonical)

    def test_why_names_an_activity_that_sets_a_cluster_apart(self):
        result = self.cluster()
        c = next(c for c, members in enumerate(result["clusters"]) if 0 in members)
        why = {w["activity"] for w in result["info"][c]["why"] if w["moreCommonHere"]}
        self.assertTrue(why & {"a", "b", "c", "d"})


if __name__ == "__main__":
    unittest.main()
