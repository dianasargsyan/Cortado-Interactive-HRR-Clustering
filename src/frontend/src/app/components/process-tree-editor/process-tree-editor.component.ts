import { PT_Constant } from './../../constants/process_tree_drawer_constants';

import { GoldenLayoutHostComponent } from 'src/app/components/golden-layout-host/golden-layout-host.component';
import { GoldenLayoutComponentService } from 'src/app/services/goldenLayoutService/golden-layout-component.service';
import { BpmnEditorComponent } from './../bpmn-editor/bpmn-editor.component';
import { BackendService } from './../../services/backendService/backend.service';
import {
  Component,
  OnInit,
  ViewChild,
  AfterViewInit,
  ElementRef,
  Inject,
  Renderer2,
  OnDestroy,
} from '@angular/core';

import { ComponentContainer, GoldenLayout, LogicalZIndex } from 'golden-layout';
import * as d3 from 'd3';
import { ColorMapService } from '../../services/colorMapService/color-map.service';

import { ImageExportService } from '../../services/imageExportService/image-export-service';

declare var $;
import { PerformanceService } from 'src/app/services/performance.service';
import { ModelPerformanceColorScaleService } from 'src/app/services/performance-color-scale.service';

import {
  ProcessTree,
  ProcessTreeSyntaxInfo,
  checkSyntax,
  ProcessTreeOperator,
} from '../../objects/ProcessTree/ProcessTree';

import { DropzoneConfig } from '../drop-zone/drop-zone.component';
import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';

import { LogService } from 'src/app/services/logService/log.service';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { ProcessTreeDrawerDirective } from 'src/app/directives/process-tree-drawer/process-tree-drawer.directive';
import { getPerformanceTable } from './utils';
import { collapsingText } from 'src/app/animations/text-animations';
import { textColorForBackgroundColor } from 'src/app/utils/render-utils';
import { NodeInsertionStrategy } from 'src/app/objects/ProcessTree/utility-functions/process-tree-edit-tree';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ModelViewModeService } from 'src/app/services/viewModeServices/model-view-mode.service';
import { ViewMode } from 'src/app/objects/ViewMode';
import { ConformanceCheckingService } from 'src/app/services/conformanceChecking/conformance-checking.service';

