import { VariantFilterService } from './../variantFilterService/variant-filter.service';
import { ColorMapService } from 'src/app/services/colorMapService/color-map.service';
import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';
import { LogService } from 'src/app/services/logService/log.service';
import * as objectHash from 'object-hash';
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { map, mergeMap, tap } from 'rxjs/operators';
import { v4 as uuidv4 } from 'uuid';
import {
  getInfixTypeForSelectedInfix,
  getSelectedChildren,
  InfixType,
  removeIntermediateGroupsWithSingleElements,
} from 'src/app/objects/Variants/infix_selection';
import { FragmentStatistics, Variant } from 'src/app/objects/Variants/variant';
import {
  deserialize,
  SequenceGroup,
} from 'src/app/objects/Variants/variant_element';
import {
  addVariantInformation,
  compute_delete_activity_variants,
  compute_rename_activity_variants,
} from './variant-transformation';
import { ToastService } from '../toast/toast.service';
import { VariantSorter } from 'src/app/objects/Variants/variant-sorter';
import { LoopCollapsedVariant } from 'src/app/objects/Variants/loop_collapsed_variant';
import { ClusteringConfig } from 'src/app/objects/ClusteringConfig';
import { ClusteringAlgorithm } from 'src/app/objects/ClusteringAlgorithm';
import { BackendService } from '../backendService/backend.service';
import {
  ActivityDeletion,
  ActivityRenaming,
  UserDefinedInfixAddition,
  UserDefinedVariantAddition,
  VariantsDeletion,
} from 'src/app/objects/LogModification';

@Injectable({
  providedIn: 'root',
})
export class VariantService {
  variantService: any;
  nameChanges: BehaviorSubject<any> = new BehaviorSubject<any>(null);

  // reference for activity element to manually hide tooltips on activities upon click
  private _activityTooltipReference;
  get activityTooltipReference() {
    return this._activityTooltipReference;
  }

  set activityTooltipReference(value) {
    this._activityTooltipReference = value;
  }

  constructor(
    private logService: LogService,
    private processTreeService: ProcessTreeService,
    private colorMapService: ColorMapService,
    private toastService: ToastService,
    private variantFilterService: VariantFilterService,
    private backendService: BackendService
  ) {
    this.logService.loadedEventLog$.subscribe(() => {
      this.variantFilterService.clearAllFilters();
      if (this.logService.variants) {
        this.variants = this.logService.variants;
        this.cachedChange = false;
      }
    });
  }

  public showVariantSequentializerDialog: Subject<any> = new Subject<any>();
  private _variants = new BehaviorSubject<Variant[]>([]);
  private _collapsedVariants = new BehaviorSubject<LoopCollapsedVariant[]>(
    null
  );
  public areVariantLoopsCollapsed = false;

  set collapsedVariants(variants: LoopCollapsedVariant[]) {
    this._collapsedVariants.next(variants);
  }

  get collapsedVariants$(): Observable<LoopCollapsedVariant[]> {
    return this._collapsedVariants.asObservable();
  }

  get variants$(): Observable<Variant[]> {
    return this._variants.asObservable();
  }

  set variants(activities: Variant[]) {
    this._variants.next(activities);
  }

  get variants(): Variant[] {
    return this._variants.getValue();
  }

  private _clusteringConfig = new BehaviorSubject<ClusteringConfig>(null);

  set clusteringConfig(clusteringConfig: ClusteringConfig) {
    if (clusteringConfig) {
      // HRR clusterings are computed by the HRRClusteringService
      if (clusteringConfig.algorithm !== ClusteringAlgorithm.HRR_CLUSTERING) {
        this.computeClusterClustering(clusteringConfig);
      }
    } else {
      this.resetClusterAssignments();
    }
    this._clusteringConfig.next(clusteringConfig);
  }

  get clusteringConfig(): ClusteringConfig {
    return this._clusteringConfig.getValue();
  }

  get clusteringConfig$(): Observable<ClusteringConfig> {
    return this._clusteringConfig.asObservable();
  }

  public lastChangeRenaming = null;
  private _cachedChange = new BehaviorSubject<boolean>(false);

  get cachedChange$(): Observable<boolean> {
    return this._cachedChange.asObservable();
  }

  set cachedChange(change: boolean) {
    this.lastChangeRenaming = null;
    this._cachedChange.next(change);
  }

  get cachedChange(): boolean {
    return this._cachedChange.getValue();
  }

  // TODO Add Spinner Removal / Toast etc.
  private afterVariantChange() {
    this.variantFilterService.clearAllFilters();
  }

  public nUserVariants: number = 0;

