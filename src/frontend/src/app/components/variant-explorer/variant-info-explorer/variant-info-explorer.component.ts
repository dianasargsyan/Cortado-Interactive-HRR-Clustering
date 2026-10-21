import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';
import { LogService } from 'src/app/services/logService/log.service';
import {
  Component,
  EventEmitter,
  OnInit,
  ElementRef,
  Inject,
  Renderer2,
  AfterViewInit,
  ChangeDetectorRef,
  OnDestroy,
  Output,
} from '@angular/core';
import {
  ComponentContainer,
  ComponentItem,
  ComponentItemConfig,
  GoldenLayout,
  LayoutManager,
  LogicalZIndex,
  Stack,
} from 'golden-layout';
import { GoldenLayoutHostComponent } from 'src/app/components/golden-layout-host/golden-layout-host.component';
import { GoldenLayoutComponentService } from 'src/app/services/goldenLayoutService/golden-layout-component.service';
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
import { CaseExplorerComponent } from '../case-explorer/case-explorer.component';
import { SubvariantExplorerComponent } from '../subvariant-explorer/subvariant-explorer.component';
import _ from 'lodash';

@Component({
  selector: 'app-variant-info-explorer',
  templateUrl: './variant-info-explorer.component.html',
  styleUrls: ['./variant-info-explorer.component.css'],
})
export class VariantInfoExplorerComponent
  extends LayoutChangeDirective
  implements OnInit, AfterViewInit, OnDestroy
{
  @Output()
  mainVariant: Variant;
  index: number;
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
    private variantPerformanceService: VariantPerformanceService,
    private goldenLayoutComponentService: GoldenLayoutComponentService
  ) {
    super(elRef.nativeElement, renderer);
    let state = this.container.initialState;
    this.mainVariant = state['variant'] as IVariant;
    this.index = state['index'] as number;
  }

  public variants: Variant[] = [];
  public displayed_variants: IVariant[] = []; //delete later

  activityColorMap: Map<string, string>;
  activitiesInTree: Set<string> = new Set<string>();
  startActivities: Set<string>;
  endActivities: Set<string>;
  activitiesInLog: any;
  activityFields: ActivityField[];
  caseStatistics: Map<string, number>[];

  sortKey: string = 'case_id';
  ascending: boolean = false;

  maximized: boolean = false;

  activityOverviewOutOfFocus: boolean = false;

  dropZoneConfig: DropzoneConfig;

  resetAvailable: boolean = false;

  private _destroy$ = new Subject();

  _goldenLayoutHostComponent: GoldenLayoutHostComponent;
  _goldenLayout: GoldenLayout;
  _subvariantcomponentItemsMap: Map<string, ComponentItem> = new Map<
    string,
    ComponentItem
  >();

  ngOnInit(): void {
    this.dropZoneConfig = new DropzoneConfig(
      '.xes',
      'false',
      'false',
      '<large> Import <strong>Event Log</strong> .xes file</large>'
    );

    this.activityFields = [];

    this.backendService
      .calculateCaseStatistics(this.index - 1)
      .subscribe((caseStatistics: Map<string, number>[]) => {
        this.caseStatistics = caseStatistics['statistics'];
      });

    this.variantService.cachedChange$
      .pipe(takeUntil(this._destroy$))
      .subscribe((change) => {
        this.resetAvailable = change;
      });
  }

  ngAfterViewInit(): void {
    this._goldenLayoutHostComponent =
      this.goldenLayoutComponentService.goldenLayoutHostComponent;
    this._goldenLayout = this.goldenLayoutComponentService.goldenLayout;

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
  ): void {
    this.maximized = logicalZIndex === 'stackMaximised';
  }

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

  //
  createCaseInfoView(case_id) {
    const state = this.container.getState();

    // find variant by id
    let variant = state['variant'];

    const currently_maximized = this.maximized;
    const LocationSelectors: LayoutManager.LocationSelector[] = [
      {
        typeId: LayoutManager.LocationSelector.TypeId.FocusedStack,
        index: undefined,
      },
    ];

    this.cleanUpSubVariantMap();

    const id =
      CaseExplorerComponent.componentName + state['variant_id'] + case_id;

    let componentItem = this._subvariantcomponentItemsMap.get(id);

    // Check if the component item reference already is stored and if the item still exists
    // Saves on a search by ID
    if (componentItem) {
      componentItem.focus();

      // Instantiate a new Subvariant Component for this variant if it did not exist or is closed
    } else {
      const subvariantInfoExplorerItem =
        this._goldenLayout.findFirstComponentItemById(
          VariantInfoExplorerComponent.componentName + state['variant_id']
        );

      subvariantInfoExplorerItem.focus();

      const itemConfig: ComponentItemConfig = {
        id: id,
        type: 'component',
        title: 'Case ' + case_id + ' (Var. ' + state['index'] + ')',
        isClosable: true,
        reorderEnabled: true,
        componentState: {
          variant: variant,
          index: state['index'],
          clusterId: state['clusterId'],
          variant_id: state['variant_id'],
          case_id: case_id,
        },
        maximised: true,
        componentType: CaseExplorerComponent.componentName,
      };

      this._goldenLayout.addItemAtLocation(itemConfig, LocationSelectors);
      componentItem = this._goldenLayout.findFirstComponentItemById(id);
      this._subvariantcomponentItemsMap.set(id, componentItem);

      // Keep the stack maximized
      if (currently_maximized) {
        const stack = componentItem.container.parent.parent as Stack;
        stack.toggleMaximise();
      }

      subvariantInfoExplorerItem.focus();
    }
  }

  cleanUpSubVariantMap() {
    const state = this.container.getState();
    for (let index = 0; index < this.variants.length; index++) {
      const id =
        SubvariantExplorerComponent.componentName + this.variants[index].id;
      const componentItem = this._subvariantcomponentItemsMap.get(id);
      if (
        componentItem &&
        !this._goldenLayoutHostComponent.getComponentRef(
          componentItem.container
        )
      ) {
        this._subvariantcomponentItemsMap.delete(id);
      }
    }
    for (let index = 0; index < this.variants.length; index++) {
      const id =
        VariantInfoExplorerComponent.componentName + this.variants[index].id;
      const componentItem = this._subvariantcomponentItemsMap.get(id);
      if (
        componentItem &&
        !this._goldenLayoutHostComponent.getComponentRef(
          componentItem.container
        )
      ) {
        this._subvariantcomponentItemsMap.delete(id);
      }
    }
    for (let caseInfo of this.caseStatistics) {
      const id =
        CaseExplorerComponent.componentName +
        state['variant_id'] +
        caseInfo['case_id'];
      const componentItem = this._subvariantcomponentItemsMap.get(id);
      if (
        componentItem &&
        !this._goldenLayoutHostComponent.getComponentRef(
          componentItem.container
        )
      ) {
        this._subvariantcomponentItemsMap.delete(id);
      }
    }
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

export namespace VariantInfoExplorerComponent {
  export const componentName = 'VariantInfoExplorerComponent';
}
