import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';
import { LogService } from 'src/app/services/logService/log.service';
import {
  Component,
  OnInit,
  ElementRef,
  Inject,
  Renderer2,
  AfterViewInit,
  ChangeDetectorRef,
  OnDestroy,
  Output,
} from '@angular/core';
import { ComponentContainer, LogicalZIndex } from 'golden-layout';
import { ColorMapService } from 'src/app/services/colorMapService/color-map.service';
import { DropzoneConfig } from 'src/app/components/drop-zone/drop-zone.component';
import { VariantService } from 'src/app/services/variantService/variant.service';
import { BackendService } from 'src/app/services/backendService/backend.service';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { VariantPerformanceService } from 'src/app/services/variant-performance.service';
import { Variant } from 'src/app/objects/Variants/variant';
import { IVariant } from 'src/app/objects/Variants/variant_interface';
import { LoopCollapsedVariant } from 'src/app/objects/Variants/loop_collapsed_variant';
import { Dictionary } from 'lodash';

@Component({
  selector: 'app-case-explorer',
  templateUrl: './case-explorer.component.html',
  styleUrls: ['./case-explorer.component.css'],
})
export class CaseExplorerComponent
  extends LayoutChangeDirective
  implements OnInit, AfterViewInit, OnDestroy
{
  @Output()
  mainVariant: Variant;
  index: number;
  caseId: string;
  constructor(
    private colorMapService: ColorMapService,
    private logService: LogService,
    private variantService: VariantService,
    private processTreeService: ProcessTreeService,
    private backendService: BackendService,
    private ref: ChangeDetectorRef,
    @Inject(LayoutChangeDirective.GoldenLayoutContainerInjectionToken)
    private container: ComponentContainer,
    elRef: ElementRef,
    renderer: Renderer2,
    private variantPerformanceService: VariantPerformanceService
  ) {
    super(elRef.nativeElement, renderer);
    let state = this.container.initialState;
    this.mainVariant = state['variant'] as IVariant;
    this.index = state['index'] as number;
    this.caseId = state['case_id'] as string;
  }

  activityColorMap: Map<string, string>;
  activitiesInTree: Set<string> = new Set<string>();
  startActivities: Set<string>;
  endActivities: Set<string>;
  activitiesInLog: any;
  activityFields: ActivityField[];
  caseActivities: Map<string, number>[];
  activityPropertyKeys: any; //how to improve

  sortKey: string = 'end_timestamp';
  ascending: boolean = true;

  activityOverviewOutOfFocus: boolean = false;

  dropZoneConfig: DropzoneConfig;

  resetAvailable: boolean = false;

  private _destroy$ = new Subject();

  ngOnInit(): void {
    this.dropZoneConfig = new DropzoneConfig(
      '.xes',
      'false',
      'false',
      '<large> Import <strong>Event Log</strong> .xes file</large>'
    );

    this.activityFields = [];

    this.backendService
      .getCaseActivities(this.index - 1, this.caseId)
      .subscribe((caseActivities: Map<string, any>[]) => {
        this.caseActivities = caseActivities['statistics'];
        this.activityPropertyKeys = caseActivities['keys'];
      });

    this.variantService.cachedChange$
      .pipe(takeUntil(this._destroy$))
      .subscribe((change) => {
        this.resetAvailable = change;
      });
  }

  ngAfterViewInit(): void {
    this.colorMapService.colorMap$
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        this.activityColorMap = colorMap;

        if (this.activityFields) {
          for (let activityField of this.activityFields) {
            activityField.color = this.activityColorMap.get(
              activityField.activityName
            );
          }
        }
      });

    // Handle change of current activies in the loaded model
    this.processTreeService.activitiesInCurrentTree$
      .pipe(takeUntil(this._destroy$))
      .subscribe((activitiesInTree) => {
        for (let field of this.activityFields) {
          field.inModel = activitiesInTree.has(field.activityName);
        }
      });

    this.variantService.variants$
      .pipe(takeUntil(this._destroy$))
      .subscribe(() => {
        if (this.activityColorMap) {
          this.resetActivityFields();
        }
      });
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }

  resetActivityFields() {
    this.startActivities = this.logService.startActivitiesInEventLog;
    this.endActivities = this.logService.endActivitiesInEventLog;
    this.activitiesInLog = this.logService.activitiesInEventLog;
    this.activitiesInTree = this.processTreeService.activitiesInCurrentTree;

    this.activityFields = [];
    for (let activity in this.activitiesInLog) {
      this.activityFields.push(
        new ActivityField(
          activity,
          this.activitiesInLog[activity],
          this.activityColorMap.get(activity),
          this.activitiesInTree.has(activity),
          this.startActivities.has(activity),
          this.endActivities.has(activity)
        )
      );
    }
  }

  toggleBlur(event) {
    this.activityOverviewOutOfFocus = event;
  }

  handleResponsiveChange(
    left: number,
    top: number,
    width: number,
    height: number
  ): void {}

  handleVisibilityChange(visibility: boolean): void {}

  handleZIndexChange(
    logicalZIndex: LogicalZIndex,
    defaultZIndex: string
  ): void {}

  toggleSort(sortKey: string) {
    // On the first Click always make descending
    if (this.sortKey != sortKey) {
      this.sortKey = sortKey;
      this.ascending = false;
    } else {
      // Make it toggle between on subsequent clicks
      this.ascending = !this.ascending;
    }
  }

  deleteActivity(e: Event, activity: ActivityField) {
    this.variantService.deleteActivity(activity.activityName).subscribe();
    this.variantPerformanceService.resetVariantPerformance();
    this.resetActivityFields();
  }

  changeActivityColor(activityField: ActivityField, color: string) {
    if (color) {
      activityField.color = color;
      this.colorMapService.changeActivityColor(
        activityField.activityName,
        color
      );
    }
  }

  resetActivityColors(): void {
    this.colorMapService.createColorMap(
      Array.from(this.activityColorMap.keys())
    );
  }

  resetActivityNames(): void {
    if (this.activityFields) {
      for (let activityField of this.activityFields) {
        activityField.inputActivityName = activityField.activityName;
      }
    }
  }

  // TODO: refactor this to shared data service
  applyActivityNameChanges(
    oldActivityName: string,
    newActivityName: string
  ): void {
    if (oldActivityName !== newActivityName) {
      this.variantService
        .renameActivity(oldActivityName, newActivityName)
        .subscribe();
      // Changing activity field table
      this.resetActivityFields();
    }
  }

  revertLastChange(e: Event) {
    e.stopPropagation();
    this.resetAvailable = false;
    this.variantService.revertChangeInBackend();
  }
}

export class ActivityField {
  activityName: string;
  occurences: number;
  inModel: boolean;
  isStart: boolean;
  isEnd: boolean;
  color: string;
  inputActivityName: string; // Storing the input name from user

  constructor(
    activityName: string,
    occurences: number,
    color: string,
    inModel: boolean,
    isStart: boolean,
    isEnd: boolean
  ) {
    this.activityName = activityName;
    this.occurences = occurences;
    this.inModel = inModel;
    this.isStart = isStart;
    this.isEnd = isEnd;
    this.color = color;
    this.inputActivityName = activityName;
  }
}

export namespace CaseExplorerComponent {
  export const componentName = 'CaseExplorerComponent';
}
