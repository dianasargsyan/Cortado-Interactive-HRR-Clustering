import { VariantSelectionMethod } from '../VariantSelectionMethod';

export type LogExportConfig = {
  variantSelectionMethod: VariantSelectionMethod;
  includeTraceFragments: boolean;
  includeUserCreatedVariants: boolean;
  sequentializeVariants: boolean;
  exportAsIntervalLog: boolean;
  includeOriginalLogInfo: boolean;
};