  public addSelectedTraceInfix(
    variant: Variant,
    sortingFeature: string,
    isAscending: boolean
  ): void {
    let isWholeVariantSelected = variant.variant.selected;

    if (isWholeVariantSelected) {
      this.toastService.showWarningToast(
        'Variant Explorer',
        `A complete variant is selected. It will not be added.`,
        'bi-list-ul'
      );

      return;
    }

    let infixType: InfixType = getInfixTypeForSelectedInfix(variant);

    let newInfix = getSelectedChildren(variant.variant);
    let reducedInfix = removeIntermediateGroupsWithSingleElements(newInfix);
    if (!(reducedInfix instanceof SequenceGroup)) {
      // Every variant should be a sequence group
      reducedInfix = new SequenceGroup([reducedInfix]);
    }
    reducedInfix.parent = null;
    const newVariant = new Variant(
      0,
      reducedInfix,
      false,
      true,
      false,
      0,
      false,
      true,
      false,
      true,
      0,
      infixType
    );

    let currentVariants = this.variants;

    newVariant.alignment = undefined;
    newVariant.deviations = undefined;
    newVariant.id = objectHash(newVariant);

    const containsDuplicate =
      currentVariants.filter((v) => v.id === newVariant.id).length > 0;

    if (containsDuplicate) {
      this.toastService.showWarningToast(
        'Variant Explorer',
        `The selected infix is already present in the variant explorer. It will not be added.`,
        'bi-list-ul'
      );

      return;
    }

    this.nUserVariants += 1;
    newVariant.bid = -this.nUserVariants;

    this.addInfixToBackend(newVariant)
      .pipe(
        mergeMap(() => this.backendService.countFragmentOccurrences(newVariant))
      )
      .subscribe((statistics: FragmentStatistics) => {
        newVariant.count = statistics.traceOccurrences;
        newVariant.fragmentStatistics = statistics;
        currentVariants.push(newVariant);
        this.variants = currentVariants;

        let sortedVariants = VariantSorter.sort(
          this.variants,
          sortingFeature,
          isAscending
        ) as Variant[];

        this.toastService.showSuccessToast(
          'Variant Explorer',
          `The selected infix is added at position ${
            sortedVariants.indexOf(newVariant) + 1
          }.`,
          'bi-list-ul'
        );
        variant.variant.resetSelectionStatus();
      });
  }

  public deleteVariant(bid: number): void {
    this.deleteVariants([bid]).subscribe();
  }

  public deleteVariants(bids: number[]): Observable<any> {
    this.logService.logModifications.push(new VariantsDeletion(bids));
    return this.backendService.deleteVariants(bids).pipe(
      tap((res) => {
        this.logService.activitiesInEventLog = res['activities'];
        this.logService.startActivitiesInEventLog = new Set(
          res['startActivities']
        );
        this.logService.endActivitiesInEventLog = new Set(res['endActivities']);

        let filtered_variants = this.variants.filter(
          (v) => !bids.includes(v.bid)
        );

        this.logService.computeLogStats(filtered_variants);
        this.variants = filtered_variants;
        this.cachedChange = true;
      })
    );
    // Count deleted Activites, Recompute if an Activity is a Start or End Activity.
  }

  /**
   * Computes a mapping that maps the bid of each variant to
   * a cluster.
   * @param clusteringConfig
   * @returns mapping of each bid to a clusterId
   */
  private computeClusterClustering(clusteringConfig: ClusteringConfig) {
    this.backendService
      .computeClusters(clusteringConfig)
      .pipe(map(this.createBidToClusterIdMapping()))
      .subscribe((clusterMap) => {
        this.assignClusters(clusterMap);
      });
  }

  public assignClusters(clusterMap: any) {
    this.variants = this.variants.map((variant: Variant) => {
      variant.clusterId = clusterMap[variant.bid];
      return variant;
    });
  }

  private createBidToClusterIdMapping() {
    return (clusters: Variant[][]) => {
      let result = {};
      clusters.forEach((cluster, clusterId) => {
        cluster.forEach((variant) => (result[variant.bid] = clusterId));
      });
      return result;
    };
  }

  private resetClusterAssignments() {
    this.variants.forEach((variant) => {
      // undefined is the default cluster id when no algorithm was applied
      variant.clusterId = -1;
    });

    this.variants = this.variants;
  }

  public deleteActivity(activityName: string) {
    this.logService.logModifications.push(new ActivityDeletion(activityName));
    const [variants, fallthrough, delete_member_list, merge_list, delete_list] =
      compute_delete_activity_variants(activityName, this.variants);

    this.logService.deleteActivityInEventLog(activityName);

    return this.backendService
      .deleteActivity(
        activityName,
        fallthrough,
        delete_member_list,
        merge_list,
        delete_list.map((v) => v.bid)
      )
      .pipe(
        tap((res) => {
          this.logService.startActivitiesInEventLog = new Set(
            res['startActivities']
          );

          this.logService.endActivitiesInEventLog = new Set(
            res['endActivities']
          );

          variants.forEach((v) => {
            for (let bid of Object.keys(res['update_variants'])) {
              if (v.bid.toString() === bid) {
                v.nSubVariants = res['update_variants'][v.bid]['nSubVariants'];
                v.count = res['update_variants'][v.bid]['count'];
              }
            }
          });

          res['new_variants'].forEach((variant) => {
            variant['id'] = objectHash(variant['variant']);
            variant['variant'] = deserialize(variant.variant);
          });

          const new_variants = addVariantInformation(res['new_variants']);

          variants.push(...new_variants);

          this.cachedChange = true;
          this.logService.computeLogStats(variants);

          this.afterVariantChange();
          this.variants = variants;
        })
      );
  }

