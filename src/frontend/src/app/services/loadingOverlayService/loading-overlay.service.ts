import { EventEmitter, Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class LoadingOverlayService {
  public loadingText = '';
  public loadingInProgress = false;

  loadingInProgressEvent = new EventEmitter();

  public showLoader(text = '') {
    this.loadingText = text;
    this.loadingInProgress = true;
    this.loadingInProgressEvent.emit(this.loadingInProgress);
  }

  public hideLoader() {
    this.loadingInProgress = false;
    this.loadingText = '';
    this.loadingInProgressEvent.emit(this.loadingInProgress);
  }
}