@Component({
  selector: 'app-process-tree-editor',
  templateUrl: './process-tree-editor.component.html',
  styleUrls: ['./process-tree-editor.component.scss'],
  animations: [collapsingText],
})
export class ProcessTreeEditorComponent
  extends LayoutChangeDirective
  implements OnInit, AfterViewInit, OnDestroy
{
  selectedPerformanceIndicator: string;
  selectedStatistic: string;
  constructor(
    private colorMapService: ColorMapService,
    private imageExportService: ImageExportService,
    private backendService: BackendService,
    private logService: LogService,
    private goldenLayoutComponentService: GoldenLayoutComponentService,
    private performanceService: PerformanceService,
    private performanceColorScaleService: ModelPerformanceColorScaleService,
    private processTreeService: ProcessTreeService,
    private modelViewModeService: ModelViewModeService,
    private conformanceCheckingService: ConformanceCheckingService,
    private renderer: Renderer2,
    @Inject(LayoutChangeDirective.GoldenLayoutContainerInjectionToken)
    private container: ComponentContainer,
    elRef: ElementRef
  ) {
    super(elRef.nativeElement, renderer);
  }

  @ViewChild('d3svg') svgElem: ElementRef;
  @ViewChild('d3container') d3ContainerElem: ElementRef;

  @ViewChild(ProcessTreeDrawerDirective)
  processTreeDrawer: ProcessTreeDrawerDirective;

  currentlyDisplayedTreeInEditor;

  // used in dropdown search form
  searchText: string;

  processTreeSyntaxInfo: ProcessTreeSyntaxInfo = undefined;

  currentEditorHeight;

  svg;
  mainSvgGroup;
  nodeEnter;

  collapse: boolean = false;

  readonly NodeInsertionStrategy = NodeInsertionStrategy;
  nodeInsertionStrategy: NodeInsertionStrategy = NodeInsertionStrategy.ABOVE;
  lastNodeInsertionStrategy: NodeInsertionStrategy;

  selectedRootNodeId: number;
  selectedRootNode: d3.HierarchyNode<ProcessTree>;

  readonly disabledInsertPositions = {
    above: false,
    leftRight: false,
    below: false,
  };

  get disabledActivityInsertion() {
    if (
      this.nodeInsertionStrategy === NodeInsertionStrategy.ABOVE &&
      this.selectedRootNode?.data
    )
      return true;
    // Disable insertion when no node is selected but pt is present
    if (!this.selectedRootNode && this.currentlyDisplayedTreeInEditor)
      return true;
    return false;
  }

  get disabledOperatorInsertion() {
    // Disable insertion when no node is selected but pt is present
    if (!this.selectedRootNode && this.currentlyDisplayedTreeInEditor)
      return true;
    return false;
  }

  root: d3.HierarchyNode<any>;

  nodeWidthCache = new Map<string, number>();

  activityColorMap: Map<string, string>;
  performanceColorMap: Map<number, any>;
  editorOpen: boolean = false;
  _goldenLayoutHostComponent: GoldenLayoutHostComponent;
  _goldenLayout: GoldenLayout;

  tree_syntax_string: string;
  tree_syntax_result: any;

  treeCacheLength: number = 0;
  treeCacheIndex: number = 0;

  activitiesOccurringInLog: string[];

  private _destroy$ = new Subject();

  get processTreeOriginX() {
    return this.d3ContainerElem.nativeElement.offsetWidth / 2;
  }

  readonly processTreeOriginY = 30;

  ngOnInit(): void {
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

    this.modelViewModeService.viewMode$
      .pipe(takeUntil(this._destroy$))
      .subscribe((viewMode) => {
        if (this.currentlyDisplayedTreeInEditor) {
          this.redraw(this.currentlyDisplayedTreeInEditor);
        }
      });

    this.conformanceCheckingService.isConformanceWeighted$
      .pipe(takeUntil(this._destroy$))
      .subscribe((_) => {
        if (this.currentlyDisplayedTreeInEditor) {
          this.redraw(this.currentlyDisplayedTreeInEditor);
        }
      });

    this.colorMapService.colorMap$
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        this.activityColorMap = colorMap;

        if (this.currentlyDisplayedTreeInEditor) {
          this.redraw(this.currentlyDisplayedTreeInEditor);
        }
      });

    this.performanceColorScaleService.currentColorScale
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        if (colorMap && colorMap != this.performanceColorMap) {
          this.performanceColorMap = colorMap;
          this.redraw(this.currentlyDisplayedTreeInEditor);
        }
      });

    this.logService.activitiesInEventLog$
      .pipe(takeUntil(this._destroy$))
      .subscribe((activties) => {
        this.activitiesOccurringInLog = Object.keys(activties);
      });

    this.processTreeService.currentDisplayedProcessTree$
      .pipe(takeUntil(this._destroy$))
      .subscribe((res) => {
        const centerTree = !this.currentlyDisplayedTreeInEditor && !!res;
        // If the tree was loaded via the process tree import or Drag&Drop that does not contain the current activities
        this.currentlyDisplayedTreeInEditor = res;

        if (res) {
          console.warn('update tree triggered by service');

          this.processTreeSyntaxInfo = checkSyntax(res);
          this.processTreeService.correctTreeSyntax =
            this.processTreeSyntaxInfo.correctSyntax;
          this.redraw(res);
          if (centerTree) this.centerTree();
        } else if (res === null && this.mainSvgGroup) {
          this.processTreeDrawer.redraw(null);
          this.selectedRootNode = null;
        }
      });
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }

  redraw(tree) {
    this.selectedStatistic =
      this.performanceColorScaleService.selectedColorScale.statistic;
    this.selectedPerformanceIndicator =
      this.performanceColorScaleService.selectedColorScale.performanceIndicator;
    this.performanceColorMap =
      this.performanceColorScaleService.getColorScale();

    this.processTreeDrawer.redraw(tree);
    setTimeout(() => this.selectRootNodeFromID(this.selectedRootNodeId), 0);
  }

  ngAfterViewInit(): void {
    this._goldenLayoutHostComponent =
      this.goldenLayoutComponentService.goldenLayoutHostComponent;
    this._goldenLayout = this.goldenLayoutComponentService.goldenLayout;

    this.initializeSvg();

    this._goldenLayoutHostComponent =
      this.goldenLayoutComponentService.goldenLayoutHostComponent;
    this._goldenLayout = this.goldenLayoutComponentService.goldenLayout;

    this.processTreeService.selectedRootNodeID$
      .pipe(takeUntil(this._destroy$))
      .subscribe((id) => {
        // Change the Selection
        if (id) {
          this.selectRootNodeFromID(id); //the last one failed
          // Unselect all
        } else {
          this.clearDisplayedSelection();
        }

        this.selectedRootNodeId = id;
      });
  }

  private selectRootNodeFromID(id) {
    const selectedRoot = this.mainSvgGroup.select(`[id="${id}"]`);
    const node = selectedRoot.data()[0];
    if (id && node) {
      this.setSelectedRootNode(node);
      this.selectSubtreeFromRoot(selectedRoot.node(), node);

      this.checkNodeInsertionStrategy(this.selectedRootNode.data);
    }
  }

  handleResponsiveChange(
    left: number,
    top: number,
    width: number,
    height: number
  ): void {
    this.collapse = width < 970;

    this.currentEditorHeight = height;
  }

  handleVisibilityChange(visibile: boolean): void {
    if (visibile) {
      if (this.currentlyDisplayedTreeInEditor) {
        this.redraw(this.currentlyDisplayedTreeInEditor);
      }
    }
  }

  handleZIndexChange(
    logicalZIndex: LogicalZIndex,
    defaultZIndex: string
  ): void {}

  insertNewNodeButtonDisabled(): boolean {
    return (
      !this.selectedRootNode &&
      this.currentlyDisplayedTreeInEditor !== null &&
      this.currentlyDisplayedTreeInEditor !== undefined
    );
  }

  leafNodeSelected(): boolean {
    return this.selectedRootNode && !this.selectedRootNode.children;
  }

  rootNodeSelected(): boolean {
    return this.selectedRootNode && this.selectedRootNode.depth === 0;
  }

  get shiftSubtreeUpDisabled(): boolean {
    if (this.buttonManipulatingMultipleNodesDisabled()) return true;
    // Disabled if there is no granparent of the selected node
    if (!this.selectedRootNode.data.parent.parent) return true;
    return false;
  }

  get shiftSubtreeLeftDisabled(): boolean {
    if (this.buttonManipulatingMultipleNodesDisabled()) return true;
    const selectedNode = this.selectedRootNode.data;
    // Disabled when selected subtree already at leftmost position
    if (selectedNode.parent.children.indexOf(selectedNode) == 0) return true;
    return false;
  }

  get shiftSubtreeRightDisabled(): boolean {
    if (this.buttonManipulatingMultipleNodesDisabled()) return true;
    const selectedNode = this.selectedRootNode.data;
    // Disabled when selected subtree already at rightmost position
    if (
      selectedNode.parent.children.indexOf(selectedNode) ==
      selectedNode.parent.children.length - 1
    )
      return true;
    return false;
  }

  buttonManipulatingMultipleNodesDisabled(): boolean {
    return !this.selectedRootNode || this.rootNodeSelected();
  }

  buttonFreezeSubtreeDisabled(): boolean {
    return !this.selectedRootNode || this.leafNodeSelected();
  }

  shiftSubtreeUp(): void {
    this.processTreeService.shiftSubtreeUp(this.selectedRootNode.data);
  }

  shiftSubtreeToLeft(): void {
    this.processTreeService.shiftSubtreeToLeft(this.selectedRootNode.data);
  }

  shiftSubtreeToRight(): void {
    this.processTreeService.shiftSubtreeToRight(this.selectedRootNode.data);
  }

  get copyDisabled() {
    return !this.selectedRootNode;
  }

  copySubtree(): void {
    this.processTreeService.copySubtreeToBuffer(this.selectedRootNode.data);
  }

  cutSubtree(): void {
    this.processTreeService.copySubtreeToBuffer(this.selectedRootNode.data);
    this.processTreeService.deleteSelected(this.selectedRootNode.data);
  }

  get pasteDisabled() {
    return (
      !this.processTreeService.bufferedProcessTree ||
      (!this.selectedRootNode && this.currentlyDisplayedTreeInEditor) ||
      this.selectedRootNode?.data.label
    );
  }

  pasteSubtree(): void {
    this.processTreeService.pasteSubtreeFromBuffer(this.selectedRootNode?.data);
  }

  undo(): void {
    this.processTreeService.undo();
  }

  redo(): void {
    this.processTreeService.redo();
  }

  centerTree(): void {
    this.mainSvgGroup.attr(
      'transform',
      `translate(${this.processTreeOriginX}, ${this.processTreeOriginY})`
    );
  }

  deleteSubtree(): void {
    this.processTreeService.deleteSelected(this.selectedRootNode.data);
  }

  insertNewNode(operator, label) {
    this.processTreeService.insertNewNode(
      this.selectedRootNode?.data,
      this.nodeInsertionStrategy,
      operator,
      label
    );
    this.afterInsertNode();
  }

  afterInsertNode(): void {
    this.searchText = undefined;
  }

  // @REFRACTOR INTO PROCESSTREE SERVICE
  createNode(operator, label): d3.HierarchyNode<any> {
    // TODO make sure that IDs are unique!!!
    const nodeData = {
      operator,
      label,
      id: Math.floor(1000000000 + Math.random() * 900000000),
      children: [],
    };
    return d3.hierarchy(nodeData);
  }

  computeNodeColor = (d: d3.HierarchyNode<ProcessTree>) => {
    switch (this.modelViewModeService.viewMode) {
      case ViewMode.CONFORMANCE:
        if (d.data.conformance === null) return '#404041';
        const conformanceValue =
          this.conformanceCheckingService.isConformanceWeighted &&
          d.data.conformance?.weighted_by_counts != undefined
            ? d.data.conformance?.weighted_by_counts.value
            : d.data.conformance?.weighted_equally.value;
        if (conformanceValue === 0) return 'url(#modelConformanceStriped)';
        return this.conformanceCheckingService.modelConformanceColorMap.getColor(
          conformanceValue
        );
      case ViewMode.PERFORMANCE:
        if (d.data.label !== ProcessTreeOperator.tau) {
          if (
            this.performanceColorMap.has(d.data.id) &&
            d.data.performance?.[this.selectedPerformanceIndicator]?.[
              this.selectedStatistic
            ] !== undefined
          ) {
            if (
              d.data.performance[this.selectedPerformanceIndicator][
                this.selectedStatistic
              ] === 0
            )
              return 'url(#whiteStriped)';
            else
              return this.performanceColorMap
                .get(d.data.id)
                .getColor(
                  d.data.performance[this.selectedPerformanceIndicator][
                    this.selectedStatistic
                  ]
                );
          } else {
            return '#404040';
          }
        }
      default:
        if (d.data.operator !== null) return PT_Constant.OPERATOR_COLOR;
        if (d.data.label !== null && d.data.label === ProcessTreeOperator.tau)
          return PT_Constant.INVISIBLE_ACTIVTIY_COLOR;
        const isVisibleActivity =
          d.data.label !== null && d.data.label !== ProcessTreeOperator.tau;
        return isVisibleActivity
          ? this.activityColorMap.get(d.data.label)
          : null;
    }
  };

  tooltipContent = (d: d3.HierarchyNode<ProcessTree>) => {
    let returnTempValue = d.data.label || d.data.operator;

    const tableHead =
      `<div style="display: flex; justify-content: space-between; border-radius: 5px 5px 0px 0px;" class="bg-dark">
        <h6 style="flex: 1; margin-top: 8px;">` +
      (d.data.label || d.data.operator) +
      `</h6>
      </div>`;

    if (
      this.modelViewModeService.viewMode === ViewMode.PERFORMANCE &&
      d.data.hasPerformance() &&
      d.data.label !== ProcessTreeOperator.tau
    ) {
      returnTempValue =
        tableHead +
        getPerformanceTable(
          d.data.performance,
          this.selectedPerformanceIndicator,
          this.selectedStatistic
        );
    } else if (
      this.modelViewModeService.viewMode === ViewMode.CONFORMANCE &&
      d.data.conformance !== null
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
            <td>${(d.data.conformance?.weighted_equally.value * 100).toFixed(
              2
            )}%</td>
            <td>${d.data.conformance?.weighted_equally.weight}</td>
        </tr>` +
        (d.data.conformance?.weighted_by_counts !== null
          ? `<tr>
            <td>By Log Frequency</td>
            <td>${(d.data.conformance?.weighted_by_counts?.value * 100).toFixed(
              2
            )}%</td>
            <td>${d.data.conformance?.weighted_by_counts?.weight}</td>
        </tr>`
          : '') +
        '</table>';
    }

    return returnTempValue;
  };

  computeFillColor = (d: d3.HierarchyNode<ProcessTree>) => {
    if (d.data.operator !== null) return PT_Constant.OPERATOR_COLOR;
    if (d.data.label !== null && d.data.label === ProcessTreeOperator.tau)
      return PT_Constant.INVISIBLE_ACTIVTIY_COLOR;
    const isVisibleActivity =
      d.data.label !== null && d.data.label !== ProcessTreeOperator.tau;
    return isVisibleActivity
      ? this.activityColorMap.get(d.data.label) ||
          PT_Constant.VISIBILE_ACTIVITY_DEFAULT_COLOR
      : null;
  };

  computeTextColor = (d: d3.HierarchyNode<ProcessTree>) => {
    if (d.data.frozen || d.data.label === ProcessTreeOperator.tau) {
      return 'white';
    }
    const nodeColor = this.computeNodeColor(d);

    const isVisibleActivity =
      (d.data.label !== null && d.data.label !== ProcessTreeOperator.tau) ||
      (this.modelViewModeService.viewMode === ViewMode.PERFORMANCE &&
        nodeColor !== undefined) ||
      this.modelViewModeService.viewMode === ViewMode.CONFORMANCE;
    return isVisibleActivity ? textColorForBackgroundColor(nodeColor) : 'white';
  };

  // END - Inserting node functionality

  // Refactor to Directive with Variant Modeler / BPMN Viewer
  addZoomFunctionality(): void {
    const zooming = function (event) {
      this.mainSvgGroup.attr(
        'transform',
        event.transform.translate(
          this.processTreeOriginX,
          this.processTreeOriginY
        )
      );
    }.bind(this);

    const zoom: any = d3.zoom().scaleExtent([0.1, 3]).on('zoom', zooming);
    this.svg.call(zoom).on('dblclick.zoom', null);

    // reset zoom
    d3.select('#btn-reset-zoom').on(
      'click',
      function () {
        this.svg
          .transition()
          .duration(250)
          .ease(d3.easeExpInOut)
          .call(zoom.transform, d3.zoomIdentity.translate(0, 0));
      }.bind(this)
    );
  }

  selectNodeCallBack = (self, event, d: d3.HierarchyNode<ProcessTree>) => {
    // hide the tooltip
    if (self.variantService.activityTooltipReference) {
      self.variantService.activityTooltipReference.tooltip('hide');
    }
    // correct the selected node after undo
    if (d && d.data && d.parent) {
      d.data.parent = d.parent.data;
    }
    this.pushIDtoService(self, d);
    this.processTreeService.selectedTree = ProcessTree.fromObj(d.data);
  };

  private pushIDtoService = (svg, d) => {
    // Activate Toogle by pushing Null to service
    if (d.data.id !== this.selectedRootNodeId) {
      this.processTreeService.selectedRootNodeID = d.data.id;
    } else {
      this.processTreeService.selectedRootNodeID = null;
    }
  };

  private setSelectedRootNode(d) {
    this.selectedRootNode = d;
  }

  private selectSubtreeFromRoot = function (svgGroup, d) {
    // Unselect All Edges and Rect
    this.mainSvgGroup.selectAll('rect').each((d) => {
      d.data.selected = false;
    });

    this.mainSvgGroup.selectAll('rect').classed('selected-node', false);
    this.mainSvgGroup.selectAll('line').classed('selected-edge', false);

    // Select the node, if it isn't selected yet
    d.data.selected = true;

    d3.select(svgGroup).select('.node').classed('selected-node', true);
  };

  private selectAllChildren = function (svgGroup, d) {
    d.data.selected = true;
    d3.select(svgGroup).select('.node').classed('selected-node', true);

    if (!d.children) return;

    // add red stroke around sub-nodes if select subtree is selected
    d.children.forEach((c) => {
      this.selectAllChildren(
        this.mainSvgGroup.select('[id="' + c.data.id + '"]').node(),
        c
      );
    });
  };

  private selectEdges = function () {
    this.mainSvgGroup
      .selectAll('line')
      .classed('frozen-edge', (e) => {
        return e.source.data.frozen;
      })
      .classed('selected-edge', (e) => {
        return e.source.data.selected;
      });
  };

  freezeSubtree(): void {
    this.processTreeService.freezeSubtree(this.selectedRootNode.data);
  }

  clearSelection(): void {
    this.processTreeService.selectedRootNodeID = null;
  }

  clearDisplayedSelection(): void {
    this.selectedRootNode = null;
    this.processTreeService.selectedTree = undefined;

    this.mainSvgGroup.selectAll('rect').each((d) => {
      d.data.selected = false;
    });

    this.mainSvgGroup.selectAll('rect').classed('selected-node', false);
    this.mainSvgGroup.selectAll('line').classed('selected-edge', false);
  }

  applyReductionRules(): void {
    this.backendService.applyTreeReductionRules();
  }

  initializeSvg(): void {
    this.svg = d3.select('#d3-svg');
    // add svg group for zooming
    this.mainSvgGroup = this.svg.select('#zoomGroup');

    this.centerTree();
    this.addZoomFunctionality();
  }

  toggleBPMNEditor() {
    this.goldenLayoutComponentService.createBPMNSplitViewWindow(
      ProcessTreeEditorComponent.componentName,
      BpmnEditorComponent.componentName
    );
  }

  exportCurrentTree(svg: SVGGraphicsElement): void {
    // Copy the current tree
    const tree_copy = svg.cloneNode(true) as SVGGraphicsElement;
    const svgBBox = (
      d3.select('#zoomGroup').node() as SVGGraphicsElement
    ).getBBox();

    // Strip all the classed information
    const tree = d3.select(tree_copy);
    tree
      .selectAll('rect')
      .classed('.selected-node', false)
      .classed('.frozen-node', false);
    tree
      .selectAll('line')
      .classed('.selected-edge', false)
      .classed('.frozen-edge', false);

    tree
      .selectAll('g')
      .attr('data-bs-toggle', 'none')
      .attr('data-bs-placement', 'none')
      .attr('data-bs-title', 'none')
      .attr('data-bs-html', 'none')
      .attr('data-bs-template', 'none');

    const shiftbyXOffset = (node, offset, attrKey) => {
      return parseFloat(node.getAttribute(attrKey)) + offset;
    };

    // Recenter the tree and reset scaling
    let xCords: number[] = [];
    tree.selectAll('rect').each(function (this: SVGGraphicsElement) {
      xCords.push(parseFloat(this.getAttribute('x')));
    });

    const xLower = Math.min(...xCords);
    const xOffset = Math.abs(xLower) + PT_Constant.EXPORT_OFFSET;

    tree.selectAll('rect').attr('x', function (this: SVGGraphicsElement) {
      return shiftbyXOffset(this, xOffset, 'x');
    });
    tree.selectAll('text').attr('x', function (this: SVGGraphicsElement) {
      return shiftbyXOffset(this, xOffset, 'x');
    });
    tree
      .selectAll('line')
      .attr('x1', function (this: SVGGraphicsElement) {
        return shiftbyXOffset(this, xOffset, 'x1');
      })
      .attr('x2', function (this: SVGGraphicsElement) {
        return shiftbyXOffset(this, xOffset, 'x2');
      });

    tree
      .selectChild()
      .attr('transform', `translate(0, ${PT_Constant.EXPORT_OFFSET})`);

    // Export the tree
    this.imageExportService.export(
      'process_tree',
      svgBBox.width + 2 * PT_Constant.EXPORT_OFFSET,
      svgBBox.height + 2 * PT_Constant.EXPORT_OFFSET,
      tree_copy
    );
  }

  checkNodeInsertionStrategy(rootNode: ProcessTree) {
    this.disabledInsertPositions.leftRight = false;

    // Disable insertions above on non-root nodes
    this.disabledInsertPositions.above = rootNode.parent != null;
    // Disable insertions below non-operator nodes, i.e. activities
    this.disabledInsertPositions.below = rootNode.operator == null;
    // Disable insertions left/right of root node
    if (rootNode.parent == null) this.disabledInsertPositions.leftRight = true;
    // Disable insertions left/right of child from loop node that already has 2 childs
    if (
      rootNode.parent?.operator === ProcessTreeOperator.loop &&
      rootNode.parent?.children.length === 2
    )
      this.disabledInsertPositions.leftRight = true;
    // Disable insertions below redo node that has 2 childs
    if (
      rootNode.operator === ProcessTreeOperator.loop &&
      rootNode.children.length === 2
    )
      this.disabledInsertPositions.below = true;

    switch (this.nodeInsertionStrategy) {
      case NodeInsertionStrategy.ABOVE:
        if (this.disabledInsertPositions.above)
          this.nodeInsertionStrategy =
            this.getFirstAvailableNodeInsertionStrategy();
        break;
      case NodeInsertionStrategy.BELOW:
        if (this.disabledInsertPositions.below)
          this.nodeInsertionStrategy =
            this.getFirstAvailableNodeInsertionStrategy();
        break;
      case NodeInsertionStrategy.LEFT:
      case NodeInsertionStrategy.RIGHT:
        if (this.disabledInsertPositions.leftRight)
          this.nodeInsertionStrategy =
            this.getFirstAvailableNodeInsertionStrategy();
        break;
      case NodeInsertionStrategy.CHANGE:
        break;
      default:
        this.nodeInsertionStrategy =
          this.getFirstAvailableNodeInsertionStrategy();
    }
  }

  getFirstAvailableNodeInsertionStrategy(): NodeInsertionStrategy {
    if (!this.disabledInsertPositions.above) return NodeInsertionStrategy.ABOVE;
    if (!this.disabledInsertPositions.leftRight)
      return NodeInsertionStrategy.LEFT;
    if (!this.disabledInsertPositions.below) return NodeInsertionStrategy.BELOW;
    return NodeInsertionStrategy.CHANGE;
  }

  hideAllTooltips() {}

  get allQuickActionsDisabled() {
    return this.makeOptionalDisabled && this.makeRepeatableDisabled;
  }

  onMakeOptional() {
    if (!this.selectedRootNode) return;
    this.processTreeService.makeSubtreeOptional(this.selectedRootNode.data);
  }

  get makeOptionalDisabled() {
    return !this.selectedRootNode;
  }

  onMakeRepeatable() {
    if (!this.selectedRootNode) return;
    this.processTreeService.makeSubtreeRepeatable(this.selectedRootNode.data);
  }

  get makeRepeatableDisabled() {
    return !this.selectedRootNode;
  }
}

// TODO should be solved differently
// tslint:disable-next-line:no-namespace
export namespace ProcessTreeEditorComponent {
  export const componentName = 'ProcessTreeEditorComponent';
}
