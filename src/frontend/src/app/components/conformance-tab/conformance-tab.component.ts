import {
  AfterViewInit,
  Component,
  ElementRef,
  Inject,
  OnDestroy,
  Renderer2,
  ViewChild,
} from '@angular/core';
import { Tab } from 'bootstrap';
import { ComponentContainer, LogicalZIndex } from 'golden-layout';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { ColorMap } from 'src/app/objects/ColorMap';
import { ViewMode } from 'src/app/objects/ViewMode';
import { ConformanceCheckingService } from 'src/app/services/conformanceChecking/conformance-checking.service';
import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';
import { ModelViewModeService } from 'src/app/services/viewModeServices/model-view-mode.service';
import { VariantViewModeService } from 'src/app/services/viewModeServices/variant-view-mode.service';
import { ColorMapValue } from '../performance/color-map/color-map.component';

@Component({
  selector: 'app-conformance-tab',
  templateUrl: './conformance-tab.component.html',
  styleUrls: ['./conformance-tab.component.css'],
})
export class ConformanceTabComponent
  extends LayoutChangeDirective
  implements AfterViewInit, OnDestroy
{
  @ViewChild('colorMapTab') colorMapTab: ElementRef;

  private _destroy$ = new Subject();
  public modelConformanceColorMapValues: ColorMapValue[];
  public modelConformancePrefixes: string[];
  public variantConformanceColorMapValues: ColorMapValue[];
  public variantConformancePrefixes: string[];

  public VM = ViewMode;

  constructor(
    @Inject(LayoutChangeDirective.GoldenLayoutContainerInjectionToken)
    private container: ComponentContainer,
    elRef: ElementRef,
    renderer: Renderer2,
    public conformanceCheckingService: ConformanceCheckingService,
    private variantViewModeService: VariantViewModeService,
    public modelViewModeService: ModelViewModeService,
    public processTreeService: ProcessTreeService
  ) {
    super(elRef.nativeElement, renderer);

    this.modelConformanceColorMapValues = this.calculateColorMapValues(
      this.conformanceCheckingService.modelConformanceColorMap
    );
    this.variantConformanceColorMapValues = this.calculateColorMapValues(
      this.conformanceCheckingService.variantConformanceColorMap
    );

    this.variantConformancePrefixes = new Array(
      this.variantConformanceColorMapValues.length
    );
    this.variantConformancePrefixes[1] = '>';
    this.variantConformancePrefixes[
      this.variantConformancePrefixes.length - 2
    ] = '<';
    this.modelConformancePrefixes = new Array(
      this.modelConformanceColorMapValues.length
    );
    this.modelConformancePrefixes[1] = '>';
    this.modelConformancePrefixes[this.modelConformancePrefixes.length - 2] =
      '<';
  }

  private calculateColorMapValues(colorMap: ColorMap) {
    const min = colorMap.domain()[0];
    const max = colorMap.domain()[colorMap.domain().length - 1];
    const increment = (max - min) / (colorMap.range().length - 3);

    const minColor = {
      lowerBound: min * 100,
      color: colorMap.range()[1],
    };
    const maxColor = {
      lowerBound: max * 100,
      color: null,
    };
    const otherColors = colorMap
      .range()
      .slice(2)
      .map((v, i) => {
        const t = min + i * increment;

        return {
          lowerBound: Math.round(t * 100),
          color: v,
        };
      });
    return [minColor].concat(otherColors, [maxColor]);
  }

  ngAfterViewInit(): void {
    this.variantViewModeService.viewMode$
      .pipe(takeUntil(this._destroy$))
      .subscribe((viewMode) => {
        if (viewMode === ViewMode.CONFORMANCE)
          this.colorMapTab.nativeElement.click();
      });
  }

  ngOnDestroy(): void {
    this._destroy$.next();
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

  public performanceStats: any;
  public colorScale;
  public title;

  public conformanceWeightMethodChange(event): void {
    const value = event.target.value;
    if (value == 'weighted_equally')
      this.conformanceCheckingService.isConformanceWeighted = false;
    else this.conformanceCheckingService.isConformanceWeighted = true;
  }
}

export namespace ConformanceTabComponent {
  export const componentName = 'VariantConformanceComponent';
}
