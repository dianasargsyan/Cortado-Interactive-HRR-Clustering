import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { distinctUntilChanged } from 'rxjs/operators';

@Injectable({
  providedIn: 'root',
})
export class VariantQueryService {
  //TODO Refactor more Code from VariantQueryComponent into this Service
  constructor() {}

  private _variantQuery: BehaviorSubject<string> = new BehaviorSubject<string>(
    ''
  );

  set variantQuery(nextQuery: string) {
    if (this.variantQuery !== nextQuery) {
      this._variantQuery.next(nextQuery);
    }
  }

  get variantQuery() {
    return this._variantQuery.value;
  }

  get variantQuery$() {
    return this._variantQuery.pipe(distinctUntilChanged());
  }
}
