import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FilterParams } from './filter-params';
import { Options } from 'ngx-slider-v2';
import { takeUntil } from 'rxjs/operators';
import { LogService } from '../../../../services/logService/log.service';
import { Subject } from 'rxjs';
import { ColorMapService } from '../../../../services/colorMapService/color-map.service';
import { computeActivityColor } from '../../../../utils/render-utils';
import { LeafNode } from '../../../../objects/Variants/variant_element';

const SELECT_ALL_TEXT = 'Select All';
const DESELECT_ALL_TEXT = 'Deselect All';

@Component({
  selector: 'app-arc-diagram-filter-form',
  templateUrl: './filter.component.html',
  styleUrls: ['./filter.component.scss'],
})
export class ArcDiagramFilterComponent implements OnInit {
  constructor(
    private logService: LogService,
    private colorMapService: ColorMapService
  ) {}

  activityDummyVariants: Map<string, LeafNode> = new Map<string, LeafNode>();

  colorMap: Map<string, string> = new Map<string, string>();
  computeActivityColor = computeActivityColor.bind(this);

  activitiesSelectionBtnText: string = DESELECT_ALL_TEXT;

  @Output()
  filterArcDiagrams = new EventEmitter<FilterParams>();
  @Output()
  newActivitiesLoaded = new EventEmitter<Set<string>>();

  @Input() set arcsMaxValues(values: MaxValues) {
    for (const [type, value] of Object.entries(values)) {
      this.setRangeFilters(type, value);
    }
  }
  @Input()
  filtering: boolean;

  private _destroy$ = new Subject();

  model: FilterParams = new FilterParams();

  ngOnInit() {
    this.logService.activitiesInEventLog$
      .pipe(takeUntil(this._destroy$))
      .subscribe((activities) => {
        this.model.activitiesSelection.activitiesList = new Set();
        Object.entries(activities).forEach(([activity], idx: number) => {
          this.model.activitiesSelection.activitiesList.add(activity);
          this.setActivityDummyVariants(activity);
        });
        this.model.activitiesSelection.selectedItems = new Set(
          this.model.activitiesSelection.activitiesList
        );
        this.newActivitiesLoaded.emit(
          this.model.activitiesSelection.selectedItems
        );
      });
    this.colorMapService.colorMap$
      .pipe(takeUntil(this._destroy$))
      .subscribe((map) => {
        this.colorMap = map;
      });
  }
  createNewOptionsObject(rangeFilter: Options, value: number) {
    const newOptions: Options = Object.assign({}, rangeFilter);
    newOptions.ceil = value + 1;
    return newOptions;
  }

  setRangeFilters(type: string, value: number) {
    if (!this.filtering) {
      this.model[`${type}Range`].high = value + 1;
    }
    this.model[`${type}Range`].options = this.createNewOptionsObject(
      this.model[`${type}Range`].options,
      value
    );
  }
  onSubmit() {
    this.filterArcDiagrams.emit(this.model);
  }

  toggleActivitiesSelection() {
    if (this.model.activitiesSelection.selectedItems.size > 0) {
      this.model.activitiesSelection.selectedItems.clear();
      this.activitiesSelectionBtnText = SELECT_ALL_TEXT;
    } else {
      this.model.activitiesSelection.selectedItems = new Set(
        this.model.activitiesSelection.activitiesList
      );
      this.activitiesSelectionBtnText = DESELECT_ALL_TEXT;
    }
  }

  setActivityDummyVariants(activity: string) {
    const leaf = new LeafNode([activity]);
    leaf.setExpanded(true);
    this.activityDummyVariants.set(activity, leaf);
  }

  onChangeCheckbox(activity: string) {
    if (this.model.activitiesSelection.selectedItems.has(activity)) {
      this.model.activitiesSelection.selectedItems.delete(activity);
    } else {
      this.model.activitiesSelection.selectedItems.add(activity);
    }
  }
  protected readonly Array = Array;
}

export class MultiRangeFilter {
  low: number;
  high: number;
  options: Options;
}

export class ActivitiesSelection {
  activitiesList: Set<string>;
  selectedItems: Set<string>;
}

export class MaxValues {
  size: number;
  length: number;
  distance: number;
}
