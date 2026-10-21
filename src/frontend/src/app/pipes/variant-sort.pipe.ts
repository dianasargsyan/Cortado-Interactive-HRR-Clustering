import { Pipe, PipeTransform } from '@angular/core';
import { Variant } from '../objects/Variants/variant';
import { VariantSorter } from '../objects/Variants/variant-sorter';

@Pipe({
  name: 'variantSort',
})
export class VariantSortPipe implements PipeTransform {
  transform(input: unknown, isAscending: boolean, feature: string): unknown {
    // if we dont get an array just return back the input
    if (!Array.isArray(input)) {
      return input;
    }

    // if any of the params is not defined we just return the input
    if (isAscending === undefined || feature === undefined) {
      return input;
    }

    // apply search
    let result = this.search(input, isAscending, feature);
    return result;
  }

  search(input: any[], isAscending: boolean, feature: string) {
    const variants = input as Variant[];
    return VariantSorter.sort(variants, feature, isAscending);
  }
}
