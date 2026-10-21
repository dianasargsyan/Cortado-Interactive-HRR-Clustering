import {
  AfterViewInit,
  Component,
  ContentChild,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  TemplateRef,
  ViewChild,
} from '@angular/core';

import { LazyLoadingServiceService } from 'src/app/services/lazyLoadingService/lazy-loading.service';
import { InfixType } from 'src/app/objects/Variants/infix_selection';
import { Variant } from 'src/app/objects/Variants/variant';
import { ViewMode } from 'src/app/objects/ViewMode';
import { VariantViewModeService } from 'src/app/services/viewModeServices/variant-view-mode.service';
import { PerformanceService } from 'src/app/services/performance.service';
import { ConformanceCheckingService } from 'src/app/services/conformanceChecking/conformance-checking.service';
import { ModelPerformanceColorScaleService } from 'src/app/services/performance-color-scale.service';
import { textColorForBackgroundColor } from 'src/app/utils/render-utils';
import { getCssStripes } from '../../performance/color-map/color-map.component';

@Component({
  // eslint-disable-next-line @angular-eslint/component-selector
  selector: '[app-variant]',
  templateUrl: './variant.component.html',
  styleUrls: ['./variant.component.scss'],
})
export class VariantComponent implements AfterViewInit {
  @ContentChild('variantInfo') variantInfo!: TemplateRef<any>;
  @ContentChild('treeButton') treeButton!: TemplateRef<any>;
  @ContentChild('variantDrawer') variantDrawer!: TemplateRef<any>;
  @ContentChild('subvariantButton') subvariantButton!: TemplateRef<any>;
  @ContentChild('infixSelection') infixSelection!: TemplateRef<any>;
  @ContentChild('removeVariantButton') removeVariantButton!: TemplateRef<any>;

  @Input()
  index: number;

  @Input()
  variant: Variant;

  @Input()
  rootElement: ElementRef;

  @Input()
  traceInfixSelectionMode: boolean = false;

  @Input()
  processTreeAvailable: boolean = false;

  @Output() clickCbFc: EventEmitter<any> = new EventEmitter();

  @ViewChild('row')
  rowElement: ElementRef;

  isVisible: boolean = false;

  // necessary because one cannot use it directly in the template file
  infixType = InfixType;

  public VM = ViewMode;

  constructor(
    private lazyLoadingService: LazyLoadingServiceService,
    public variantViewModeService: VariantViewModeService,
    private conformanceCheckingService: ConformanceCheckingService,
    private performanceService: PerformanceService,
    private modelPerformanceColorScaleService: ModelPerformanceColorScaleService
  ) {}

  ngAfterViewInit(): void {
    const self = this;

    this.lazyLoadingService.addVariant(
      this.rowElement.nativeElement.parentNode,
      this.rootElement,
      (isIntersecting) => {
        self.isVisible = isIntersecting;
      }
    );
  }

  isExpanded(): boolean {
    return this.variant.variant.expanded;
  }

  get isTreeConformanceActive() {
    return this.conformanceCheckingService.isTreeConformanceActive(
      this.variant
    );
  }

  get treeConformanceValue() {
    const tree = this.conformanceCheckingService.variantsTreeConformance.get(
      this.variant
    );

    if (!tree) return null;

    return this.conformanceCheckingService.isConformanceWeighted &&
      tree.conformance?.weighted_by_counts != undefined
      ? tree.conformance?.weighted_by_counts.value
      : tree.conformance?.weighted_equally.value;
  }

  get isTreePerformanceActive() {
    return this.performanceService.isTreePerformanceActive(this.variant);
  }

  get treePerformanceValue() {
    const selectedColorScale =
      this.modelPerformanceColorScaleService.selectedColorScale;
    let performance = this.performanceService.variantsTreePerformance.get(
      this.variant
    ).performance[selectedColorScale.performanceIndicator]?.[
      selectedColorScale.statistic
    ];
    if (performance == undefined) {
      performance = 0;
    }
    return performance;
  }

  get performanceTextColor(): string {
    const buttonColor = this.performanceButtonColor;
    if (!buttonColor) return 'white';
    return textColorForBackgroundColor(buttonColor);
  }

  get performanceButtonColor() {
    if (this.isTreePerformanceActive) {
      let tree;
      tree = this.performanceService.variantsTreePerformance.get(this.variant);

      if (!tree) {
        return null;
      }

      let selectedScale =
        this.modelPerformanceColorScaleService.selectedColorScale;
      const colorScale = this.modelPerformanceColorScaleService
        .getVariantComparisonColorScale()
        .get(tree.id);
      if (
        colorScale &&
        tree.performance?.[selectedScale.performanceIndicator]?.[
          selectedScale.statistic
        ] !== undefined
      ) {
        if (
          tree.performance[selectedScale.performanceIndicator][
            selectedScale.statistic
          ] == 0
        )
          return getCssStripes();
        else
          return colorScale.getColor(
            tree.performance[selectedScale.performanceIndicator][
              selectedScale.statistic
            ]
          );
      }
    }
    return '#d3d3d3';
  }

  get conformanceButtonColor() {
    if (this.treeConformanceValue >= 0 && this.isTreeConformanceActive)
      return this.conformanceCheckingService.modelConformanceColorMap.getColor(
        this.treeConformanceValue
      );
    else return '#d3d3d3';
  }

  get conformanceTextColor() {
    const buttonColor = this.conformanceButtonColor;
    if (!buttonColor) return 'white';
    return textColorForBackgroundColor(buttonColor);
  }
}
