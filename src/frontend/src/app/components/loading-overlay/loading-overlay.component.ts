import { Component, OnDestroy, OnInit } from '@angular/core';
import { LoadingOverlayService } from 'src/app/services/loadingOverlayService/loading-overlay.service';

@Component({
  selector: 'app-loading-overlay',
  templateUrl: './loading-overlay.component.html',
  styleUrls: ['./loading-overlay.component.css'],
})
export class LoadingOverlayComponent implements OnInit, OnDestroy {
  loadingInProgressEvent: any;
  loadingInProgress: boolean = false;

  constructor(public loadingOverlayService: LoadingOverlayService) {}

  ngOnInit() {
    this.loadingInProgressEvent =
      this.loadingOverlayService.loadingInProgressEvent.subscribe((event) => {
        this.loadingInProgress = event;
      });
  }

  ngOnDestroy() {
    this.loadingInProgressEvent.unsubscribe();
  }
}
