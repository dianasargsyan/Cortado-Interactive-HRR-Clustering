import { Pipe, PipeTransform } from '@angular/core';
import { ActivityField } from 'src/app/components/activity-overview/activity-overview.component';

@Pipe({
  name: 'tableSorting',
})
export class TableSortingPipe implements PipeTransform {
  transform(array: any, sortKey: string, ascending: boolean): any {
    if (!Array.isArray(array)) {
      throw new Error('Input Data is not a sortable Array');
    }

    // Reverse behavior for string keys
    if (
      sortKey == 'activityName' ||
      sortKey == 'case_id' ||
      sortKey == 'earliest_time' ||
      sortKey == 'latest_time' ||
      sortKey == 'total_duration'
    ) {
      ascending = !ascending;
    }

    array.sort((a: ActivityField, b: ActivityField) => {
      if (a[sortKey] == undefined && a[sortKey] == undefined) {
        if (a['property'][sortKey] < b['property'][sortKey]) {
          return ascending ? -1 : 1;
        } else if (a['property'][sortKey] > b['property'][sortKey]) {
          return ascending ? 1 : -1;
        } else {
          return 0;
        }
      } else {
        if (a[sortKey] < b[sortKey]) {
          return ascending ? -1 : 1;
        } else if (a[sortKey] > b[sortKey]) {
          return ascending ? 1 : -1;
        } else {
          return 0;
        }
      }
    });

    return array;
  }
}
