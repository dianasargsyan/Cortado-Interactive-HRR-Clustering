import { Component, Input } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';

interface MustLinkGroup {
  members: number[];
}

@Component({
  selector: 'app-constraint-overview-dialog',
  templateUrl: './constraint-overview-dialog.component.html',
  styleUrls: ['./constraint-overview-dialog.component.scss'],
})
export class ConstraintOverviewDialogComponent {
  @Input() mustLink: [number, number][] = [];
  @Input() cannotLink: [number, number][] = [];

  constructor(public activeModal: NgbActiveModal) {}

  get mustLinkGroups(): MustLinkGroup[] {
    const parent = new Map<number, number>();

    const find = (x: number): number => {
      if (!parent.has(x)) parent.set(x, x);
      if (parent.get(x) !== x) parent.set(x, find(parent.get(x)!));
      return parent.get(x)!;
    };

    for (const [a, b] of this.mustLink) {
      parent.set(find(a), find(b));
    }

    const groups = new Map<number, Set<number>>();
    for (const [a, b] of this.mustLink) {
      const root = find(a);
      if (!groups.has(root)) groups.set(root, new Set());
      groups.get(root)!.add(a);
      groups.get(root)!.add(b);
    }

    return Array.from(groups.values())
      .map(set => ({ members: Array.from(set).sort((x, y) => x - y) }))
      .sort((a, b) => b.members.length - a.members.length);
  }

  get cannotLinkPairs(): [number, number][] {
    return this.cannotLink.map(([a, b]) => [Math.min(a, b), Math.max(a, b)] as [number, number]);
  }
}
