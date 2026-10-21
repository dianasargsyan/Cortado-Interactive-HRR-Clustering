import { KeyValue } from '@angular/common';
import * as objectHash from 'object-hash';
import { OperatorFunction } from 'rxjs';
import { map } from 'rxjs/operators';
import { Variant } from '../objects/Variants/variant';
import { deserialize } from '../objects/Variants/variant_element';

export function originalOrder(
  a: KeyValue<number, string>,
  b: KeyValue<number, string>
): number {
  return 0;
}

export function transformVariants(properties) {
  properties['variants'].forEach((variant, i) => {
    variant['id'] = objectHash(variant['variant']);
    variant['variant'] = deserialize(variant.variant);
  });
  return properties;
}

export function transformVariantList(variants: Variant[]) {
  variants.forEach((variant, i) => {
    variant['id'] = objectHash(variant['variant']);
    variant['variant'] = deserialize(variant.variant);
  });
  return variants;
}

export function mapVariantsList(): OperatorFunction<any, any> {
  return map((result) => {
    return transformVariantList(result);
  });
}

export function mapVariants(): OperatorFunction<any, any> {
  return map((result) => {
    return transformVariants(result);
  });
}

export function blobToBase64(blob) {
  return new Promise((resolve, _) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.readAsDataURL(blob);
  });
}

export function isUndefined(value: any) {
  return typeof value === 'undefined';
}

export function extractDeepPropertyByMapKey(obj: any, map: string): any {
  const keys = map.split('.');
  const head = keys.shift();

  return keys.reduce((prop: any, key: string) => {
    return !isUndefined(prop) && prop != null && !isUndefined(prop[key])
      ? prop[key]
      : undefined;
  }, obj[head || '']);
}

export function isFunction(value: any) {
  return typeof value === 'function';
}
