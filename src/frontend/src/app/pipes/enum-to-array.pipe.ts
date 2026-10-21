import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'enumToArray',
})
export class EnumToArrayPipe implements PipeTransform {
  transform(enumObject: any): any {
    return Object.keys(enumObject).map((key) => ({
      key: key,
      value: enumObject[key],
    }));
  }
}
