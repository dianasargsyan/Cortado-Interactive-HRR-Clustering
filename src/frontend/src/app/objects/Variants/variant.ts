import { Transform, TransformationType, Type } from 'class-transformer';
import { ProcessTree } from '../ProcessTree/ProcessTree';
import { InfixType } from './infix_selection';
import { VariantElement, deserialize } from './variant_element';
import { IVariant } from './variant_interface';

export interface FragmentStatistics {
  totalOccurrences: number;
  traceOccurrences: number;
  variantOccurrences: number;
}

export class Variant implements IVariant {
  id: string;
  bid: number; //Positive Numbers indicate Log Variants, Negative Number User Variants
  count: number;
  length: number;
  number_of_activities: number;
  @Type(() => VariantElement)
  @Transform(({ value, key, obj, type }) => {
    if (type === TransformationType.PLAIN_TO_CLASS && value)
      return deserialize(value);
    if (type === TransformationType.CLASS_TO_PLAIN && value)
      return (<VariantElement>value).serialize();
    return value;
  })
  variant: VariantElement;
  isSelected: boolean;
  isDisplayed: boolean;
  isAddedFittingVariant: boolean;
  percentage: number;
  calculationInProgress: boolean | undefined;
  userDefined: boolean;
  @Type(() => VariantElement)
  @Transform(({ value, key, obj, type }) => {
    if (type === TransformationType.PLAIN_TO_CLASS && value)
      return deserialize(value);
    if (type === TransformationType.CLASS_TO_PLAIN && value)
      return (<VariantElement>value).serialize();
    return value;
  })
  alignment: VariantElement | undefined;
  deviations: number | undefined;
  isTimeouted: boolean;
  isConformanceOutdated: boolean;
  @Type(() => ProcessTree)
  usedTreeForConformanceChecking: ProcessTree;
  nSubVariants: number;
  infixType: InfixType;
  fragmentStatistics: FragmentStatistics;
  collapsedVariantId: string;
  clusterId: number; // id of the cluster to which the variant belongs to, default value (no clustering) = -1

  constructor(
    count: number,
    variant: VariantElement,
    isSelected: boolean,
    isDisplayed: boolean,
    isAddedFittingVariant: boolean,
    percentage: number,
    calculationInProgress: boolean | undefined,
    userDefined: boolean,
    isTimeouted: boolean,
    isConformanceOutdated: boolean,
    nSubVariants: number,
    infixType: InfixType = InfixType.NOT_AN_INFIX,
    clusterId: number = -1
  ) {
    this.count = count;
    this.variant = variant;
    this.isSelected = isSelected;
    this.isDisplayed = isDisplayed;
    this.isAddedFittingVariant = isAddedFittingVariant;
    this.percentage = percentage;
    this.calculationInProgress = calculationInProgress;
    this.userDefined = userDefined;
    this.isTimeouted = isTimeouted;
    this.isConformanceOutdated = isConformanceOutdated;
    this.nSubVariants = nSubVariants;
    this.infixType = infixType;
    this.clusterId = clusterId;
  }

  public equals(variant: Variant): boolean {
    let equals = false;
    if (
      this.variant.getElements().length !== variant.variant.getElements().length
    ) {
      equals = false;
    } else {
      equals = this.variant.getElements().every((value, index) => {
        return value.equals(variant.variant.getElements()[index]);
      });
    }
    if (equals) {
      // check infix
      if (variant.infixType !== this.infixType) {
        equals = false;
      }
    }
    return equals;
  }
}
