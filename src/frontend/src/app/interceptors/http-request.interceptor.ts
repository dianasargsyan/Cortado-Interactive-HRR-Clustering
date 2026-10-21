import { Injectable } from '@angular/core';
import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, finalize } from 'rxjs/operators';
import { BackgroundTaskInfoService } from '../services/backgroundTaskInfoService/background-task-info.service';
import { BackendService } from '../services/backendService/backend.service';
import { ErrorService } from '../services/errorService/error.service';
import { BackendInfoService } from '../services/backendInfoService/backend-info.service';
import { ROUTES } from '../constants/backend_route_constants';

@Injectable()
export class HttpRequestInterceptor implements HttpInterceptor {
  private excludedEndpointsForTaskCounter = ['info', 'log/reset Log Cache'];
  private endpointsToCancelBeforeInterception = [
    'subvariant Mining/repetitions Mining',
  ];

  constructor(
    private backgroundTaskInfoService: BackgroundTaskInfoService,
    private backendService: BackendService,
    private errorService: ErrorService,
    private backendInfoService: BackendInfoService
  ) {}

  intercept(
    request: HttpRequest<unknown>,
    next: HttpHandler
  ): Observable<HttpEvent<unknown>> {
    const calledEndpoint = request.url
      .slice(ROUTES.HTTP_BASE_URL.length)
      .replace(/([a-z0-9])([A-Z])/g, '$1 $2');

    if (this.shouldCancelEndpoints(calledEndpoint)) {
      this.backendService.cancelOtherBgTasks.next();
    }

    let id;
    if (!this.shouldIgnoreRequestForTaskCounter(calledEndpoint)) {
      id = this.backgroundTaskInfoService.setRequest(String(calledEndpoint));
    }

    return next.handle(request).pipe(
      catchError((error: HttpErrorResponse) => {
        this.setBackendRunningState(error);
        if (this.shouldIgnoreError(error)) {
          return next.handle(request);
        }

        this.errorService.addApiError(error);
        return throwError(error);
      }),
      finalize(() => {
        if (id) {
          this.backgroundTaskInfoService.removeRequest(id);
        }
      })
    );
  }

  shouldIgnoreError(error: HttpErrorResponse): boolean {
    return (
      // ignore timeouts for alignment computations because they are handled in the variant explorer
      (error.status == 504 &&
        error.url?.endsWith('calculateAlignmentsCVariant')) ||
      // info requests are made to show the backend state in the footer; therefore, we do not want to show the error dialog
      error.url?.endsWith('/info') ||
      error.url?.endsWith('resetLogCache') ||
      // ignore FileNotFoundError while loading EventLog because of handling in caller
      (error.status == 404 && error.url?.endsWith('/loadEventLogFromFilePath'))
    );
  }

  shouldIgnoreRequestForTaskCounter(endpoint: string): boolean {
    return this.excludedEndpointsForTaskCounter.includes(endpoint);
  }

  shouldCancelEndpoints(endpoint: string): boolean {
    const activeRequestToBeCancelledExists =
      Array.from(this.backgroundTaskInfoService.activeRequests.values())?.find(
        (task) =>
          this.endpointsToCancelBeforeInterception.includes(task.Description)
      ) !== undefined;
    return (
      activeRequestToBeCancelledExists &&
      !this.endpointsToCancelBeforeInterception.includes(endpoint) &&
      !this.shouldIgnoreRequestForTaskCounter(endpoint)
    );
  }

  setBackendRunningState(error: HttpErrorResponse): void {
    let isRunning = true;
    if (error.status === 0) {
      isRunning = false;
    }

    this.backendInfoService.setRunning(isRunning);
  }
}