  public renameActivity(activityName: string, newActivityName: string) {
    this.logService.logModifications.push(
      new ActivityRenaming(activityName, newActivityName)
    );

    const [variants, rename_list, merge_list, updateMap] =
      compute_rename_activity_variants(
        activityName,
        newActivityName,
        this.variants
      );

    this.logService.renameActivitiesInEventLog(activityName, newActivityName);
    this.processTreeService.renameActivityInProcessTree(
      activityName,
      newActivityName
    );

    this.colorMapService.renameColorInActivityColorMap(
      activityName,
      newActivityName
    );

    return this.backendService
      .changeActivityName(
        merge_list,
        rename_list,
        activityName,
        newActivityName
      )
      .pipe(
        tap((res) => {
          variants.forEach((v) => {
            for (let bid of Object.keys(res)) {
              if (v.bid.toString() === bid) {
                v.nSubVariants = res[v.bid]['nSubVariants'];
              }
            }
          });

          this.afterVariantChange();
          this.variants = variants;

          this.logService.update_log_stats(null, null, null, updateMap.size);
          this.cachedChange = true;
          this.lastChangeRenaming = [activityName, newActivityName];
          this.nameChanges.next([activityName, newActivityName]);
        })
      );
  }

  revertChangeInBackend() {
    this.backendService.revertLastLogModification().subscribe((res) => {
      this.logService.activitiesInEventLog = res['activities'];
      this.logService.startActivitiesInEventLog = new Set(
        res['startActivities']
      );
      this.logService.endActivitiesInEventLog = new Set(res['endActivities']);

      this.logService.performanceInfoAvailable = true;
      this.logService.timeGranularity = res['timeGranularity'];
      this.logService.logGranularity = res['timeGranularity'];

      const lastNameChange = this.lastChangeRenaming;
      this.cachedChange = false;

      const variants = addVariantInformation(res['variants']);
      this.afterVariantChange();

      this.variants = variants;
      this.logService.computeLogStats(variants);
      if (lastNameChange !== null) {
        this.nameChanges.next([lastNameChange[1], lastNameChange[0]]);
      }
    });
  }

  public addUserDefinedVariant(variant: Variant) {
    this.logService.logModifications.push(
      new UserDefinedVariantAddition(variant)
    );
    return this.backendService.addUserDefinedVariant(variant).pipe(
      tap(
        (res) => console.log(res),
        (err) => console.log('error ' + err)
      )
    );
  }

  public expandCollapseLoopsInVariants() {
    if (this.areVariantLoopsCollapsed) {
      this.collapsedVariants = null;
    } else {
      this.loadLoopCollapsedVariants();
      this.toastService.showWarningToast(
        'Variant Explorer',
        `Disabled severeal features that are not applicable after collapsing loops.`,
        'bi-arrow-repeat'
      );
    }
    this.areVariantLoopsCollapsed = !this.areVariantLoopsCollapsed;
  }

  private loadLoopCollapsedVariants() {
    this.backendService.getCollapsedVariants().subscribe((res) => {
      let collapsedVariants = [];

      let bidToVariant = new Map<number, Variant>();
      for (let variant of this.variants) {
        bidToVariant.set(variant.bid, variant);
      }

      for (let idx in res) {
        let collapsedVariant = res[idx];

        let underlyingVariants = [];

        for (let bid of collapsedVariant['ids']) {
          underlyingVariants.push(bidToVariant.get(bid));
        }

        collapsedVariants.push(
          new LoopCollapsedVariant(
            uuidv4(),
            underlyingVariants,
            deserialize(collapsedVariant['variant'])
          )
        );
      }

      this.collapsedVariants = collapsedVariants;
    });
  }

  public addInfixToBackend(variant: Variant) {
    this.logService.logModifications.push(
      new UserDefinedInfixAddition(variant)
    );
    return this.backendService.addUserDefinedInfix(variant).pipe(
      tap(
        (_) => console.log('successfully added infix to backend'),
        (_) =>
          this.toastService.showErrorToast(
            'Variant Explorer',
            `Adding the selected infix failed`,
            'bi-exclamation-circle'
          )
      )
    );
  }
}
