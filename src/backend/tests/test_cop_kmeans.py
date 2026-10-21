import random
import unittest
from unittest import mock

import numpy as np

from api.routes.variants.cop_kmeans import NoFeasibleCluster, cop_kmeans

try:
    import copkmeans.cop_kmeans as reference
except ImportError:
    reference = None


def random_problem(seed, n_constraints=6):
    rnd = np.random.default_rng(seed)
    n = int(rnd.integers(20, 60))
    dim = int(rnd.integers(2, 10))
    k = int(rnd.integers(2, 6))
    dataset = rnd.normal(size=(n, dim))
    groups = rnd.integers(0, k, size=n)
    ml, cl = [], []
    while len(ml) + len(cl) < n_constraints:
        i, j = (int(x) for x in rnd.choice(n, size=2, replace=False))
        if groups[i] == groups[j]:
            ml.append((i, j))
        else:
            cl.append((i, j))
    return dataset, k, ml, cl


def satisfies(clusters, ml, cl):
    return all(clusters[i] == clusters[j] for i, j in ml) and all(
        clusters[i] != clusters[j] for i, j in cl
    )


@unittest.skipIf(reference is None, "COP-Kmeans by Babaki is not installed")
class CopKmeansReferenceTest(unittest.TestCase):
    def assert_same_as_reference(self, dataset, k, ml, cl, initialization, seed):
        random.seed(seed)
        expected, expected_centers = reference.cop_kmeans(
            dataset.tolist(), k, ml, cl, initialization=initialization
        )
        try:
            clusters, centers = cop_kmeans(
                dataset, k, ml, cl, initialization, rng=random.Random(seed)
            )
        except NoFeasibleCluster:
            self.assertIsNone(expected)
            return
        self.assertIsNotNone(expected)
        self.assertEqual(clusters.tolist(), list(expected))
        np.testing.assert_allclose(centers, np.array(expected_centers), atol=1e-9)

    def test_same_clusters_as_reference_with_kmeans_plus_plus(self):
        for seed in range(60):
            dataset, k, ml, cl = random_problem(seed)
            self.assert_same_as_reference(dataset, k, ml, cl, "kmpp", seed)

    def test_same_clusters_as_reference_with_random_initialization(self):
        for seed in range(60):
            dataset, k, ml, cl = random_problem(seed)
            self.assert_same_as_reference(dataset, k, ml, cl, "random", seed)

    def test_same_clusters_as_reference_without_constraints(self):
        for seed in range(30):
            dataset, k, _, _ = random_problem(seed)
            self.assert_same_as_reference(dataset, k, [], [], "kmpp", seed)

    def assert_same_as_reference_from(self, dataset, k, ml, cl, start):
        with mock.patch.object(
            reference, "initialize_centers", return_value=start.tolist()
        ):
            expected, _ = reference.cop_kmeans(dataset.tolist(), k, ml, cl)
        try:
            clusters, _ = cop_kmeans(dataset, k, ml, cl, start)
        except NoFeasibleCluster:
            self.assertIsNone(expected)
            return
        self.assertEqual(clusters.tolist(), list(expected))

    def test_same_clusters_as_reference_from_given_centers(self):
        for seed in range(30):
            dataset, k, ml, cl = random_problem(seed)
            start = np.random.default_rng(seed).normal(size=(k, dataset.shape[1]))
            self.assert_same_as_reference_from(dataset, k, ml, cl, start)

    def test_same_clusters_as_reference_when_a_cluster_empties(self):
        for seed in range(30):
            dataset, k, ml, cl = random_problem(seed, n_constraints=10)
            start = np.random.default_rng(seed).normal(size=(k, dataset.shape[1]))
            start[-1] += 100.0
            self.assert_same_as_reference_from(dataset, k, ml, cl, start)


class CopKmeansTest(unittest.TestCase):
    def test_constraints_hold(self):
        for seed in range(30):
            dataset, k, ml, cl = random_problem(seed, n_constraints=10)
            try:
                clusters, _ = cop_kmeans(dataset, k, ml, cl, rng=random.Random(seed))
            except NoFeasibleCluster:
                continue
            self.assertTrue(satisfies(clusters, ml, cl))

    def test_names_the_point_without_an_allowed_cluster(self):
        dataset = np.array([[0.0, 0.0], [0.1, 0.0], [5.0, 5.0], [5.1, 5.0]])
        cl = [(0, 1), (1, 2), (0, 2)]
        with self.assertRaises(NoFeasibleCluster) as raised:
            cop_kmeans(dataset, 2, [], cl, rng=random.Random(0))
        self.assertIn(raised.exception.index, (0, 1, 2))

    def test_inconsistent_constraints_are_refused(self):
        dataset = np.zeros((3, 2))
        with self.assertRaises(Exception):
            cop_kmeans(dataset, 2, [(0, 1), (1, 2)], [(0, 2)])

    def test_starting_from_converged_centers_changes_nothing(self):
        dataset, k, ml, cl = random_problem(3)
        clusters, centers = cop_kmeans(dataset, k, ml, cl, rng=random.Random(3))
        again, _ = cop_kmeans(dataset, k, ml, cl, centers)
        self.assertEqual(again.tolist(), clusters.tolist())


if __name__ == "__main__":
    unittest.main()
