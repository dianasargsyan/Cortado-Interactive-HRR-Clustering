import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import * as d3 from 'd3';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { PT_Constant } from 'src/app/constants/process_tree_drawer_constants';
import { ProcessTreeDrawerDirective } from 'src/app/directives/process-tree-drawer/process-tree-drawer.directive';
import { VariantDrawerDirective } from 'src/app/directives/variant-drawer/variant-drawer.directive';
import { LocalProcessModelWithPatterns } from 'src/app/objects/LocalProcessModelWithPatterns';
import { LpmMetrics } from 'src/app/objects/LpmMetrics';
import {
  ProcessTree,
  ProcessTreeOperator,
} from 'src/app/objects/ProcessTree/ProcessTree';
import { InfixType } from 'src/app/objects/Variants/infix_selection';
import { Variant } from 'src/app/objects/Variants/variant';
import {
  VariantElement,
  LeafNode,
} from 'src/app/objects/Variants/variant_element';
import { BackendService } from 'src/app/services/backendService/backend.service';
import { ColorMapService } from 'src/app/services/colorMapService/color-map.service';
import { LazyLoadingServiceService } from 'src/app/services/lazyLoadingService/lazy-loading.service';
import { LpmService } from 'src/app/services/lpmService/lpm.service';
import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';
import { textColorForBackgroundColor } from 'src/app/utils/render-utils';
import { contextMenuCallback } from '../../variant-explorer/functions/variant-drawer-callbacks';

@Component({
  // eslint-disable-next-line @angular-eslint/component-selector
  selector: '[app-lpm-explorer-row]',
  templateUrl: './lpm-explorer-row.component.html',
  styleUrls: ['./lpm-explorer-row.component.scss'],
})
export class LpmExplorerRowComponent
  implements AfterViewInit, OnDestroy, OnInit
{
  @Input()
  lpm: LocalProcessModelWithPatterns;

  @ViewChild('row')
  lpmRowElement: ElementRef;

  _rootElement: ElementRef;

  @ViewChild(VariantDrawerDirective)
  variantDrawer: VariantDrawerDirective;

  @ViewChild(ProcessTreeDrawerDirective)
  processTreeDrawer: ProcessTreeDrawerDirective;

  processTreeInSvg;
  openContextCallback = contextMenuCallback.bind(this);
  InfixType = InfixType;
  isVisible: boolean = false;
  activityColorMap: Map<string, string>;
  private _destroy$ = new Subject();
  lpmColumnSize = 0;
  treeSvgHeight = '0px';

  constructor(
    private lazyLoadingService: LazyLoadingServiceService,
    private colorMapService: ColorMapService,
    private processTreeService: ProcessTreeService,
    private backendService: BackendService,
    private lpmService: LpmService
  ) {}
  ngOnInit(): void {
    let height = this.getHeightOfLpm(this.lpm.lpm);
    let treeSvgHeightN =
      height * (PT_Constant.BASE_HEIGHT_WIDTH + 2 * 3) +
      (height - 1) * PT_Constant.NODE_SPACING;
    this.treeSvgHeight = treeSvgHeightN + 'px';
  }

  ngAfterViewInit(): void {
    this.processTreeInSvg = d3.select('d3-svg-directive');

    let obs = new ResizeObserver((entries) => {
      for (let entry of entries) {
        this.lpmColumnSize = entry.contentRect.width;
      }
    });
    obs.observe(this.lpmRowElement.nativeElement);

    this.colorMapService.colorMap$
      .pipe(takeUntil(this._destroy$))
      .subscribe((colorMap) => {
        this.activityColorMap = colorMap;
      });

    const self = this;
    this.lazyLoadingService.addLpm(
      this.lpmRowElement.nativeElement,
      (isIntersecting) => {
        self.isVisible = isIntersecting;
        if (self.isVisible) {
          this.processTreeDrawer.redraw(this.lpm.lpm);
        }
      }
    );
  }

  showInProcessTreeEditor() {
    this.processTreeService.set_currentDisplayedProcessTree_with_Cache(
      this.lpm.lpm
    );
  }

  showMetrics() {
    this.backendService
      .getLpmMetrics(this.lpm.lpm)
      .subscribe(
        (metrics: LpmMetrics) => (this.lpmService.lpmMetrics = metrics)
      );
  }

  computeTextColor = (d: d3.HierarchyNode<ProcessTree>) => {
    if (d.data.label === ProcessTreeOperator.tau) {
      return 'white';
    }
    const nodeColor = this.computeNodeColor(d);

    const isVisibleActivity =
      d.data.label !== null && d.data.label !== ProcessTreeOperator.tau;
    return isVisibleActivity ? textColorForBackgroundColor(nodeColor) : 'white';
  };

  computeNodeColor = (d: d3.HierarchyNode<ProcessTree>) => {
    if (d.data.operator !== null) return PT_Constant.OPERATOR_COLOR;
    if (d.data.label === '...') return 'gray';
    if (d.data.label !== null && d.data.label === ProcessTreeOperator.tau)
      return PT_Constant.INVISIBLE_ACTIVTIY_COLOR;
    const isVisibleActivity =
      d.data.label !== null && d.data.label !== ProcessTreeOperator.tau;

    return isVisibleActivity ? this.activityColorMap.get(d.data.label) : null;
  };

  computeActivityColor = (
    self: VariantDrawerDirective,
    element: VariantElement,
    variant: Variant
  ) => {
    let color;

    if (element instanceof LeafNode) {
      color = this.activityColorMap.get(element.asLeafNode().activity[0]);

      if (element.activity.length > 1) {
        color = '#d3d3d3'; // lightgray
      }
    } else {
      color = '#d3d3d3';
    }

    return color;
  };

  selectNodeCallBack = (self, event, d) => {
    console.log(this.treeSvgHeight);
  };

  tooltipContent = (d: d3.HierarchyNode<ProcessTree>) => {
    return '';
  };

  getHeightOfLpm(processTree: ProcessTree) {
    if (processTree.children.length == 0) {
      return 1;
    }
    let childHeights = [];
    for (let child of processTree.children) {
      childHeights.push(this.getHeightOfLpm(child));
    }

    return 1 + Math.max(...childHeights);
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }
}
