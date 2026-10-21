import { ActivityField } from 'src/app/components/activity-overview/activity-overview.component';
import {
  Component,
  Input,
  AfterViewInit,
  OnChanges,
  OnDestroy,
} from '@angular/core';
import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';
import { takeUntil } from 'rxjs/operators';
import { Subject } from 'rxjs';

@Component({
  selector: 'app-activity-overview-info-bar',
  template: ` <div class="info-bar ps-2 pe-2">
    <span class="float-end" *ngIf="totalActivities"
      >Activities in model: {{ numActivitiesInModel }}/{{ totalActivities }} ({{
        ((numActivitiesInModel * 100) / totalActivities).toFixed(1)
      }}
      %)</span
    >
  </div>`,
})
export class InfoBarComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input()
  activityFields: ActivityField[];

  numActivitiesInModel: number;
  totalActivities: number;

  private _destroy$ = new Subject();

  constructor(private processTreeService: ProcessTreeService) {}

  ngOnChanges(): void {
    this.totalActivities = this.activityFields.length;
  }

  ngAfterViewInit(): void {
    // Handle change of current activies in the loaded model
    this.processTreeService.activitiesInCurrentTree$
      .pipe(takeUntil(this._destroy$))
      .subscribe((activitiesInTree) => {
        this.numActivitiesInModel = this.activityFields.filter((act) =>
          activitiesInTree.has(act.activityName)
        ).length;
      });
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }
}
