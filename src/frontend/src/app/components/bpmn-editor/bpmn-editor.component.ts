import { ProcessTreeService } from './../../services/processTreeService/process-tree.service';
import { Subject } from 'rxjs';
import { ColorMapService } from 'src/app/services/colorMapService/color-map.service';
import {
  Component,
  ElementRef,
  Inject,
  OnInit,
  Renderer2,
  ViewChild,
  AfterViewInit,
  OnDestroy,
} from '@angular/core';
import * as d3 from 'd3';
import { ComponentContainer, LogicalZIndex } from 'golden-layout';

import {
  ProcessTree,
  ProcessTreeOperator,
} from 'src/app/objects/ProcessTree/ProcessTree';
import { ModelPerformanceColorScaleService } from 'src/app/services/performance-color-scale.service';
import { ImageExportService } from 'src/app/services/imageExportService/image-export-service';
import { PerformanceService } from 'src/app/services/performance.service';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { BPMN_Constant } from 'src/app/constants/bpmn_model_drawer_constants';
import { BpmnDrawerDirective } from 'src/app/directives/bpmn-drawer/bpmn-drawer.directive';
import { getPerformanceTable } from '../process-tree-editor/utils';
import { textColorForBackgroundColor } from 'src/app/utils/render-utils';
import { takeUntil } from 'rxjs/operators';
import { ModelViewModeService } from 'src/app/services/viewModeServices/model-view-mode.service';
import { ViewMode } from 'src/app/objects/ViewMode';
import { ConformanceCheckingService } from 'src/app/services/conformanceChecking/conformance-checking.service';

