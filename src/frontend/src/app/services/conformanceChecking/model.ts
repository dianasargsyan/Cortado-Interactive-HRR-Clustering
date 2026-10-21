import { ProcessTree } from 'src/app/objects/ProcessTree/ProcessTree';

export class ConformanceCheckingResult {
  constructor(
    public id: string,
    public type: number,
    public isTimeout: boolean,
    public cost: number,
    public deviations: number,
    public alignment: string,
    public processTree: ProcessTree
  ) {}
}
export interface treeConformanceResult {
  merged_conformance_tree: ProcessTree;
  variants_tree_conformance: ProcessTree[];
}
