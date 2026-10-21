import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  Output,
  QueryList,
  SimpleChanges,
  ViewChildren,
} from '@angular/core';
import { ColorMapService } from '../../../services/colorMapService/color-map.service';
import { ActvitiyFilterState } from '../variant-miner.component';
import {
  LeafNode,
  VariantElement,
} from '../../../objects/Variants/variant_element';
import { VariantDrawerDirective } from '../../../directives/variant-drawer/variant-drawer.directive';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { Variant } from '../../../objects/Variants/variant';
import * as d3 from 'd3';

@Component({
  selector: 'app-variant-miner-activities-filter',
  templateUrl: './variant-miner-activities-filter.component.html',
  styleUrls: ['./variant-miner-activities-filter.component.css'],
})
export class VariantMinerActivitiesFIlterComponent
  implements OnChanges, OnInit, OnDestroy
{
  constructor(private colorMapService: ColorMapService) {}

  @Input()
  activityNames: Array<string> = [];
  interleavedActivityNames: Array<string> = [];
  @Input()
  activityNamesFilter: Map<string, ActvitiyFilterState> = new Map<
    string,
    ActvitiyFilterState
  >();
  activityDummyVariants: Map<string, LeafNode> = new Map<string, LeafNode>();
  activityFilterStates: Map<string, { checkbox: boolean; toggle: boolean }>;

  @Output()
  activityButtonClick = new EventEmitter();

  @ViewChildren(VariantDrawerDirective)
  activityButtons: QueryList<VariantDrawerDirective>;

  colorMap: Map<string, string> = new Map<string, string>();

  private _destroy$ = new Subject();

  ngOnInit() {
    this.activityDummyVariants = new Map<string, LeafNode>();
    this.activityFilterStates = new Map<
      string,
      { checkbox: boolean; toggle: boolean }
    >();

    this.interleavedActivityNames = this.activityNames.slice();

    this.interleavedActivityNames = this.interleaveArrays(
      this.interleavedActivityNames
        .splice(0, Math.ceil(this.interleavedActivityNames.length / 2))
        .sort(),
      this.interleavedActivityNames.sort()
    );

    for (let activity of this.activityNames) {
      const leaf = new LeafNode([activity]);
      leaf.setExpanded(true);
      this.activityDummyVariants.set(activity, leaf);

      const activityFilter = this.activityNamesFilter.get(activity);
      switch (activityFilter) {
        case ActvitiyFilterState.Default:
          this.activityFilterStates.set(activity, {
            checkbox: false,
            toggle: false,
          });
          break;

        case ActvitiyFilterState.In:
          this.activityFilterStates.set(activity, {
            checkbox: true,
            toggle: true,
          });
          break;

        case ActvitiyFilterState.Out:
          this.activityFilterStates.set(activity, {
            checkbox: true,
            toggle: false,
          });
          break;
      }
    }

    this.colorMapService.colorMap$
      .pipe(takeUntil(this._destroy$))
      .subscribe((map) => {
        this.colorMap = map;
        if (this.activityButtons) {
          for (let button of this.activityButtons) {
            button.redraw();
          }
        }
      });
  }

  interleaveArrays(
    array1: Array<string>,
    array2: Array<string>
  ): Array<string> {
    const result = array1.reduce((arr, v, i) => {
      return arr.concat(v, array2[i]);
    }, []);
    if (array1.length > array2.length) {
      result.pop();
    }
    return result;
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }

  computeActivityColor = (
    self: VariantDrawerDirective,
    element: VariantElement,
    variant: Variant
  ) => {
    let color;
    color = this.colorMap.get(element.asLeafNode().activity[0]);

    if (!color) {
      color = '#d3d3d3'; // lightgrey
    }

    return color;
  };

  ngOnChanges(changes: SimpleChanges): void {
    // A somewhat crude way to trigger a redraw after the value did change and preventing it from firing on the initalization
    // Review when the colormap might change after init
    this.activityDummyVariants = new Map<string, LeafNode>();

    for (let activity of changes.activityNames.currentValue) {
      const leaf = new LeafNode([activity]);
      leaf.setExpanded(true);
      this.activityDummyVariants.set(activity, leaf);
    }
  }

  public get actvitiyFilterState(): typeof ActvitiyFilterState {
    return ActvitiyFilterState;
  }

  // tslint:disable-next-line:typedef
  activityFilterChange(event, activity) {
    const checkbox = this.activityFilterStates.get(activity).checkbox;
    const toggle = this.activityFilterStates.get(activity).toggle;
    let filter = ActvitiyFilterState.Default;

    if (checkbox === false) {
      filter = ActvitiyFilterState.Default;
      this.activityFilterStates.set(activity, {
        checkbox: false,
        toggle: false,
      });
      event.preventDefault();
    } else if (checkbox === true && toggle === false) {
      filter = ActvitiyFilterState.Out;
    } else if (checkbox === true && toggle === true) {
      filter = ActvitiyFilterState.In;
    }

    this.activityNamesFilter.set(activity, filter);
    this.activityButtonClick.emit({ activityName: activity, filter });
  }
}
