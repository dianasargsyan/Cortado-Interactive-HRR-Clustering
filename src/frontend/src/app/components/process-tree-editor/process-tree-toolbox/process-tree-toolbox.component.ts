import {
  Component,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
} from '@angular/core';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { PT_Constant } from 'src/app/constants/process_tree_drawer_constants';
import { ProcessTreeOperator } from 'src/app/objects/ProcessTree/ProcessTree';
import { ProcessTree } from 'src/app/objects/ProcessTree/ProcessTree';
import { ColorMapService } from 'src/app/services/colorMapService/color-map.service';
import { LogService } from 'src/app/services/logService/log.service';
import { textColorForBackgroundColor } from 'src/app/utils/render-utils';

@Component({
  selector: 'app-process-tree-toolbox',
  templateUrl: './process-tree-toolbox.component.html',
  styleUrls: ['./process-tree-toolbox.component.css'],
})
export class ProcessTreeToolboxComponent implements OnDestroy {
  readonly operatorNodeColor = PT_Constant.OPERATOR_COLOR;
  readonly operatorTextColor = textColorForBackgroundColor(
    PT_Constant.OPERATOR_COLOR
  );
  readonly ProcessTreeOperator = ProcessTreeOperator;

  processTreeOperators: ProcessTreeOperator[];
  processTreeActivities: string[];

  showToolbox: boolean = false;

  @Input() operatorInsertionDisabled = false;
  @Output() operatorInsertion = new EventEmitter<string>();

  @Input() activityInsertionDisabled = false;
  @Output() activityInsertion = new EventEmitter<string>();

  private _destroy$ = new Subject();

  constructor(
    private colorMapService: ColorMapService,
    private logService: LogService
  ) {
    this.processTreeOperators = [
      ProcessTreeOperator.sequence,
      ProcessTreeOperator.parallelism,
      ProcessTreeOperator.choice,
      ProcessTreeOperator.loop,
    ];

    this.logService.activitiesInEventLog$
      .pipe(takeUntil(this._destroy$))
      .subscribe((activities) => {
        this.processTreeActivities = Object.keys(activities);
      });
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }

  insertOperatorNode(operator: string) {
    this.operatorInsertion.emit(operator);
  }

  insertActivityNode(activity: string) {
    this.activityInsertion.emit(activity);
  }

  computeActivityColor(activity: string) {
    if (activity === ProcessTreeOperator.tau)
      return PT_Constant.INVISIBLE_ACTIVTIY_COLOR;
    return this.colorMapService.colorMap?.get(activity);
  }

  computeTextColor(activity: string) {
    return textColorForBackgroundColor(this.computeActivityColor(activity));
  }

  tooltipContent = (d: d3.HierarchyNode<ProcessTree>) => {
    return d.data.label || d.data.operator;
  };
}
