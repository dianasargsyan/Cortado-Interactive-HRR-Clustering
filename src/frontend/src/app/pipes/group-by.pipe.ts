import { Pipe, PipeTransform } from '@angular/core';
import { extractDeepPropertyByMapKey, isFunction } from '../utils/util';

@Pipe({ name: 'groupBy' })
export class GroupByPipe implements PipeTransform {
  transform(input: any, discriminator: any = [], delimiter: string = '|'): any {
    if (!Array.isArray(input)) {
      return input;
    }

    let result = this.groupBy(input, discriminator, delimiter);
    return result;
  }

  private groupBy(list: any[], discriminator: any, delimiter: string) {
    return list.reduce((acc: any, payload: string) => {
      const key = this.extractKeyByDiscriminator(
        discriminator,
        payload,
        delimiter
      );

      acc[key] = Array.isArray(acc[key])
        ? acc[key].concat([payload])
        : [payload];

      return acc;
    }, {});
  }

  private extractKeyByDiscriminator(
    discriminator: any,
    payload: string,
    delimiter: string
  ) {
    if (isFunction(discriminator)) {
      return (<Function>discriminator)(payload);
    }

    if (Array.isArray(discriminator)) {
      return discriminator
        .map((k) => extractDeepPropertyByMapKey(payload, k))
        .join(delimiter);
    }

    return extractDeepPropertyByMapKey(payload, <string>discriminator);
  }
}
