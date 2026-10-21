import { Injectable } from '@angular/core';
import {
  BehaviorSubject,
  Observable,
  partition,
  Subject,
  Subscription,
} from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { BackgroundTaskInfoService } from '../backgroundTaskInfoService/background-task-info.service';
import { ConformanceCheckingResult, treeConformanceResult } from './model';
import Swal from 'sweetalert2';
import { ProcessTree } from 'src/app/objects/ProcessTree/ProcessTree';
import { VariantService } from '../variantService/variant.service';
import { InfixType } from 'src/app/objects/Variants/infix_selection';
import { Variant } from 'src/app/objects/Variants/variant';
import { ColorMap } from 'src/app/objects/ColorMap';
import * as d3 from 'd3';
import { COLORS_BLUE, COLORS_PURPLE } from 'src/app/objects/Colors';
import { ROUTES } from 'src/app/constants/backend_route_constants';
import { ProcessTreeService } from '../processTreeService/process-tree.service';
import { BackendService } from '../backendService/backend.service';
import { processTreesEqual } from 'src/app/objects/ProcessTree/utility-functions/process-tree-integrity-check';
import { ModelViewModeService } from '../viewModeServices/model-view-mode.service';
import { ViewMode } from 'src/app/objects/ViewMode';

@Injectable({
  providedIn: 'root',
})
export class ConformanceCheckingService {
  constructor(
    private infoService: BackgroundTaskInfoService,
    private variantService: VariantService,
    private processTreeService: ProcessTreeService,
    private backendService: BackendService,
    private modelViewModeService: ModelViewModeService
  ) {
    this.processTreeService.currentDisplayedProcessTree$.subscribe((pt) => {
      if (!processTreesEqual(pt, this.usedProcessTreeForTreeConformance)) {
        this.activeTreeConformances.clear();
        this.mergedTreeConformance = undefined;
        this.variantsTreeConformance.clear();
        this.hideTreeConformance();
      }
    });

    this.modelViewModeService.viewMode$.subscribe((viewMode) => {
      if (viewMode === ViewMode.CONFORMANCE && this.anyTreeConformanceActive)
        this.showTreeConformance();
    });
  }

  public readonly modelConformanceColorMap = new ColorMap(
    d3
      .scaleThreshold<any, any>()
      .domain(
        COLORS_PURPLE.map((value, index) => index / (COLORS_PURPLE.length - 1))
      )
      .range(['#d3d3d3', ...COLORS_PURPLE])
  );
  public readonly modelConformanceStripeColors = [
    COLORS_PURPLE[0],
    COLORS_PURPLE[1],
  ];

  public readonly variantConformanceColorMap = new ColorMap(
    d3
      .scaleThreshold<any, any>()
      .domain(
        COLORS_BLUE.map((value, index) => index / (COLORS_BLUE.length - 1))
      )
      .range(['#d3d3d3', ...COLORS_BLUE])
  );
  public readonly variantConformanceStripeColors = [
    COLORS_BLUE[0],
    COLORS_BLUE[1],
  ];

  private socket: WebSocketSubject<any>;
  private runningRequests: number[] = [];
  public varResults: Observable<ConformanceCheckingResult>;
  public patternResults: Observable<ConformanceCheckingResult>;
  public showConformanceCheckingTimeoutDialog: Subject<any> =
    new Subject<any>();

  private usedProcessTreeForTreeConformance: ProcessTree;

  public isConformanceWeighted$: BehaviorSubject<Boolean> =
    new BehaviorSubject<Boolean>(false);

  set isConformanceWeighted(isWeighted: Boolean) {
    if (this.isConformanceWeighted !== isWeighted) {
      this.isConformanceWeighted$.next(isWeighted);
    }
  }

  get isConformanceWeighted() {
    return this.isConformanceWeighted$.value;
  }

  private activeTreeConformances: Set<Variant> = new Set<Variant>();
  private mergedTreeConformance: ProcessTree;
  public variantsTreeConformance: Map<Variant, ProcessTree> = new Map<
    Variant,
    ProcessTree
  >();
  private latestRequest: Subscription;
  public calculationInProgress = new Set<Variant>();

  public connect(): boolean {
    if (!this.socket || this.socket.closed) {
      this.socket = webSocket(
        ROUTES.WS_HTTP_BASE_URL + ROUTES.VARIANT_CONFORMANCE
      );
      const results = this.socket.pipe(
        catchError((error) => {
          this.runningRequests.forEach((r: number) =>
            this.infoService.removeRequest(r)
          );
          this.runningRequests = [];
          this.socket = null;

          throw error;
        }),
        tap((_) => {
          this.infoService.removeRequest(this.runningRequests.pop());
        }),
        map((result) => {
          if ('error' in result) {
            Swal.fire({
              title: 'Error occurred',
              html:
                '<b>Error message: </b><br>' +
                '<code>' +
                'Calculating conformance statistics failed' +
                '</code>',
              icon: 'error',
              showCloseButton: false,
              showConfirmButton: false,
              showCancelButton: true,
              cancelButtonText: 'close',
            });
            return result;
          }
          return new ConformanceCheckingResult(
            result['id'],
            result['type'],
            result['isTimeout'],
            result['cost'],
            result['deviations'],
            result['alignment'],
            result['pt']
          );
        })
      );
      [this.varResults, this.patternResults] = partition(
        results,
        (ccr: ConformanceCheckingResult) => ccr.type === 1 || 'error' in ccr
      );

      return true;
    }

    return false;
  }

