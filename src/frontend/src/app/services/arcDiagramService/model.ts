import { Pair } from '../../directives/arc-diagram/data';

export class ArcDiagramComputationResult {
  constructor(
    public pairs: PairsPerBid,
    public maximal_values: { size: number; length: number }
  ) {}
}

export interface PairsPerBid {
  [bid: string]: Pair[];
}
