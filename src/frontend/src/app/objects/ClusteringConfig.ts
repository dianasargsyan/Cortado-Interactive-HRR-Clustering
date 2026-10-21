import { ClusteringAlgorithm } from './ClusteringAlgorithm';

export interface ClusteringConstraints {
  mustLink: [number, number][];
  cannotLink: [number, number][];
}

export type ClusteringConfig = {
  algorithm: ClusteringAlgorithm;
  params: any;
  constraints?: ClusteringConstraints;
};

