import {
  VariantFilter,
  VariantFilterService,
} from '../../services/variantFilterService/variant-filter.service';

import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  ElementRef,
  HostListener,
  Inject,
  OnDestroy,
  OnInit,
  QueryList,
  Renderer2,
  ViewChild,
  ViewChildren,
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
import { combineLatest, from, Subject } from 'rxjs';
import {
  concatMap,
  delay,
  filter,
  mergeMap,
  retryWhen,
  take,
  takeUntil,
  tap,
} from 'rxjs/operators';
import { GoldenLayoutHostComponent } from 'src/app/components/golden-layout-host/golden-layout-host.component';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { VariantDrawerDirective } from 'src/app/directives/variant-drawer/variant-drawer.directive';

import { TimeUnit } from 'src/app/objects/TimeUnit';
import { HumanizeDurationPipe } from 'src/app/pipes/humanize-duration.pipe';
import {
  AlignmentType,
  ConformanceCheckingService,
} from 'src/app/services/conformanceChecking/conformance-checking.service';
import { GoldenLayoutComponentService } from 'src/app/services/goldenLayoutService/golden-layout-component.service';
import { LogService, LogStats } from 'src/app/services/logService/log.service';
import { ModelPerformanceColorScaleService } from 'src/app/services/performance-color-scale.service';
import { PerformanceService } from 'src/app/services/performance.service';
import { PolygonDrawingService } from 'src/app/services/polygon-drawing.service';
import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';
import { VariantPerformanceService } from 'src/app/services/variant-performance.service';
import { VariantService } from 'src/app/services/variantService/variant.service';
import { originalOrder } from 'src/app/utils/util';
import { BackendService } from '../../services/backendService/backend.service';
import { ColorMapService } from '../../services/colorMapService/color-map.service';
import { ImageExportService } from '../../services/imageExportService/image-export-service';
import { SharedDataService } from '../../services/sharedDataService/shared-data.service';
import { DropzoneConfig } from '../drop-zone/drop-zone.component';
import { SubvariantExplorerComponent } from './subvariant-explorer/subvariant-explorer.component';
import { VariantInfoExplorerComponent } from './variant-info-explorer/variant-info-explorer.component';
import { Variant } from 'src/app/objects/Variants/variant';
import {
  deserialize,
  LeafNode,
  ParallelGroup,
  SequenceGroup,
  VariantElement,
} from 'src/app/objects/Variants/variant_element';
import { exportVariantDrawer } from './functions/export-variant-explorer';
import {
  fadeInOutComponent,
  openCloseComponent,
} from 'src/app/animations/component-animations';
import { collapsingText } from 'src/app/animations/text-animations';
import { textColorForBackgroundColor } from 'src/app/utils/render-utils';
import { processTreesEqual } from 'src/app/objects/ProcessTree/utility-functions/process-tree-integrity-check';
import { ViewMode } from 'src/app/objects/ViewMode';
import { VariantViewModeService } from 'src/app/services/viewModeServices/variant-view-mode.service';
import { EditorOptions } from './variant-query/variant-query.component';
import { ContextMenuItem } from './variant-explorer-context-menu/variant-explorer-context-menu.component';
import { ToastService } from 'src/app/services/toast/toast.service';
import { ProcessTree } from 'src/app/objects/ProcessTree/ProcessTree';
import { IVariant } from 'src/app/objects/Variants/variant_interface';
import { LoopCollapsedVariant } from 'src/app/objects/Variants/loop_collapsed_variant';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ClusteringSettingsDialogComponent } from './clustering-settings-dialog/clustering-settings-dialog.component';
import { ConstraintOverviewDialogComponent } from './constraint-overview-dialog/constraint-overview-dialog.component';
import { ConstraintService } from 'src/app/services/constraintService/constraint.service';
import { HRRClusteringService } from 'src/app/services/hrrClusteringService/hrr-clustering.service';
import {
  HRRClusterInfo,
  HRRClusteringResult,
} from 'src/app/objects/HRRClustering';

type HRRClusterHeader = {
  label: string;
  typical: Variant | null;
  color: (self: any, element: VariantElement, variant: Variant) => string;
  why: string;
  changes: string | null;
};
import _ from 'lodash';
import { InfixType } from 'src/app/objects/Variants/infix_selection';
import { DocumentationService } from '../documentation/documentation.service';
import * as d3 from 'd3';
import { Arc, Pair } from '../../directives/arc-diagram/data';
import { VariantVisualisationComponent } from './variant/subcomponents/variant-visualisation/variant-visualisation.component';
import { FilterParams } from './arc-diagram/filter/filter-params';
import { MaxValues } from './arc-diagram/filter/filter.component';
import { ArcsViewMode } from './arc-diagram/arcs-view-mode';
import { ArcDiagramService } from '../../services/arcDiagramService/arc-diagram.service';
import { ArcDiagramComputationResult } from '../../services/arcDiagramService/model';

