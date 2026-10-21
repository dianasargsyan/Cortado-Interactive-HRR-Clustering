import { Type } from 'class-transformer';
import { Variant } from './Variants/variant';

export enum LogModificationType {
  ACTIVITY_RENAMING,
  ACTIVITY_DELETION,
  VARIANT_DELETION,
  USER_DEFINED_VARIANT_ADDITION,
  USER_DEFINED_INFIX_ADDITION,
}

export abstract class LogModification {
  public abstract readonly type: LogModificationType;
  constructor() {}
}

export class ActivityDeletion extends LogModification {
  public readonly type = LogModificationType.ACTIVITY_DELETION;

  constructor(public activityName: string) {
    super();
  }
}

export class ActivityRenaming extends LogModification {
  public readonly type = LogModificationType.ACTIVITY_RENAMING;

  constructor(public activityName: string, public newActivityName: string) {
    super();
  }
}

export class VariantsDeletion extends LogModification {
  public readonly type = LogModificationType.VARIANT_DELETION;

  constructor(public variantsBids: number[]) {
    super();
  }
}

export class UserDefinedVariantAddition extends LogModification {
  public readonly type = LogModificationType.USER_DEFINED_VARIANT_ADDITION;

  @Type(() => Variant)
  public variant: Variant;

  constructor(variant: Variant) {
    super();
    this.variant = variant;
  }
}

export class UserDefinedInfixAddition extends LogModification {
  public readonly type = LogModificationType.USER_DEFINED_INFIX_ADDITION;

  @Type(() => Variant)
  public infix: Variant;

  constructor(infix: Variant) {
    super();
    this.infix = infix;
  }
}
