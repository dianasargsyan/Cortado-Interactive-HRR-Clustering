import { Injectable } from '@angular/core';
import {
  ProcessTree,
  TreePerformance,
} from '../objects/ProcessTree/ProcessTree';
import { BackendService } from './backendService/backend.service';
import { BehaviorSubject, Subscription } from 'rxjs';
import { HumanizeDurationPipe } from '../pipes/humanize-duration.pipe';
import { ProcessTreeService } from './processTreeService/process-tree.service';
import { VariantService } from './variantService/variant.service';
import { Variant } from '../objects/Variants/variant';
import { ModelViewModeService } from './viewModeServices/model-view-mode.service';
import { ViewMode } from '../objects/ViewMode';

@Injectable({
  providedIn: 'root',
})
export class PerformanceService {
  mergedTreePerformance: ProcessTree;

  // key is variant, value is process tree
  variantsTreePerformance: Map<Variant, ProcessTree> = new Map<
    Variant,
    ProcessTree
  >();

  public availablePerformances: Set<Variant> = new Set<Variant>();

  // key is id of node, value is map with performance stats for each variant
  allValues: Map<number, Map<Variant, TreePerformance>> = new Map<
    number,
    Map<Variant, TreePerformance>
  >();

  allValuesMean: Map<number, TreePerformance> = new Map<
    number,
    TreePerformance
  >();

  // colorScale for each tree node;
  private activeTreePerformances: Set<Variant> = new Set<Variant>();
  newValues: BehaviorSubject<boolean> = new BehaviorSubject<boolean>(false);
  calculationInProgress = new Set<Variant>();
  latestRequest: Subscription;
  fitness = new Map<Variant, number>();

  private currentPt: ProcessTree;

  constructor(
    private variantService: VariantService,
    private backendService: BackendService,
    private processTreeService: ProcessTreeService,
    private modelViewModeService: ModelViewModeService
  ) {
    this.currentPt = processTreeService.currentDisplayedProcessTree;

    this.variantService.variants$.subscribe((_variants) => {
      this.clear();
    });
    processTreeService.currentDisplayedProcessTree$.subscribe((pt) => {
      if (pt) {
        this.processTreeService.selectedTree = pt;
      } else {
        this.clear();
        this.processTreeService.selectedTree = undefined;
        this.currentPt = undefined;
        return;
      }

      if (
        !this.currentPt?.equals(pt) ||
        (this.currentPt.equals(pt) &&
          !pt.performance &&
          this.currentPt.performance)
      ) {
        this.clear();
        this.currentPt = pt;
      }
    });

    this.modelViewModeService.viewMode$.subscribe((viewMode) => {
      if (
        viewMode === ViewMode.PERFORMANCE &&
        this.anyTreePerformanceActive()
      ) {
        this.showTreePerformance();
      }
    });
  }

  private updateTreePerformance(variants: Variant[]): void {
    this.latestRequest?.unsubscribe();

    this.latestRequest = this.backendService
      .getTreePerformance(variants.map((v) => v.bid))
      .subscribe(
        (performance) => {
          this.mergedTreePerformance = ProcessTree.fromObj(
            performance.merged_performance_tree
          );

          this.allValues.clear();

          variants.forEach((variant, i) => {
            const pt = performance.variants_tree_performance[i];

            this.fitness.set(variant, performance.fitness_values[i]);
            this.variantsTreePerformance.set(variant, pt);
            this.calculationInProgress.delete(variant);
            this.collectPerformance(pt, variant, this.allValues);
            this.activeTreePerformances.add(variant);
          });

          this.allValuesMean.clear();
          this.setMeanPerformanceMap(this.mergedTreePerformance);

          this.newValues.next(true);

          this.processTreeService.currentDisplayedProcessTree =
            performance.merged_performance_tree;

          this.showTreePerformance();
        },
        (error) => {
          variants.forEach((v) => this.calculationInProgress.delete(v));
        }
      );
  }