  public calculateConformance(
    id: string,
    infixType: InfixType,
    pt: ProcessTree,
    variant: any,
    timeout: number,
    alignType: AlignmentType
  ): boolean {
    const resubscribe = this.connect();
    const rid = this.infoService.setRequest('conformance checking', () =>
      this.cancelConformanceCheckingRequests()
    );
    this.runningRequests.push(rid);
    this.socket.next({
      id: id,
      infixType: infixType,
      alignType: alignType,
      pt: pt.copy(false),
      variant: variant,
      timeout: timeout,
    });

    return resubscribe;
  }

  private cancelConformanceCheckingRequests(): void {
    this.socket.next({ isCancellationRequested: true });
    this.runningRequests.forEach((r: number) =>
      this.infoService.removeRequest(r)
    );
    this.runningRequests = [];
    this.variantService.variants.forEach((v) => {
      v.calculationInProgress = false;
    });
    this.socket.unsubscribe();
  }

  public showConformanceTimeoutDialog(variant: Variant, callbackFunc) {
    this.showConformanceCheckingTimeoutDialog.next([variant, callbackFunc]);
  }

  public isTreeConformanceActive(v: Variant) {
    return this.activeTreeConformances.has(v);
  }

  public isTreeConformanceCalcInProgress(v: Variant) {
    return this.calculationInProgress.has(v);
  }

  public anyTreeConformanceActive() {
    return this.activeTreeConformances.size > 0;
  }

  private updateTreeConformance(variants: Variant[]) {
    this.latestRequest?.unsubscribe();

    this.usedProcessTreeForTreeConformance =
      this.processTreeService.currentDisplayedProcessTree.copy(false);

    this.latestRequest = this.backendService
      .getTreeConformance(this.usedProcessTreeForTreeConformance, variants)
      .subscribe((res: treeConformanceResult) => {
        this.mergedTreeConformance = res.merged_conformance_tree;

        variants.forEach((variant, index) => {
          const pt = res.variants_tree_conformance[index];
          this.activeTreeConformances.add(variant);
          this.variantsTreeConformance.set(variant, pt);

          this.calculationInProgress.delete(variant);
        });

        this.showTreeConformance();
      });
  }

  public showTreeConformance() {
    if (
      this.processTreeService.currentDisplayedProcessTree !==
      this.mergedTreeConformance
    )
      this.processTreeService.currentDisplayedProcessTree =
        this.mergedTreeConformance;
    if (this.modelViewModeService.viewMode !== ViewMode.CONFORMANCE)
      this.modelViewModeService.viewMode = ViewMode.CONFORMANCE;
  }

  public hideTreeConformance() {
    this.stopRunningRequest();
    this.modelViewModeService.viewMode = ViewMode.STANDARD;
    this.activeTreeConformances.clear();
  }

  private stopRunningRequest() {
    this.latestRequest?.unsubscribe();
    this.calculationInProgress.clear();
  }

  public toggleTreeConformance() {
    if (this.anyTreeConformanceActive()) this.hideTreeConformance();
    else this.showTreeConformance();
  }

  public addToTreeConformance(variant: Variant) {
    if (
      !this.activeTreeConformances.has(variant) &&
      !this.calculationInProgress.has(variant)
    ) {
      this.calculationInProgress.add(variant);
      const variantsCombined: Variant[] = Array.from(
        new Set([...this.activeTreeConformances, ...this.calculationInProgress])
      );
      this.updateTreeConformance(Array.from(variantsCombined));
    } else {
      this.showTreeConformance();
    }
  }

  public removeFromTreeConformance(variant: Variant) {
    const wasActive = this.activeTreeConformances.delete(variant);
    const wasInProgress = this.calculationInProgress.delete(variant);
    if (wasActive || wasInProgress) {
      if (this.activeTreeConformances.size == 0) this.hideTreeConformance();
      else {
        const variantsCombined: Variant[] = Array.from(
          new Set([
            ...this.activeTreeConformances,
            ...this.calculationInProgress,
          ])
        );
        this.updateTreeConformance(Array.from(variantsCombined));
      }
    }
  }
}

export enum AlignmentType {
  VariantAlignment = 1,
  PatternAlignment = 2,
}
