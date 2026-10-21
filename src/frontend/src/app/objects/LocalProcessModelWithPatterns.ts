import { ProcessTree } from './ProcessTree/ProcessTree';
import { VariantElement } from './Variants/variant_element';

export class LocalProcessModelWithPatterns {
  lpm: ProcessTree;
  patterns: VariantElement[];

  constructor(lpm, patterns) {
    this.lpm = lpm;
    this.patterns = patterns;
  }
}
