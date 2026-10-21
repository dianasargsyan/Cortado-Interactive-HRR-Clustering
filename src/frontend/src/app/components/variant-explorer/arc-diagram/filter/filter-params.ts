import { ActivitiesSelection, MultiRangeFilter } from './filter.component';

export class FilterParams {
  lengthRange: MultiRangeFilter;
  sizeRange: MultiRangeFilter;
  distanceRange: MultiRangeFilter;
  activitiesSelection: ActivitiesSelection;
  constructor() {
    this.distanceRange = {
      low: 0,
      high: 20,
      options: {
        step: 1,
        floor: 0,
        ceil: 2,
        showTicks: true,
      },
    };
    this.sizeRange = {
      ...this.distanceRange,
      low: 1,
      options: {
        ...this.distanceRange.options,
        floor: 1,
      },
    };

    this.lengthRange = {
      ...this.sizeRange,
    };

    this.activitiesSelection = {
      selectedItems: new Set<string>(),
      activitiesList: new Set<string>(),
    };
  }
}
