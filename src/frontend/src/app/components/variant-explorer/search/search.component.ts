import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';

@Component({
  selector: 'app-search',
  templateUrl: './search.component.html',
  styleUrls: ['./search.component.scss'],
})
export class SearchComponent implements OnInit {
  // default values
  @Input()
  isAscendingOrder: any = false;
  @Input()
  sortingFeature: any = 'count';

  @Output()
  public sortEvent: EventEmitter<any> = new EventEmitter();

  constructor() {}

  ngOnInit(): void {
    this.emit();
  }

  onSortOrderChanged(isAscendingOrder: boolean) {
    this.isAscendingOrder = isAscendingOrder;
    this.emit();
  }

  sort(feature: string) {
    this.sortingFeature = feature;
    this.emit();
  }

  emit() {
    this.sortEvent.emit({
      isAscendingOrder: this.isAscendingOrder,
      feature: this.sortingFeature,
    });
  }
}