  public hideTreePerformance() {
    this.modelViewModeService.viewMode = ViewMode.STANDARD;
    this.activeTreePerformances.clear();
  }

  public setVariantsPerformance(
    variants: Variant[],
    performanceTrees: ProcessTree[]
  ): void {
    for (let i = 0; i < variants.length; i++) {
      this.variantsTreePerformance.set(variants[i], performanceTrees[i]);
    }

    variants.forEach((variant, i) => {
      const tree = performanceTrees[i];
      this.collectPerformance(tree, variant, this.allValues);
    });
  }

  // Stores performance values for each tree node in the performances map under the given variantIdx
  collectPerformance(
    vp: ProcessTree,
    variant: Variant,
    performances: Map<number, Map<Variant, TreePerformance>>
  ): Map<number, Map<Variant, TreePerformance>> {
    if (!performances.has(vp.id)) {
      performances.set(vp.id, new Map<Variant, TreePerformance>());
    }
    performances.get(vp.id).set(variant, vp.performance);

    for (const child of vp.children) {
      this.collectPerformance(child, variant, performances);
    }
    return performances;
  }

  public showTreePerformance() {
    if (
      this.processTreeService.currentDisplayedProcessTree !==
      this.mergedTreePerformance
    )
      this.processTreeService.currentDisplayedProcessTree =
        this.mergedTreePerformance;
    if (this.modelViewModeService.viewMode !== ViewMode.PERFORMANCE)
      this.modelViewModeService.viewMode = ViewMode.PERFORMANCE;
  }

  public toggleTreePerformance() {
    if (this.anyTreePerformanceActive()) this.hideTreePerformance();
    else this.showTreePerformance();
  }

  private stopRunningRequest() {
    this.latestRequest.unsubscribe();
    this.calculationInProgress.clear();
  }

  private clear(): void {
    this.mergedTreePerformance = undefined;
    this.variantsTreePerformance.clear();
    this.availablePerformances.clear();
    this.allValues.clear();
    this.allValuesMean.clear();
    this.activeTreePerformances.clear();
    this.calculationInProgress.clear();
    this.processTreeService.selectedTree = undefined;

    this.modelViewModeService.viewMode = ViewMode.STANDARD;
  }

  public addToTreePerformance(variant: Variant) {
    if (
      !this.activeTreePerformances.has(variant) &&
      !this.calculationInProgress.has(variant)
    ) {
      this.calculationInProgress.add(variant);
      const variantsCombined: Variant[] = Array.from(
        new Set([...this.activeTreePerformances, ...this.calculationInProgress])
      );
      this.updateTreePerformance(Array.from(variantsCombined));
    } else {
      this.showTreePerformance();
    }
  }

  public removeFromTreePerformance(variant: Variant) {
    const wasActive = this.activeTreePerformances.delete(variant);
    const wasInProgress = this.calculationInProgress.delete(variant);
    if (wasActive || wasInProgress) {
      if (this.activeTreePerformances.size == 0) this.hideTreePerformance();
      else {
        const variantsCombined: Variant[] = Array.from(
          new Set([
            ...this.activeTreePerformances,
            ...this.calculationInProgress,
          ])
        );
        this.updateTreePerformance(Array.from(variantsCombined));
      }
    }
  }

  private setMeanPerformanceMap(tree: ProcessTree): void {
    this.allValuesMean.set(tree.id, tree.performance);
    tree.children.forEach((node) => this.setMeanPerformanceMap(node));
  }

  public isTreePerformanceActive(v: Variant) {
    return this.activeTreePerformances.has(v);
  }

  public anyTreePerformanceActive() {
    return this.activeTreePerformances.size > 0;
  }

  public isTreePerformanceCalcInProgress(v: Variant) {
    return this.calculationInProgress.has(v);
  }

  public isTreePerformanceFitting(v: Variant) {
    const fitness = this.fitness.get(v);
    return fitness == undefined || fitness == 1;
  }
}
