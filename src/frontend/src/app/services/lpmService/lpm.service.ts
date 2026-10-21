import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { LocalProcessModelWithPatterns } from 'src/app/objects/LocalProcessModelWithPatterns';
import { LpmMetrics } from 'src/app/objects/LpmMetrics';

@Injectable({
  providedIn: 'root',
})
export class LpmService {
  private _localProcessModels = new BehaviorSubject<
    LocalProcessModelWithPatterns[]
  >([]);

  private _lpmMetrics = new BehaviorSubject<LpmMetrics>(null);

  set localProcessModels(lpms: LocalProcessModelWithPatterns[]) {
    this._localProcessModels.next(lpms);
  }

  get localProcessModels$(): Observable<LocalProcessModelWithPatterns[]> {
    return this._localProcessModels.asObservable();
  }

  set lpmMetrics(metrics: LpmMetrics) {
    this._lpmMetrics.next(metrics);
  }

  get lpmMetrics$(): Observable<LpmMetrics> {
    return this._lpmMetrics.asObservable();
  }
}