@Component({
  selector: 'app-variant-explorer',
  templateUrl: './variant-explorer.component.html',
  styleUrls: ['./variant-explorer.component.scss'],
  animations: [collapsingText, fadeInOutComponent, openCloseComponent],
})
export class VariantExplorerComponent
  extends LayoutChangeDirective
  implements OnInit, AfterViewInit, OnDestroy
{
  constructor(
    private colorMapService: ColorMapService,
    private sharedDataService: SharedDataService,
    public variantService: VariantService,
    private variantFilterService: VariantFilterService,
    private backendService: BackendService,
    private logService: LogService,
    private imageExportService: ImageExportService,
    private polygonDrawingService: PolygonDrawingService,
    @Inject(LayoutChangeDirective.GoldenLayoutContainerInjectionToken)
    private container: ComponentContainer,
    public processTreeService: ProcessTreeService,
    elRef: ElementRef,
    private renderer: Renderer2,
    public performanceService: PerformanceService,
    private performanceColorService: ModelPerformanceColorScaleService,
    public variantPerformanceService: VariantPerformanceService,
    public conformanceCheckingService: ConformanceCheckingService,
    public arcDiagramService: ArcDiagramService,
    private goldenLayoutComponentService: GoldenLayoutComponentService,
    public variantViewModeService: VariantViewModeService,
    private toastService: ToastService,
    private modalService: NgbModal,
    private changeDetectorRef: ChangeDetectorRef,
    private documentationService: DocumentationService,
    public constraintService: ConstraintService,
    public hrrClusteringService: HRRClusteringService
  ) {
    super(elRef.nativeElement, renderer);
    this.explorerElement = elRef;
  }
  explorerElement: ElementRef;

  collapse: boolean = false;
  maximized: boolean = false;

  public variants: Variant[] = [];
  public displayed_variants: IVariant[] = [];
  public colorMap: Map<string, string>;
  public sidebarHeight = 0;

  public logStats: LogStats = null;

  public currentlyDisplayedProcessTree;
  protected unsubscribe: Subject<void> = new Subject<void>();

  public correctTreeSyntax = false;
  expansionState: Map<string, boolean> = new Map<string, boolean>();
  serviceTimeColorMap: any;
  waitingTimeColorMap: any;

  public VM = ViewMode;

  public svgRenderingInProgress: boolean = false;
  public variantExplorerOutOfFocus: boolean = false;

  _goldenLayoutHostComponent: GoldenLayoutHostComponent;
  _goldenLayout: GoldenLayout;
  _subvariantcomponentItemsMap: Map<string, ComponentItem> = new Map<
    string,
    ComponentItem
  >();

  dropZoneConfig: DropzoneConfig;
  public isAscendingOrder: boolean = false;
  public sortingFeature: string = 'count';
  queryActive: boolean = false;
  showQueryInfo: boolean = false;

  contextMenu_xPos: number = 10;
  contextMenu_yPos: number = 10;
  contextMenu_element: VariantElement;
  contextMenu_variant: VariantElement;
  contextMenu_directive: VariantDrawerDirective;

  filterMap: Map<string, VariantFilter> = new Map<string, VariantFilter>();

  public options: EditorOptions = new EditorOptions();

  // Exporter
  exportVariantSVG = exportVariantDrawer.bind(this);

  public traceInfixSelectionMode: boolean = false;

  @ViewChild('variantExplorer', { static: true })
  variantExplorerDiv: ElementRef<HTMLDivElement>;

  @ViewChild('variantExplorerContainer')
  variantExplorerContainer: ElementRef<HTMLDivElement>;

  @ViewChild('tooltipContainer')
  tooltipContainer: ElementRef<HTMLDivElement>;

  @ViewChildren(VariantVisualisationComponent)
  variantVisualisations: QueryList<VariantVisualisationComponent>;

  public visibleVariantsHeight = 1000;

  public deletedVariants: Variant[][] = [];

  timeUnit = TimeUnit;

  selectedGranularity = TimeUnit.SEC;

  originalOrder = originalOrder;

  public arcs: { [id: number]: Arc[] } = {};
  public arcsMaxValues: MaxValues = {
    size: 1,
    length: 1,
    distance: 1,
  };
  public showFilterMenu: boolean = false;
  public lastArcsActivitiesFilter = new Set<string>();
  public arcsCache: { [bid: string]: Pair[] } = {};
  public arcsViewMode: ArcsViewMode = ArcsViewMode.INITIAL;
  public filterParams: FilterParams = new FilterParams();
  public filtering: boolean;

  deleteVariant = function () {
    const bids = this.variantService.variants
      .filter((v) => v.variant === this.contextMenu_variant)
      .map((v) => v.bid);

    this.variantService.deleteVariants(bids);
  }.bind(this);

  contextMenuOptions: Array<ContextMenuItem> = [
    new ContextMenuItem('Delete Variant', 'bi-trash', this.deleteVariant),
  ];

  // stores the sort settings for each cluster
  // if no clustering algo is applied we only have the key
  // 'unefined' which is the default cluster key
  clusterSortSettings: {} = {};

  public hideRuleContent: boolean[] = [];
  public buttonName: any = 'Expand';

  toggle(index) {
    // toggle based on index
    this.hideRuleContent[index] = !this.hideRuleContent[index];
  }

  private _destroy$ = new Subject();

  ngOnInit(): void {
    // initialize variables and initial variants
    this.init();
    // update variant explorer on log change
    this.listenForLogChange();
    // redraw variants on color map change
    this.listenForColorMapChange();
    // update view when activity names change
    this.listenForCorrectSyntax();
    this.listenForProcessTreeChange();
    this.conformanceCheckingService.connect();
    this.arcDiagramService.connect();
    this.subscribeForConformanceCheckingResults();
    this.subscribeForArcDiagramsComputationsResults();
    this.listenForLogGranularityChange();
    this.listenForLogStatChange();
    this.listenForViewModeChange();
    this.listenForLoopCollapsedVariantsChange();
    this.listenForHRRClusteringResult();

    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length === 1) {
        const newHeight = entries[0].contentRect.height;
        d3.select(this.explorerElement.nativeElement)
          .select('.dropdown-menu')
          .style('max-height', newHeight.toString() + 'px');
      }
    });
    resizeObserver.observe(this.variantExplorerDiv.nativeElement);
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }

  @HostListener('window:keydown.control.q', ['$event'])
  onopenComponent(e) {
    this.toggleQueryFilterDialog();
  }

  ngAfterViewInit() {
    this.polygonDrawingService.setElementRefereneces(
      this.variantExplorerContainer,
      this.tooltipContainer
    );

    this._goldenLayoutHostComponent =
      this.goldenLayoutComponentService.goldenLayoutHostComponent;
    this._goldenLayout = this.goldenLayoutComponentService.goldenLayout;

    const variantExplorerItem = this._goldenLayout.findFirstComponentItemById(
      VariantExplorerComponent.componentName
    );

    variantExplorerItem.focus();

    this.variantService.variants$
      .pipe(takeUntil(this._destroy$))
      .subscribe((variants) => {
        this.variantService.areVariantLoopsCollapsed = false;
        this.variants = variants;
        this.displayed_variants = variants.filter((v) => v.isDisplayed);
        this.sort(this.sortingFeature);
        this.closeAllSubvariantWindows();
        this.redraw_components();
        this.arcsCache = {};
      });

    this.variantFilterService.variantFilters$.subscribe((filterMap) => {
      this.filterMap = filterMap;

      if (filterMap.size > 0) {
        const intersectSets = function (a: Set<number>, b: Set<number>) {
          const c: Set<number> = new Set<number>();
          a.forEach((v) => b.has(v) && c.add(v));
          return c;
        };

        const filterSet = Array.from(filterMap.values())
          .map((f) => f.bids)
          .reduce((a, b) => intersectSets(a, b));

        this.displayed_variants = this.variants.filter((v) => {
          if (filterSet.has(v.bid)) {
            v.isDisplayed = true;
            return true;
          } else {
            v.isDisplayed = false;
          }
        });
      } else {
        this.displayed_variants = this.variants;
        this.variants.forEach((v) => (v.isDisplayed = true));
      }

      this.updateAllSubvariantWindows();
      this.redraw_components();
    });

    this.variantPerformanceService.serviceTimeColorMap
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        if (colorMap !== undefined) {
          this.serviceTimeColorMap = colorMap;
          this.redraw_components();
        }
      });

    this.variantPerformanceService.waitingTimeColorMap
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        if (colorMap !== undefined) {
          this.waitingTimeColorMap = colorMap;
          this.redraw_components();
        }
      });
  }

  private init() {
    console.warn('Running Init');
    this.displayed_variants = [];
    this.backendService
      .resetLogCache() // for now show the sample log again on reload
      .pipe(retryWhen((errors) => errors.pipe(delay(500), take(50)))) // backend might need some time to start up
      .pipe(
        mergeMap(() =>
          // Time granularity is null because the granularity is determined in the backend
          this.backendService.getLogPropsAndUpdateState(null, 'preload')
        ),
        takeUntil(this._destroy$)
      )
      .subscribe((val) => {
        this.selectedGranularity = val.timeGranularity;
      });
  }

  private listenForProcessTreeChange() {
    this.processTreeService.currentDisplayedProcessTree$
      .pipe(
        takeUntil(this._destroy$),
        filter(
          (tree) => !processTreesEqual(tree, this.currentlyDisplayedProcessTree)
        )
      )
      .subscribe((tree) => {
        this.currentlyDisplayedProcessTree = tree?.copy();

        this.variants.forEach((variant) => {
          if (variant.usedTreeForConformanceChecking)
            variant.isConformanceOutdated = !processTreesEqual(
              tree,
              variant.usedTreeForConformanceChecking
            );
        });
        this.redraw_components();
      });
  }

  private listenForCorrectSyntax() {
    this.processTreeService.correctTreeSyntax$
      .pipe(takeUntil(this._destroy$))
      .subscribe((res) => {
        this.correctTreeSyntax = res;
      });
  }

  private listenForColorMapChange() {
    this.colorMapService.colorMap$
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        this.colorMap = colorMap;
        this.redraw_components();
      });
  }

  private listenForLogStatChange() {
    this.logService.logStatistics$
      .pipe(takeUntil(this._destroy$))
      .subscribe((logStat) => {
        this.logStats = logStat;
      });
  }

  private listenForLogChange() {
    this.logService.loadedEventLog$
      .pipe(
        tap(() => {
          this.closeAllSubvariantWindows();
          this.variantViewModeService.viewMode = ViewMode.STANDARD;
          this.variantService.areVariantLoopsCollapsed = false;
          this.variantService.clusteringConfig = null; // reset applied clustering
          this.arcsCache = {};
        })
      )
      .pipe(takeUntil(this._destroy$))
      .subscribe();
  }

  private redraw_components() {
    if (this.variantVisualisations) {
      for (let component of this.variantVisualisations) {
        component.variantDrawer.redraw();
        this.renderer.setStyle(
          component.arcDiagram.svgHtmlElement.nativeElement,
          'display',
          'none'
        );
        this.arcsViewMode = ArcsViewMode.HIDE_ALL;
      }
    }
  }

  subscribeForConformanceCheckingResults(): void {
    this.conformanceCheckingService.varResults
      .pipe(takeUntil(this._destroy$))
      .subscribe(
        (res) => {
          if ('error' in res) {
            this.variants.forEach((v) => {
              v.calculationInProgress = false;
            });

            this.updateAlignmentStatistics();
            this.redraw_components();
            return;
          }

          const variant = this.variants.find((v) => v.id == res.id);
          variant.calculationInProgress = false;
          variant.isTimeouted = res.isTimeout;
          variant.isConformanceOutdated = res.isTimeout;

          if (!res.isTimeout) {
            variant.alignment = deserialize(res.alignment);
            variant.alignment.setExpanded(variant.variant.getExpanded());
            variant.deviations = res.deviations;
            variant.usedTreeForConformanceChecking = res.processTree;
          }

          this.updateAlignmentStatistics();
          this.variantVisualisations
            .find((vv) => vv.id == res.id)
            ?.variantDrawer?.redraw();
        },
        (_) => {
          this.variants.forEach((v) => {
            v.calculationInProgress = false;
          });

          this.updateAlignmentStatistics();
          this.redraw_components();
        }
      );
  }

  updateAlignments(): void {
    this.variants.forEach((v) => {
      this.updateConformanceForVariant(v, 0);
    });
  }

  // @ Refactor into Alignment Service
  updateAlignmentStatistics(): void {
    let numberFittingVariants = 0;
    let numberFittingTraces = 0;

    this.variants.forEach((v) => {
      if (v.deviations == 0) {
        numberFittingVariants++;
        numberFittingTraces += v.count;
      }
    });

    this.logService.update_log_stats(
      numberFittingTraces,
      numberFittingVariants
    );
  }

  updateConformanceForVariant(variant: IVariant, timeout: number): void {
    let underlyingVariants = [];
    if (variant instanceof LoopCollapsedVariant) {
      underlyingVariants = variant.variants;
    } else {
      underlyingVariants = [variant];
    }

    underlyingVariants.forEach((v) => {
      v.calculationInProgress = true;
      v.deviations = undefined;

      const resubscribe = this.conformanceCheckingService.calculateConformance(
        v.id,
        v.infixType,
        this.processTreeService.currentDisplayedProcessTree,
        v.variant.serialize(1),
        timeout,
        AlignmentType.VariantAlignment
      );

      if (resubscribe) {
        this.subscribeForConformanceCheckingResults();
      }
    });
  }

  updateConformanceForSingleVariantClicked(variant: IVariant): void {
    if (variant.isTimeouted) {
      this.conformanceCheckingService.showConformanceTimeoutDialog(
        variant,
        this.updateConformanceForVariant.bind(this)
      );
    } else {
      this.updateConformanceForVariant(variant, 0);
    }
  }

  computePerformanceButtonColor = (variant: Variant) => {
    let tree;
    tree = this.performanceService.variantsTreePerformance.get(variant);

    if (!tree) {
      return null;
    }

    let selectedScale = this.performanceColorService.selectedColorScale;
    const colorScale = this.performanceColorService
      .getVariantComparisonColorScale()
      .get(tree.id);
    if (
      colorScale &&
      tree.performance?.[selectedScale.performanceIndicator]?.[
        selectedScale.statistic
      ] !== undefined
    ) {
      return colorScale.getColor(
        tree.performance[selectedScale.performanceIndicator][
          selectedScale.statistic
        ]
      );
    }
    return '#d3d3d3';
  };

  removeFilter(filter_name: string) {
    this.variantFilterService.removeVariantFilter(filter_name);
  }

  handleSelectInfix(variant: Variant) {
    this.variantService.addSelectedTraceInfix(
      this.variants.filter((v) => v.bid === variant.bid)[0],
      this.sortingFeature,
      this.isAscendingOrder
    );
  }

  discoverInitialModel(): void {
    const variants = this.getSelectedVariants();

    this.backendService
      .discoverProcessModelFromConcurrencyVariants(variants)
      .pipe(takeUntil(this._destroy$))
      .subscribe((tree) =>
        this.refreshConformanceIconsAfterModelChange(true, tree)
      );
  }

  changeQueryOption(event, option) {
    const newOptions: EditorOptions = new EditorOptions();
    Object.entries(this.options).forEach((v) => (newOptions[v[0]] = v[1]));
    newOptions[option] = event.target.checked;

    this.options = newOptions;
  }

  genSimpleVariants(variant: VariantElement): any {
    if (variant instanceof SequenceGroup) {
      return variant.elements;
    } else if (variant instanceof ParallelGroup) {
    } else {
      return [variant.asLeafNode().activity];
    }
  }

  mapVariantToEventList(variant): any {
    return {
      events: variant
        .flat()
        .filter((v) => v[1].toLowerCase() === 'complete')
        .map((v) => `${v[0]}`),
    };
  }

  selectionChangedForVariant(variant: Variant, isSelected: boolean): void {
    variant.isSelected = isSelected;
  }

  addSelectedVariantsToModel(): void {
    const selectedVariants = this.getSelectedVariants();

    // TODO we currently distinguish two cases here: 1. outdated conformance and 2. known conformance
    // in the future, we want to use caching in the backend and use only a single call from frontend
    if (this.isAnyVariantOutdated(selectedVariants)) {
      this.addSelectedVariantsToModelForOutdatedConformance(selectedVariants);
      return;
    }

    this.addSelectedVariantsToModelForGivenConformance(selectedVariants);
  }

  handleTreePerformanceClear() {
    this.performanceService.hideTreePerformance();
  }

  /**
   * Create subvariant tab
   * @param clusterId id of the cluster
   * @param idx position in the cluster
   * @param variant_id id of the variant
   */
  createSubVariantView(clusterId, idx, variant_id) {
    // find variant by id
    let variant = _.find(
      this.displayed_variants,
      (variant) => variant_id === variant.id
    );

    const currently_maximized = this.maximized;

    const LocationSelectors: LayoutManager.LocationSelector[] = [
      {
        typeId: LayoutManager.LocationSelector.TypeId.FocusedStack,
        index: undefined,
      },
    ];

    this.cleanUpSubVariantMap();

    const id = SubvariantExplorerComponent.componentName + variant_id;

    let componentItem = this._subvariantcomponentItemsMap.get(id);

    // Check if the component item reference already is stored and if the item still exists
    // Saves on a search by ID
    if (componentItem) {
      componentItem.focus();

      // Instantiate a new Subvariant Component for this variant if it did not exist or is closed
    } else {
      const variantExplorerItem = this._goldenLayout.findFirstComponentItemById(
        VariantExplorerComponent.componentName
      );

      variantExplorerItem.focus();

      const itemConfig: ComponentItemConfig = {
        id: id,
        type: 'component',
        title: 'Sub-Variants for ' + idx + ' (Cluster ' + clusterId + ')',
        isClosable: true,
        reorderEnabled: true,
        componentState: {
          variant: variant,
          index: idx,
        },
        maximised: true,
        componentType: SubvariantExplorerComponent.componentName,
      };

      this._goldenLayout.addItemAtLocation(itemConfig, LocationSelectors);
      componentItem = this._goldenLayout.findFirstComponentItemById(id);
      this._subvariantcomponentItemsMap.set(id, componentItem);

      // Keep the stack maximized
      if (currently_maximized) {
        const stack = componentItem.container.parent.parent as Stack;
        stack.toggleMaximise();
      }

      variantExplorerItem.focus();
    }
  }

  /**
   * Create subvariant tab
   * @param clusterId id of the cluster
   * @param idx position in the cluster
   * @param variant_id id of the variant
   */
  createVariantInfoView(clusterId, idx, variant_id) {
    // find variant by id
    let variant = _.find(
      this.displayed_variants,
      (variant) => variant_id === variant.id
    );
    const currently_maximized = this.maximized;
    const LocationSelectors: LayoutManager.LocationSelector[] = [
      {
        typeId: LayoutManager.LocationSelector.TypeId.FocusedStack,
        index: undefined,
      },
    ];
    this.cleanUpSubVariantMap();

    const id = VariantInfoExplorerComponent.componentName + variant_id;

    let componentItem = this._subvariantcomponentItemsMap.get(id);
    // Check if the component item reference already is stored and if the item still exists
    // Saves on a search by ID
    if (componentItem) {
      componentItem.focus();
      // Instantiate a new Subvariant Component for this variant if it did not exist or is closed
    } else {
      const variantExplorerItem = this._goldenLayout.findFirstComponentItemById(
        VariantExplorerComponent.componentName
      );
      variantExplorerItem.focus();
      const itemConfig: ComponentItemConfig = {
        id: id,
        type: 'component',
        title: 'Cases (Var.' + idx + ')',
        isClosable: true,
        reorderEnabled: true,
        componentState: {
          variant: variant,
          index: idx,
          clusterId: clusterId,
          variant_id: variant_id,
        },
        maximised: true,
        componentType: VariantInfoExplorerComponent.componentName,
      };
      this._goldenLayout.addItemAtLocation(itemConfig, LocationSelectors); //erroe here
      componentItem = this._goldenLayout.findFirstComponentItemById(id);
      this._subvariantcomponentItemsMap.set(id, componentItem);
      // Keep the stack maximized
      if (currently_maximized) {
        const stack = componentItem.container.parent.parent as Stack;
        stack.toggleMaximise();
      }

      variantExplorerItem.focus();
    }
  }

  closeAllSubvariantWindows(): void {
    this._subvariantcomponentItemsMap.forEach((value) => {
      if (
        value &&
        this._goldenLayoutHostComponent.getComponentRef(value.container)
      ) {
        value.close();
      }
    });

    // Reset the Map to empty
    this._subvariantcomponentItemsMap = new Map<string, ComponentItem>();
  }

  updateAllSubvariantWindows(): void {
    this._subvariantcomponentItemsMap.forEach((value) => {
      if (value) {
        value.setTitle('Sub-Variant');
      }
    });

    for (let index = 0; index < this.displayed_variants.length; index++) {
      const id =
        SubvariantExplorerComponent.componentName +
        this.displayed_variants[index].id;
      let componentItem = this._subvariantcomponentItemsMap.get(id);
      if (componentItem) {
        componentItem.setTitle('Sub-Variants for ' + (index + 1));
        let c = componentItem.component as SubvariantExplorerComponent;
        c.setIndex(index + 1);
      }
    }
  }

  cleanUpSubVariantMap() {
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
  }

  getSelectedVariants(): Variant[] {
    return this.variants.filter((v) => v.isSelected);
  }

  isAnyVariantOutdated(variants: Variant[]): boolean {
    return variants.some((v) => v.isConformanceOutdated);
  }

  isConformanceOutdated(): boolean {
    return this.isAnyVariantOutdated(this.variants);
  }

  isAlignmentCalculationInProgress(): boolean {
    return this.variants.some((v) => v.calculationInProgress);
  }

  addSelectedVariantsToModelForOutdatedConformance(
    selectedVariants: Variant[]
  ): void {
    this.backendService
      .addConcurrencyVariantsToProcessModelForUnknownConformance(
        selectedVariants
      )
      .pipe(takeUntil(this._destroy$))
      .subscribe((tree) => {
        this.refreshConformanceIconsAfterModelChange(false, tree);
      });
  }

  addSelectedVariantsToModelForGivenConformance(
    selectedVariants: Variant[]
  ): void {
    const fittingVariants = selectedVariants
      .filter((v) => v.deviations == 0)
      .map((v) => v);
    const variantsToAdd = selectedVariants
      .filter((v) => v.deviations > 0)
      .map((v) => v);

    this.backendService
      .addConcurrencyVariantsToProcessModel(variantsToAdd, fittingVariants)
      .pipe(takeUntil(this._destroy$))
      .subscribe((tree) => {
        this.refreshConformanceIconsAfterModelChange(false, tree);
      });
  }

  refreshConformanceIconsAfterModelChange(
    wasInitialDiscovery: boolean,
    pt: ProcessTree
  ): void {
    if (wasInitialDiscovery) {
      this.variants.forEach((v) => {
        v.deviations = undefined;
        v.calculationInProgress = false;
        v.usedTreeForConformanceChecking = undefined;
        v.isConformanceOutdated = true;
      });
    }

    this.getSelectedVariants().forEach((v) => {
      v.isAddedFittingVariant = true;
      v.deviations = 0;
      // Make variant as fitting alignment
      v.alignment = v.variant;
      v.alignment.updateConformance(1);
      v.usedTreeForConformanceChecking = pt;

      v.calculationInProgress = false;
      v.isConformanceOutdated = false;
      v.isTimeouted = false;
    });

    // redraw if in conformance view
    if (this.variantViewModeService.viewMode === ViewMode.CONFORMANCE)
      this.getSelectedVariants().forEach((v) => {
        this.variantVisualisations
          .find((vv) => vv.id == v.id)
          .variantDrawer.redraw();
      });
  }

  isAnyVariantSelected(): boolean {
    return this.variants.some((v) => v.isSelected);
  }

  isNoVariantSelected(): boolean {
    return !this.isAnyVariantSelected();
  }

  isInfixSelected(): boolean {
    return this.variants.some(
      (v) => v.isSelected && v.infixType !== InfixType.NOT_AN_INFIX
    );
  }

  areAllDisplayedVariantsSelected(): boolean {
    return this.displayed_variants.every((v) => v.isSelected);
  }

  unSelectAllChanged(isSelected: boolean): void {
    this.displayed_variants.forEach((v) => (v.isSelected = isSelected));
  }

  areAllVariantsExpanded(): boolean {
    if (
      this.variantVisualisations === undefined ||
      (this.variants && this.variants.length < 1)
    ) {
      return false;
    }

    const unexpandedVariantsExist = this.variants.some(
      (v) => !v.variant.expanded
    );
    return !unexpandedVariantsExist;
  }

  expandCollapseAll(): void {
    const shouldExpand = !this.areAllVariantsExpanded();

    this.variantVisualisations.forEach((vv) => {
      if (
        this.variantViewModeService.viewMode !== ViewMode.PERFORMANCE &&
        shouldExpand != vv.variantDrawer.variant.variant.expanded
      ) {
        vv.variantDrawer.setExpanded(shouldExpand);
        vv.variantDrawer.redraw();
        if (vv.arcsViewMode !== ArcsViewMode.HIDE_ALL) {
          vv.drawArcs();
        }
      }
    });

    // Necessary, because there are only variant drawers for children that are rendered.
    // This is often only a subset of variants because of lazy loading.
    this.variants.forEach((v) => v.variant.setExpanded(shouldExpand));
  }

  handleResponsiveChange(
    left: number,
    top: number,
    width: number,
    height: number
  ): void {
    this.collapse = width < 875;

    this.sidebarHeight = height;
  }

  handleVisibilityChange(visibility: boolean): void {}

  handleZIndexChange(
    logicalZIndex: LogicalZIndex,
    defaultZIndex: string
  ): void {
    this.maximized = logicalZIndex === 'stackMaximised';
  }

  meanPerformance(): string {
    let p = this.performanceService.mergedTreePerformance?.performance;
    let selectedScale = this.performanceColorService.selectedColorScale;
    let pValue =
      p[selectedScale.performanceIndicator]?.[selectedScale.statistic];
    return HumanizeDurationPipe.apply(pValue * 1000, { round: true });
  }

  variantPerformanceColor(): string {
    let tree = this.performanceService.mergedTreePerformance;
    if (!tree) {
      return null;
    }
    let selectedScale = this.performanceColorService.selectedColorScale;
    const colorScale = this.performanceColorService
      .getVariantComparisonColorScale()
      .get(tree.id);
    if (
      colorScale &&
      tree.performance?.[selectedScale.performanceIndicator]?.[
        selectedScale.statistic
      ] !== undefined
    ) {
      return colorScale.getColor(
        tree.performance[selectedScale.performanceIndicator][
          selectedScale.statistic
        ]
      );
    }
    return '#d3d3d3';
  }

  textColorForBackgroundColor(): string {
    if (this.variantPerformanceColor() === null) {
      return 'white';
    }
    return textColorForBackgroundColor(this.variantPerformanceColor());
  }

  toggleQueryInfo(event: Event): void {
    this.openDocumentation('Variant Querying');
    // this.showQueryInfo = !this.showQueryInfo;
    event.stopPropagation();
  }

  openDocumentation(heading: string) {
    this.documentationService.showDocumentationDialog(heading);
  }

  toggleBlur(event) {
    this.variantExplorerOutOfFocus = event;
  }

  toggleQueryFilterDialog() {
    this.queryActive = !this.queryActive;
  }

  filterToggle = true; // true by default (i.e. displayed activities are filtered)
  toggleAppliedQueryFilter() {
    // toggle the query filter...
    if (this.filterToggle) {
      this.variantFilterService.variantFilters = this.filterMap;
    } else {
      this.displayed_variants = this.variants;
      this.variants.forEach((v) => (v.isDisplayed = true));
    }

    this.updateAllSubvariantWindows();
    this.redraw_components();
  }

  sort(sortingFeature: string): void {
    this.sortingFeature = sortingFeature;
    // -1 is the keys of the default cluster (when no clustering was applied)
    this.clusterSortSettings[-1] = {
      feature: sortingFeature,
      isAscendingOrder: this.isAscendingOrder,
    };
    this.variantExplorerDiv.nativeElement.scroll(0, 0);
    this.updateAllSubvariantWindows();
    // to avoid expression changed after checked error
    this.changeDetectorRef.detectChanges();

    if (this.variantService.clusteringConfig) {
      this.sortAllClusters(sortingFeature);
    }
  }

  onSortOrderChanged(isAscending: boolean): void {
    this.isAscendingOrder = isAscending;
    this.sort(this.sortingFeature);
  }

  toggleTraceInfixSelectionMode(): void {
    this.traceInfixSelectionMode = !this.traceInfixSelectionMode;
    this.redraw_components();
  }

  onGranularityChange(granularity): void {
    if (this.processTreeService.currentDisplayedProcessTree)
      this.performanceService.hideTreePerformance();

    this.selectedGranularity = granularity;
    this.backendService
      .getLogPropsAndUpdateState(granularity, this.logService.loadedEventLog)
      .pipe(takeUntil(this._destroy$))
      .subscribe();
  }

  listenForLogGranularityChange() {
    this.logService.logGranularity$
      .pipe(takeUntil(this._destroy$))
      .subscribe((granularity) => {
        this.selectedGranularity = granularity;
        this.variantService.areVariantLoopsCollapsed = false;
      });
  }

  onScroll(): void {}

  executeRemovalActionOnFilteredVariants(removeFiltered: boolean): void {
    let bids = [];
    let infoText = '';
    if (removeFiltered) {
      // remove all filtered variants
      bids = this.displayed_variants.map((v) => v.bid);
      infoText = 'Removed all filtered variants. Filters are cleared.';
    } else {
      // keep only filtered variants
      bids = this.variants.filter((v) => !v.isDisplayed).map((v) => v.bid);
      infoText = 'Removed all not filtered variants. Filters are cleared.';
    }

    this.variantService.deleteVariants(bids).subscribe();

    for (let filter of this.filterMap.keys()) {
      this.removeFilter(filter);
    }

    this.toastService.showSuccessToast(
      'Variants removed',
      infoText,
      'bi-trash'
    );
  }

  private listenForViewModeChange() {
    this.variantViewModeService.viewMode$
      .pipe(takeUntil(this._destroy$))
      .subscribe((viewMode) => {
        if (viewMode !== ViewMode.STANDARD && this.traceInfixSelectionMode)
          this.toggleTraceInfixSelectionMode();
      });
  }

  private listenForLoopCollapsedVariantsChange() {
    this.variantService.collapsedVariants$
      .pipe(takeUntil(this._destroy$))
      .subscribe((variants) => {
        if (variants !== null) {
          this.traceInfixSelectionMode = false;
          this.displayed_variants = variants;
          this.sort(this.sortingFeature);
        } else {
          this.displayed_variants = this.variants;
        }
      });
  }

  openClusteringSettingsDialog() {
    const clusteringModel = this.modalService.open(
      ClusteringSettingsDialogComponent,
      {
        ariaLabelledBy: 'modal-basic-title',
      }
    );

    clusteringModel.componentInstance.numberOfVariants = this.variants.length;
  }

  openConstraintOverview(): void {
    const modal = this.modalService.open(ConstraintOverviewDialogComponent, {
      size: 'lg',
      centered: true,
    });
    modal.componentInstance.mustLink = this.constraintService.mustLink;
    modal.componentInstance.cannotLink = this.constraintService.cannotLink;
  }

  addMustLink(): void {
    const selected = this.getSelectedVariants();
    if (selected.length !== 2) return;
    const error = this.constraintService.addMustLink(selected[0].bid, selected[1].bid);
    if (error) {
      this.toastService.showWarningToast('Constraint conflict', error, 'bi-exclamation-triangle');
      return;
    }
    selected.forEach((v) => (v.isSelected = false));
  }

  addCannotLink(): void {
    const selected = this.getSelectedVariants();
    if (selected.length !== 2) return;
    const error = this.constraintService.addCannotLink(selected[0].bid, selected[1].bid);
    if (error) {
      this.toastService.showWarningToast('Constraint conflict', error, 'bi-exclamation-triangle');
      return;
    }
    selected.forEach((v) => (v.isSelected = false));
  }

  hasMustLink(bid: number): boolean {
    return this.constraintService.mustLink.some(([a, b]) => a === bid || b === bid);
  }

  hasCannotLink(bid: number): boolean {
    return this.constraintService.cannotLink.some(([a, b]) => a === bid || b === bid);
  }

  getMustLinkTooltip(bid: number): string {
    const partners = this.constraintService.mustLink
      .filter(([a, b]) => a === bid || b === bid)
      .map(([a, b]) => (a === bid ? b : a))
      .sort((x, y) => x - y)
      .map(n => `#${n + 1}`);
    return `must-link with: ${partners.join(', ')}`;
  }

  getCannotLinkTooltip(bid: number): string {
    const partners = this.constraintService.cannotLink
      .filter(([a, b]) => a === bid || b === bid)
      .map(([a, b]) => (a === bid ? b : a))
      .sort((x, y) => x - y)
      .map(n => `#${n + 1}`);
    return `cannot-link with: ${partners.join(', ')}`;
  }

  public hrrHeaders = new Map<number, HRRClusterHeader>();

  compareClusterIds = (a, b) => Number(a.key) - Number(b.key);

  private listenForHRRClusteringResult() {
    combineLatest([
      this.hrrClusteringService.result$,
      this.hrrClusteringService.changes$,
    ])
      .pipe(takeUntil(this._destroy$))
      .subscribe(([result, changes]) => this.updateHRRHeaders(result, changes));

    // a new clustering starts with every cluster closed
    this.hrrClusteringService.result$
      .pipe(takeUntil(this._destroy$))
      .subscribe((result) => {
        if (result?.fromScratch && !this.hrrClusteringService.restored) {
          this.hideRuleContent = new Array(result.clusters.length + 1).fill(true);
        }
      });
  }

  private updateHRRHeaders(
    result: HRRClusteringResult,
    changes: Map<number, [number, number]>
  ) {
    this.hrrHeaders = new Map();
    if (!result) return;

    const variantOf = new Map(this.variantService.variants.map((v) => [v.bid, v]));
    result.clusters.forEach((members, c) => {
      const info = result.info[c];
      const change = changes.get(c);
      this.hrrHeaders.set(c, {
        label: `Cluster ${c + 1}`,
        typical: this.copyVariant(variantOf.get(members[0])),
        color: this.skeletonColor(info, result.canonical),
        why: this.whyText(info),
        changes: change
          ? `Since the last change: +${change[0]} in, ${change[1]} out`
          : null,
      });
    });
    this.hrrHeaders.set(result.clusters.length, {
      label: 'No activity left after the edits',
      typical: null,
      color: null,
      why: '',
      changes: null,
    });
  }

  private copyVariant(variant: Variant): Variant {
    const copy = Object.assign(Object.create(Object.getPrototypeOf(variant)), variant);
    copy.variant = deserialize(variant.variant.serialize());
    return copy;
  }

  private skeletonColor(info: HRRClusterInfo, canonical: { [a: string]: string }) {
    const apart = new Set(
      info.why.filter((w) => w.moreCommonHere).map((w) => w.activity)
    );
    return (self, element: VariantElement, variant: Variant) => {
      if (!(element instanceof LeafNode)) return undefined;
      const activity = element.asLeafNode().activity[0];
      const shown =
        !this.hrrClusteringService.isIgnored(activity) &&
        apart.has(canonical[activity] ?? activity);
      return shown ? this.colorMap.get(activity) : '#d3d3d3'; // lightgray
    };
  }

  private whyText(info: HRRClusterInfo): string {
    if (info.why.length === 0) {
      return 'No single activity sets it apart';
    }
    const percent = (n: number, of: number) => `${Math.round((100 * n) / of)}%`;
    const list = (more: boolean) =>
      info.why
        .filter((w) => w.moreCommonHere === more)
        .map(
          (w) =>
            `${w.activity} ${percent(w.here, info.size)} vs ${percent(w.elsewhere, info.rest)}`
        )
        .join(', ');
    return [
      [true, 'More common here than elsewhere: '],
      [false, 'Less common here than elsewhere: '],
    ]
      .filter(([more]) => list(more as boolean))
      .map(([more, label]) => label + list(more as boolean))
      .join('; ');
  }

  handleClusterSort(sortEvent, clusterId) {
    this.clusterSortSettings[clusterId] = sortEvent;
    this.updateAllSubvariantWindows();
    // detect changes manually to avoid expression changed after checked
    this.changeDetectorRef.detectChanges();
  }

  sortAllClusters(sortingFeature: string) {
    const numOfClusters = Math.max(
      ...this.displayed_variants.map((o) => o.clusterId)
    );

    for (let i = 0; i <= numOfClusters; i++) {
      this.clusterSortSettings[i] = {
        feature: sortingFeature,
        isAscendingOrder: this.isAscendingOrder,
      };
    }

    // -1 is the keys of the default cluster (when no clustering was applied)
    this.clusterSortSettings[-1] = {
      feature: sortingFeature,
      isAscendingOrder: this.isAscendingOrder,
    };
  }

  calculateTotalTracesInCluster(cluster) {
    const count = cluster.reduce((a, b) => +a + +b.count, 0);
    return count;
  }

  showVariantSequentializerDialog() {
    this.variantService.showVariantSequentializerDialog.next();
  }

  handleTreeConformanceClear() {
    this.conformanceCheckingService.hideTreeConformance();
  }

  performanceColumnHeader() {
    const selectedColorScale = this.performanceColorService.selectedColorScale;
    return `${selectedColorScale.performanceIndicator}\n(${selectedColorScale.statistic})`;
  }

  setupVariantVisualisationForArcDiagrams(
    variantViz: VariantVisualisationComponent,
    computedArcs: Pair[]
  ) {
    const { maxDistance } = variantViz.arcDiagram.parseInput(computedArcs);
    this.arcsMaxValues = {
      ...this.arcsMaxValues,
      distance: Math.max(maxDistance, this.arcsMaxValues.distance),
    };
    this.filterParams.distanceRange.options.ceil = Math.max(
      this.filterParams.distanceRange.high,
      this.arcsMaxValues.distance
    );
    this.filterParams.lengthRange.options.ceil = Math.max(
      this.filterParams.lengthRange.high,
      this.arcsMaxValues.length
    );
    this.filterParams.sizeRange.options.ceil = Math.max(
      this.filterParams.sizeRange.high,
      this.arcsMaxValues.size
    );

    return variantViz;
  }

  subscribeForArcDiagramsComputationsResults() {
    this.arcDiagramService.arcDiagramsResult
      .pipe(takeUntil(this._destroy$))
      .subscribe((res: ArcDiagramComputationResult) => {
        this.arcsMaxValues = {
          ...this.arcsMaxValues,
          size: Math.max(res.maximal_values.size, this.arcsMaxValues.size),
          length: Math.max(
            res.maximal_values.length,
            this.arcsMaxValues.length
          ),
        };
        for (let [bid, pairs] of Object.entries(res['pairs'])) {
          this.arcsCache[bid] = pairs;
          const variantViz: VariantVisualisationComponent =
            this.variantVisualisations.find(
              (vv: VariantVisualisationComponent) =>
                vv.bid == (bid as unknown as number)
            );
          if (variantViz) {
            this.setupVariantVisualisationForArcDiagrams(
              variantViz,
              pairs
            ).drawArcs(this.filterParams);
          }
        }
      });
  }

  showSingleArcDiagram(bids: string[] | number[]) {
    this.arcsViewMode = ArcsViewMode.SHOW_SOME;
    this.computeAndDrawArcDiagram(bids);
  }

  computeAndDrawArcDiagram(bids: string[] | number[]) {
    let resubscribe = this.arcDiagramService.computeArcDiagrams(
      bids,
      this.filterParams
    );
    if (resubscribe) {
      this.subscribeForArcDiagramsComputationsResults();
    }
  }

  filterArcDiagrams(filterParams: FilterParams) {
    this.filtering = true;
    this.filterParams = _.cloneDeep(filterParams);
    this.computeAndDrawArcDiagram(Object.keys(this.arcsCache));
    this.lastArcsActivitiesFilter = new Set(
      filterParams.activitiesSelection.selectedItems
    );
  }

  newActivitiesLoaded(newActivities: Set<string>) {
    this.lastArcsActivitiesFilter = new Set(newActivities);
  }

  toggleArcsVisibility() {
    if (
      this.arcsViewMode == ArcsViewMode.SHOW_ALL ||
      this.arcsViewMode == ArcsViewMode.SHOW_SOME
    ) {
      this.arcsViewMode = ArcsViewMode.HIDE_ALL;
      this.variantVisualisations.forEach((vv) =>
        this.renderer.setStyle(
          vv.arcDiagram.svgHtmlElement.nativeElement,
          'display',
          'none'
        )
      );
    } else {
      this.arcsViewMode = ArcsViewMode.SHOW_ALL;

      const paramsObs = from(
        Array(Math.ceil(this.variants.length / 30))
          .fill(0)
          .map((_, idx) =>
            this.variants.slice(30 * idx, 30 * (idx + 1)).map((v) => v.bid)
          )
      );

      paramsObs
        .pipe(
          takeUntil(this._destroy$),
          concatMap(async (param) => this.computeAndDrawArcDiagram(param))
        )
        .subscribe();
    }
  }

  protected readonly ArcsViewMode = ArcsViewMode;
}

export namespace VariantExplorerComponent {
  export const componentName = 'VariantExplorerComponent';
}
