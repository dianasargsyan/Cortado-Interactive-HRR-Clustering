import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { Variant } from 'src/app/objects/Variants/variant';
import { LogService } from '../logService/log.service';
import { VariantService } from '../variantService/variant.service';

class UnionFind {
  private parent = new Map<number, number>();

  find(x: number): number {
    if (!this.parent.has(x)) this.parent.set(x, x);
    if (this.parent.get(x) !== x) {
      this.parent.set(x, this.find(this.parent.get(x)!));
    }
    return this.parent.get(x)!;
  }

  union(x: number, y: number): void {
    this.parent.set(this.find(x), this.find(y));
  }

  connected(x: number, y: number): boolean {
    return this.find(x) === this.find(y);
  }
}

@Injectable({ providedIn: 'root' })
export class ConstraintService {
  private _mustLink = new BehaviorSubject<[number, number][]>([]);
  private _cannotLink = new BehaviorSubject<[number, number][]>([]);

  mustLink$ = this._mustLink.asObservable();
  cannotLink$ = this._cannotLink.asObservable();

  constructor(private logService: LogService, private variantService: VariantService) {
    // Constraints refer to variants by their bid, so they only hold for the log they were set on
    this.logService.loadedEventLog$.subscribe(() => this.clearAll());
    this.variantService.variants$.subscribe((variants) => this.removeMissingVariants(variants));
  }

  get mustLink(): [number, number][] {
    return this._mustLink.value;
  }

  get cannotLink(): [number, number][] {
    return this._cannotLink.value;
  }

  private pairExists(list: [number, number][], bid1: number, bid2: number): boolean {
    return list.some(([a, b]) => (a === bid1 && b === bid2) || (a === bid2 && b === bid1));
  }

  private buildUnionFind(mustLinks: [number, number][]): UnionFind {
    const uf = new UnionFind();
    for (const [a, b] of mustLinks) {
      uf.union(a, b);
    }
    return uf;
  }

  /** Returns an error message string if the constraint cannot be added, otherwise null. */
  addMustLink(bid1: number, bid2: number): string | null {
    if (this.pairExists(this._cannotLink.value, bid1, bid2)) {
      return 'This pair already has a cannot-link constraint.';
    }
    if (this.pairExists(this._mustLink.value, bid1, bid2)) {
      return 'This must-link constraint already exists.';
    }
    const uf = this.buildUnionFind([...this._mustLink.value, [bid1, bid2]]);
    for (const [a, b] of this._cannotLink.value) {
      if (uf.connected(a, b)) {
        return `Transitive conflict: adding this must-link would put #${a + 1} and #${b + 1} (cannot-link) into the same group.`;
      }
    }
    const updated = [...this._mustLink.value, [bid1, bid2] as [number, number]];
    this._mustLink.next(updated);
    return null;
  }

  /** Returns an error message string if the constraint cannot be added, otherwise null. */
  addCannotLink(bid1: number, bid2: number): string | null {
    if (this.pairExists(this._mustLink.value, bid1, bid2)) {
      return 'This pair already has a must-link constraint.';
    }
    if (this.pairExists(this._cannotLink.value, bid1, bid2)) {
      return 'This cannot-link constraint already exists.';
    }
    const uf = this.buildUnionFind(this._mustLink.value);
    if (uf.connected(bid1, bid2)) {
      return `Transitive conflict: #${bid1 + 1} and #${bid2 + 1} are already in the same must-link group.`;
    }
    const updated = [...this._cannotLink.value, [bid1, bid2] as [number, number]];
    this._cannotLink.next(updated);
    return null;
  }

  removeMustLink(bid1: number, bid2: number): void {
    const updated = this._mustLink.value.filter(
      ([a, b]) => !((a === bid1 && b === bid2) || (a === bid2 && b === bid1))
    );
    this._mustLink.next(updated);
  }

  removeCannotLink(bid1: number, bid2: number): void {
    const updated = this._cannotLink.value.filter(
      ([a, b]) => !((a === bid1 && b === bid2) || (a === bid2 && b === bid1))
    );
    this._cannotLink.next(updated);
  }

  clearAll(): void {
    this._mustLink.next([]);
    this._cannotLink.next([]);
  }

  /** Drops the constraints of variants that were deleted or merged into another variant. */
  private removeMissingVariants(variants: Variant[]): void {
    const bids = new Set(variants.map((v) => v.bid));
    const present = (list: [number, number][]) => list.filter(([a, b]) => bids.has(a) && bids.has(b));

    const mustLink = present(this._mustLink.value);
    if (mustLink.length < this._mustLink.value.length) this._mustLink.next(mustLink);

    const cannotLink = present(this._cannotLink.value);
    if (cannotLink.length < this._cannotLink.value.length) this._cannotLink.next(cannotLink);
  }
}
