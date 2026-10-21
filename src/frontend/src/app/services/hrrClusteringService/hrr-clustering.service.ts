import { Injectable } from '@angular/core';
import { BehaviorSubject, combineLatest } from 'rxjs';
import { debounceTime, skip } from 'rxjs/operators';
import { ClusteringAlgorithm } from 'src/app/objects/ClusteringAlgorithm';
import {
  HRRClusteringRequest,
  HRRClusteringResult,
} from 'src/app/objects/HRRClustering';
import { BackendService } from '../backendService/backend.service';
import { ConstraintService } from '../constraintService/constraint.service';
import { LogService } from '../logService/log.service';
import { VariantService } from '../variantService/variant.service';

export type HRRSettings = {
  nClusters: number;
  order: number;
  nesting: number;
  sameActivities: string[][];
  ignoredActivities: string[];
};

const DEFAULT_SETTINGS: HRRSettings = {
  nClusters: 5,
  order: 1,
  nesting: 1,
  sameActivities: [],
  ignoredActivities: [],
};

type ClusterAssignment = { [bid: number]: number };

@Injectable({ providedIn: 'root' })
export class HRRClusteringService {
  private _settings = new BehaviorSubject<HRRSettings>(DEFAULT_SETTINGS);
  private _result = new BehaviorSubject<HRRClusteringResult>(null);
  private _changes = new BehaviorSubject<Map<number, [number, number]>>(
    new Map()
  );
  private seen = new Map<
    string,
    { assignment: ClusterAssignment; result: HRRClusteringResult }
  >();

  settings$ = this._settings.asObservable();
  result$ = this._result.asObservable();
  changes$ = this._changes.asObservable();
  restored = false;
  private movedFromCluster = new Map<number, number>();

  constructor(
    private variantService: VariantService,
    private backendService: BackendService,
    private constraintService: ConstraintService,
    private logService: LogService
  ) {
    this.variantService.clusteringConfig$.subscribe((config) => {
      if (config?.algorithm === ClusteringAlgorithm.HRR_CLUSTERING) {
        this.updateSettings(
          {
            nClusters: config.params.nClusters,
            order: config.params.order,
            nesting: config.params.nesting,
          },
          false
        );
        this.recluster(true);
      } else {
        this._result.next(null);
      }
    });

    combineLatest([
      this.constraintService.mustLink$,
      this.constraintService.cannotLink$,
    ])
      // a new log clears the constraints before the clustering is switched off
      .pipe(skip(1), debounceTime(0))
      .subscribe(() => {
        if (this.active) this.recluster();
      });

    this.logService.loadedEventLog$.subscribe(() => {
      this.seen.clear();
      this.movedFromCluster.clear();
      this.updateSettings({ sameActivities: [], ignoredActivities: [] }, false);
    });
  }

  get settings(): HRRSettings {
    return this._settings.value;
  }

  get result(): HRRClusteringResult {
    return this._result.value;
  }

  get active(): boolean {
    return (
      this.variantService.clusteringConfig?.algorithm ===
      ClusteringAlgorithm.HRR_CLUSTERING
    );
  }

  setOrder(order: number) {
    this.updateSettings({ order });
  }

  setNesting(nesting: number) {
    this.updateSettings({ nesting });
  }

  setNClusters(nClusters: number) {
    if (nClusters >= 1) this.updateSettings({ nClusters });
  }

  addSameActivities(activities: string[]) {
    const group = new Set(activities);
    const sameActivities = [];
    for (const other of this.settings.sameActivities) {
      if (other.some((a) => group.has(a))) other.forEach((a) => group.add(a));
      else sameActivities.push(other);
    }
    sameActivities.push([...group].sort());
    this.updateSettings({ sameActivities });
  }

  removeSameActivities(group: string[]) {
    this.updateSettings({
      sameActivities: this.settings.sameActivities.filter((g) => g !== group),
    });
  }

  toggleIgnored(activity: string) {
    const ignored = this.settings.ignoredActivities;
    const group = this.sameGroupOf(activity);
    this.updateSettings({
      ignoredActivities: this.isIgnored(activity)
        ? ignored.filter((a) => !group.includes(a))
        : [...ignored, activity].sort(),
    });
  }

  movedFrom(bid: number): number | undefined {
    return this.active ? this.movedFromCluster.get(bid) : undefined;
  }

  isIgnored(activity: string): boolean {
    return this.sameGroupOf(activity).some((a) =>
      this.settings.ignoredActivities.includes(a)
    );
  }

  private sameGroupOf(activity: string): string[] {
    return (
      this.settings.sameActivities.find((g) => g.includes(activity)) ?? [
        activity,
      ]
    );
  }

  recluster(fromScratch = false) {
    const request = this.createRequest(fromScratch);
    const key = this.stateKey(request);
    const seen = this.seen.get(key);
    if (seen && !fromScratch) {
      this.apply(seen.result, seen.assignment, request.previousClusters, true);
      return;
    }

    this.backendService.computeHRRClusters(request).subscribe((result) => {
      const assignment: ClusterAssignment = {};
      result.clusters.forEach((members, c) =>
        members.forEach((bid) => (assignment[bid] = c))
      );
      result.noActivities.forEach(
        (bid) => (assignment[bid] = result.clusters.length)
      );
      this.seen.set(key, { assignment, result });
      this.apply(result, assignment, request.previousClusters, false);
    });
  }

  private apply(
    result: HRRClusteringResult,
    assignment: ClusterAssignment,
    previous: ClusterAssignment,
    restored: boolean
  ) {
    const changes = new Map<number, [number, number]>();
    const movedFrom = new Map<number, number>();
    if (!result.fromScratch && Object.keys(previous).length > 0) {
      result.clusters.forEach((_, c) => changes.set(c, [0, 0]));
      for (const [bid, cluster] of Object.entries(assignment)) {
        const before = previous[bid];
        if (before !== undefined && before !== cluster) {
          movedFrom.set(Number(bid), before);
          if (changes.has(cluster)) changes.get(cluster)[0]++;
          if (changes.has(before)) changes.get(before)[1]++;
        }
      }
    }

    this.restored = restored;
    this.movedFromCluster = movedFrom;
    this.variantService.assignClusters(assignment);
    this._changes.next(changes);
    this._result.next(result);
  }

  private createRequest(fromScratch: boolean): HRRClusteringRequest {
    const k = this.result?.clusters.length;
    const previousClusters: ClusterAssignment = {};
    for (const variant of this.variantService.variants) {
      if (variant.clusterId >= 0 && variant.clusterId < k) {
        previousClusters[variant.bid] = variant.clusterId;
      }
    }

    return {
      ...this.settings,
      mustLink: this.constraintService.mustLink,
      cannotLink: this.constraintService.cannotLink,
      previousClusters,
      fromScratch,
    };
  }

  private stateKey(request: HRRClusteringRequest): string {
    const pairs = (list: [number, number][]) =>
      list.map(([a, b]) => [Math.min(a, b), Math.max(a, b)]).sort();
    return JSON.stringify([
      request.nClusters,
      request.order,
      request.nesting,
      request.sameActivities.map((g) => [...g].sort()).sort(),
      [...request.ignoredActivities].sort(),
      pairs(request.mustLink),
      pairs(request.cannotLink),
    ]);
  }

  private updateSettings(change: Partial<HRRSettings>, recluster = true) {
    const settings = { ...this.settings, ...change };
    this._settings.next(settings);
    if (recluster && this.active) this.recluster();
  }
}