@Component({
  selector: 'app-bpmn-editor',
  templateUrl: './bpmn-editor.component.html',
  styleUrls: ['./bpmn-editor.component.css'],
})
export class BpmnEditorComponent
  extends LayoutChangeDirective
  implements OnInit, AfterViewInit, OnDestroy
{
  selectedNode: any;
  currentTree: ProcessTree;

  activityColorMap: Map<string, string>;
  performanceColorMap: Map<number, any>;

  nodeWidthCache = new Map<string, number>();
  selectedRootID: number;

  @ViewChild('bpmn') svgElem: ElementRef;
  @ViewChild('BPMNcontainer') bpmnContainerElem: ElementRef;
  @ViewChild(BpmnDrawerDirective) bpmnDrawer: BpmnDrawerDirective;

  mainGroup: d3.Selection<SVGGElement, any, any, any>;
  selectedStatistic: string;
  selectedPerformanceIndicator: string;
  zoom: d3.ZoomBehavior<Element, unknown>;

  treeCacheLength: number = 0;
  treeCacheIndex: number = 0;

  private _destroy$ = new Subject();

  constructor(
    @Inject(LayoutChangeDirective.GoldenLayoutContainerInjectionToken)
    private container: ComponentContainer,
    elRef: ElementRef,
    private renderer: Renderer2,
    private colorMapService: ColorMapService,
    private performanceColorScaleService: ModelPerformanceColorScaleService,
    private performanceService: PerformanceService,
    private processTreeService: ProcessTreeService,
    private imageExportService: ImageExportService,
    private modelViewModeService: ModelViewModeService,
    private conformanceCheckingService: ConformanceCheckingService
  ) {
    super(elRef.nativeElement, renderer);
    const state = this.container.initialState;
  }

  ngOnInit(): void {
    this.processTreeService.nodeWidthCache$
      .pipe(takeUntil(this._destroy$))
      .subscribe((cache) => {
        this.nodeWidthCache = cache;
      });

    this.processTreeService.treeCacheIndex$
      .pipe(takeUntil(this._destroy$))
      .subscribe((idx) => {
        this.treeCacheIndex = idx;
      });

    this.processTreeService.treeCacheLength$
      .pipe(takeUntil(this._destroy$))
      .subscribe((len) => {
        this.treeCacheLength = len;
      });
  }

  ngAfterViewInit(): void {
    this.nodeWidthCache = this.processTreeService.nodeWidthCache;

    this.modelViewModeService.viewMode$
      .pipe(takeUntil(this._destroy$))
      .subscribe((viewMode) => {
        if (this.currentTree) {
          this.redraw(this.currentTree);
        }
      });

    this.conformanceCheckingService.isConformanceWeighted$
      .pipe(takeUntil(this._destroy$))
      .subscribe((_) => {
        if (this.currentTree) {
          this.redraw(this.currentTree);
        }
      });

    this.mainGroup = d3.select('#bpmn-zoom-group');

    this.createArrowHeadMarker();

    this.addZoomFunctionality();

    this.colorMapService.colorMap$
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        this.activityColorMap = colorMap;

        if (this.currentTree) {
          this.redraw(this.currentTree);
        }
      });

    this.performanceColorScaleService.currentColorScale
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        if (colorMap && colorMap != this.performanceColorMap) {
          this.performanceColorMap = colorMap;

          if (this.currentTree) {
            this.redraw(this.currentTree);
          }
        }
      });

    this.processTreeService.currentDisplayedProcessTree$
      .pipe(takeUntil(this._destroy$))
      .subscribe((tree) => {
        this.currentTree = tree;
        this.redraw(tree);
        this.reset_zoom(false);
      });

    this.processTreeService.selectedRootNodeID$
      .pipe(takeUntil(this._destroy$))
      .subscribe((id) => {
        if (id) {
          this.selectBPMNNode(id);
        } else {
          this.unselectAll();
        }

        this.selectedRootID = id;
      });
  }

  selectNodeCallBack = (self, event: PointerEvent, d) => {
    // hide the tooltip
    if (self.variantService.activityTooltipReference) {
      self.variantService.activityTooltipReference.tooltip('hide');
    }

    event.stopPropagation();
    event.preventDefault();

    if (d.id === this.selectedRootID) {
      this.processTreeService.selectedRootNodeID = null;
      this.processTreeService.selectedTree = undefined;
    } else {
      this.processTreeService.selectedRootNodeID = d.id;
      this.processTreeService.selectedTree = ProcessTree.fromObj(d);
    }
  };

  createArrowHeadMarker() {
    const marker_colors = {
      'arrow-grey': BPMN_Constant.STROKE_COLOR,
      'arrow-red': 'red',
      'arrow-frozen': '#425bbf',
    };

    for (const [marker_id, fill_color] of Object.entries(marker_colors)) {
      d3.select(this.svgElem.nativeElement)
        .append('svg:defs')
        .append('svg:marker')
        .attr('id', marker_id)
        .attr('viewBox', '-1 -2 4 4')
        .attr('refX', 0)
        .attr('refY', 0)
        .attr('markerWidth', BPMN_Constant.ARROW_LENGTH)
        .attr('markerHeight', '100%')
        .attr('orient', 'auto')
        .attr('markerUnits', 'userSpaceOnUse')
        .append('polygon')
        .attr('points', '-1,-2 3,0 -1,2 0,0')
        .attr('fill', fill_color);
    }
  }

  redraw(tree: ProcessTree) {
    this.selectedStatistic =
      this.performanceColorScaleService.selectedColorScale.statistic;
    this.selectedPerformanceIndicator =
      this.performanceColorScaleService.selectedColorScale.performanceIndicator;

    this.bpmnDrawer.redraw(tree);
    this.selectBPMNNode(this.selectedRootID);
  }

  tooltipContent = (d: ProcessTree) => {
    let returnTempValue = d.label || d.operator;

    const tableHead =
      `<div style="display: flex; justify-content: space-between; border-radius: 5px 5px 0px 0px;" class="bg-dark">
        <h6 style="flex: 1; margin-top: 8px;">` +
      (d.label || d.operator) +
      `</h6>
      </div>`;

    if (
      this.modelViewModeService.viewMode === ViewMode.PERFORMANCE &&
      d.hasPerformance() &&
      d.label !== ProcessTreeOperator.tau
    ) {
      returnTempValue =
        tableHead +
        getPerformanceTable(
          d.performance,
          this.selectedPerformanceIndicator,
          this.selectedStatistic
        );
    } else if (
      this.modelViewModeService.viewMode === ViewMode.CONFORMANCE &&
      d.conformance !== null
    ) {
      returnTempValue =
        tableHead +
        `<table class="table table-dark table-striped table-bordered">
          <tr>
            <td>Weighted</td>
            <td>Conformance</td>
            <td>Weight</td>
          </tr>` +
        `<tr>
            <td>Equally</td>
            <td>${(d.conformance?.weighted_equally.value * 100).toFixed(
              2
            )}%</td>
            <td>${d.conformance?.weighted_equally.weight}</td>
        </tr>` +
        (d.conformance?.weighted_by_counts !== null
          ? `<tr>
            <td>By Log Frequency</td>
            <td>${(d.conformance?.weighted_by_counts?.value * 100).toFixed(
              2
            )}%</td>
            <td>${d.conformance?.weighted_by_counts?.weight}</td>
        </tr>`
          : '') +
        '</table>';
    }

    return returnTempValue;
  };

  computeNodeColor = (pt: ProcessTree) => {
    let color;

    switch (this.modelViewModeService.viewMode) {
      case ViewMode.CONFORMANCE:
        if (pt.conformance === null) return '#404041';
        const conformanceValue =
          this.conformanceCheckingService.isConformanceWeighted &&
          pt.conformance?.weighted_by_counts != undefined
            ? pt.conformance?.weighted_by_counts.value
            : pt.conformance?.weighted_equally.value;
        if (conformanceValue === 0) return 'url(#modelConformanceStriped)';
        return this.conformanceCheckingService.modelConformanceColorMap.getColor(
          conformanceValue
        );
      case ViewMode.PERFORMANCE:
        if (
          this.performanceColorMap.has(pt.id) &&
          pt.performance?.[this.selectedPerformanceIndicator]?.[
            this.selectedStatistic
          ] !== undefined
        ) {
          if (
            pt.performance[this.selectedPerformanceIndicator][
              this.selectedStatistic
            ] === 0
          )
            return 'url(#whiteStriped)';
          else
            return this.performanceColorMap
              .get(pt.id)
              .getColor(
                pt.performance[this.selectedPerformanceIndicator][
                  this.selectedStatistic
                ]
              );
        } else {
          color = '#404040';
        }

        break;
      default:
        color =
          pt.label !== '\u03C4'
            ? this.activityColorMap.get(pt.label)
            : BPMN_Constant.INVISIBLE_ACTIVITIY_DEFAULT_COLOR;
        break;
    }

    return color;
  };

  computeTextColor = (pt: ProcessTree) => {
    return pt.label === ProcessTreeOperator.tau || pt.frozen
      ? 'White'
      : textColorForBackgroundColor(this.computeNodeColor(pt));
  };

  ngOnDestroy() {
    this._destroy$.next();
  }

  unselectAll() {
    this.mainGroup.classed('selected-bpmn-operator', false);

    this.mainGroup
      .selectAll('.selected-bpmn-event')
      .classed('selected-bpmn-event', false);
    this.mainGroup
      .selectAll('.selected-bpmn-operator')
      .classed('selected-bpmn-operator', false);
  }

  freezeSubtree() {
    this.processTreeService.freezeSubtree(this.selectedNode.datum());
  }

  buttonFreezeSubtreeDisabled() {
    return (
      this.selectedRootID == null ||
      (this.selectedNode && this.selectedNode.datum().children.length === 0)
    );
  }

  selectBPMNNode(id: number) {
    this.unselectAll();

    const selected_node = this.mainGroup.select('[id="' + id + '"]');
    if (!selected_node.empty()) {
      this.selectedNode = selected_node;
      if ((selected_node.datum() as ProcessTree).operator) {
        if (this.currentTree === selected_node.datum()) {
          this.mainGroup.classed('selected-bpmn-operator', true);
        } else {
          selected_node.classed('selected-bpmn-operator', true);
        }
      } else {
        selected_node.classed('selected-bpmn-event', true);
      }
    }
  }

  undo(): void {
    this.processTreeService.undo();
  }

  redo(): void {
    this.processTreeService.redo();
  }

  handleResponsiveChange(
    left: number,
    top: number,
    width: number,
    height: number
  ): void {}

  handleVisibilityChange(visibile: boolean): void {
    if (this.currentTree && visibile) {
      this.reset_zoom(false);
      this.redraw(this.currentTree);
    }
  }

  handleZIndexChange(
    logicalZIndex: LogicalZIndex,
    defaultZIndex: string
  ): void {}

  clearSelection() {
    this.processTreeService.selectedRootNodeID = null;
  }

  deleteSelected() {
    this.processTreeService.deleteSelected(this.selectedNode.datum());
  }

  addZoomFunctionality(): void {
    const zooming = function (event) {
      this.mainGroup.attr('transform', event.transform.translate(0, 0));
    }.bind(this);

    this.zoom = d3
      .zoom()
      .scaleExtent([BPMN_Constant.MIN_ZOOM, BPMN_Constant.MAX_ZOOM])
      .on('zoom', zooming);
    d3.select(this.svgElem.nativeElement)
      .call(this.zoom)
      .on('dblclick.zoom', null);
  }

  reset_zoom(animation: boolean = true): void {
    const rTime = animation ? 250 : 0;

    const bounds = this.mainGroup.node().getBBox();
    const editorZone = <any>this.mainGroup.node().parentElement;
    const svgWidth = editorZone.width.baseVal.value - 2 * BPMN_Constant.PADDING;
    const svgHeight =
      editorZone.height.baseVal.value - 2 * BPMN_Constant.PADDING;

    // Calculate the scale to fit the content within the SVG
    let scale = Math.min(svgWidth / bounds.width, svgHeight / bounds.height);
    scale = Math.min(scale, BPMN_Constant.DEFAULT_ZOOM);
    scale = Math.max(scale, BPMN_Constant.MIN_ZOOM);

    // Center SVG
    const translateX = (svgWidth - bounds.width * scale) / 2;
    const translateY = (svgHeight - bounds.height * scale) / 2;

    d3.select(this.svgElem.nativeElement)
      .transition()
      .duration(rTime)
      .ease(d3.easeExpInOut)
      .call(
        this.zoom.transform,
        d3.zoomIdentity.translate(translateX, translateY).scale(scale)
      );
  }

  exportBPMN(svg: SVGGraphicsElement): void {
    // Copy the current tree
    const bpmn_copy = svg.cloneNode(true) as SVGGraphicsElement;
    const svgBBox = (this.mainGroup.node() as SVGGraphicsElement).getBBox();

    // Strip all the classed information
    const bpmn = d3.select(bpmn_copy);

    bpmn
      .selectAll('g')
      .attr('data-bs-toggle', 'none')
      .attr('data-bs-placement', 'none')
      .attr('data-bs-title', 'none')
      .attr('data-bs-html', 'none')
      .attr('data-bs-template', 'none');

    // Reset origin and add padding
    bpmn
      .select('#bpmn-zoom-group')
      .attr(
        'transform',
        `translate(${BPMN_Constant.PADDING}, ${BPMN_Constant.PADDING})`
      );

    // Change Cortado colors of BPMN Nodes to black and white
    bpmn.selectAll('.BPMNOperatorNode').attr('fill', 'white');
    bpmn.selectAll('.BPMNOperatorText').attr('fill', 'black');

    // Export the BPMN
    this.imageExportService.export(
      'bpmn_diagram',
      svgBBox.width + 2 * BPMN_Constant.PADDING,
      svgBBox.height + 2 * BPMN_Constant.PADDING,
      bpmn_copy
    );
  }
}

export namespace BpmnEditorComponent {
  export const componentName = 'BpmnEditorComponent';
}
