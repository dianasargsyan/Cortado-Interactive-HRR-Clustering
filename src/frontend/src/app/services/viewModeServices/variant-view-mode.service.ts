import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { distinctUntilChanged } from 'rxjs/operators';
import { ViewMode } from 'src/app/objects/ViewMode';
import { ConformanceCheckingService } from '../conformanceChecking/conformance-checking.service';
import { PerformanceService } from '../performance.service';
import { ModelViewModeService } from './model-view-mode.service';

@Injectable({
  providedIn: 'root',
})
export class VariantViewModeService {
  constructor(
    private modelViewModeService: ModelViewModeService,
    private conformanceCheckingService: ConformanceCheckingService,
    private performanceService: PerformanceService
  ) {}

  private _viewMode: BehaviorSubject<ViewMode> = new BehaviorSubject<ViewMode>(
    ViewMode.STANDARD
  );

  set viewMode(nextViewMode: ViewMode) {
    if (this.viewMode !== nextViewMode) {
      this._viewMode.next(nextViewMode);

      if (
        (nextViewMode === ViewMode.CONFORMANCE &&
          !this.conformanceCheckingService.anyTreeConformanceActive()) ||
        (nextViewMode === ViewMode.PERFORMANCE &&
          !this.performanceService.anyTreePerformanceActive())
      ) {
        this.modelViewModeService.viewMode = ViewMode.STANDARD;
      } else {
        this.modelViewModeService.viewMode = nextViewMode;
      }
    }
  }

  get viewMode() {
    return this._viewMode.value;
  }

  get viewMode$() {
    return this._viewMode.pipe(distinctUntilChanged());
  }
}
