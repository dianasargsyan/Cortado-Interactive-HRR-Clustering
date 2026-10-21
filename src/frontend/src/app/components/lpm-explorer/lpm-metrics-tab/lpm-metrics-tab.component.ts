import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  Inject,
  OnInit,
  Renderer2,
} from '@angular/core';
import { ComponentContainer, LogicalZIndex } from 'golden-layout';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { LpmMetrics } from 'src/app/objects/LpmMetrics';
import { GoldenLayoutComponentService } from 'src/app/services/goldenLayoutService/golden-layout-component.service';
import { LpmService } from 'src/app/services/lpmService/lpm.service';
import { VariantPerformanceService } from 'src/app/services/variant-performance.service';
import { VariantViewModeService } from 'src/app/services/viewModeServices/variant-view-mode.service';

@Component({
  selector: 'app-lpm-metrics-tab',
  templateUrl: './lpm-metrics-tab.component.html',
  styleUrls: ['./lpm-metrics-tab.component.css'],
})
export class LpmMetricsTabComponent
  extends LayoutChangeDirective
  implements OnInit
{
  metrics: LpmMetrics = null;

  constructor(
    renderer: Renderer2,
    @Inject(LayoutChangeDirective.GoldenLayoutContainerInjectionToken)
    private container: ComponentContainer,
    elRef: ElementRef,
    private lpmService: LpmService,
    private goldenLayoutService: GoldenLayoutComponentService
  ) {
    super(elRef.nativeElement, renderer);
  }
  ngOnInit(): void {
    this.lpmService.lpmMetrics$.subscribe((m) => {
      this.metrics = m;
      if (this.metrics !== null)
        this.goldenLayoutService.activateLpmMetricsView();
    });
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
}

export namespace LpmMetricsTabComponent {
  export const componentName = 'LpmMetricsTabComponent';
}
