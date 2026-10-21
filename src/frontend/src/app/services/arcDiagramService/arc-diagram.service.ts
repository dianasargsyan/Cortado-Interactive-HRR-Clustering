import { Injectable } from '@angular/core';
import { BackgroundTaskInfoService } from '../backgroundTaskInfoService/background-task-info.service';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { ArcDiagramComputationResult } from './model';
import { Observable } from 'rxjs';
import { FilterParams } from '../../components/variant-explorer/arc-diagram/filter/filter-params';
import { ROUTES } from '../../constants/backend_route_constants';
import { catchError, map, tap } from 'rxjs/operators';
import Swal from 'sweetalert2';

@Injectable({
  providedIn: 'root',
})
export class ArcDiagramService {
  constructor(private infoService: BackgroundTaskInfoService) {}

  private socket: WebSocketSubject<any>;
  private runningRequests: number[] = [];

  public arcDiagramsResult: Observable<ArcDiagramComputationResult>;

  public connect(): boolean {
    if (!this.socket || this.socket.closed) {
      this.socket = webSocket(
        ROUTES.WS_HTTP_BASE_URL + ROUTES.REPETITIONS_MINING
      );
      this.arcDiagramsResult = this.socket.pipe(
        catchError((error) => {
          this.runningRequests.forEach((r: number) =>
            this.infoService.removeRequest(r)
          );
          this.runningRequests = [];
          this.socket = null;

          throw error;
        }),
        tap((_) => {
          this.infoService.removeRequest(this.runningRequests.pop());
        }),
        map((result) => {
          if ('error' in result) {
            Swal.fire({
              title: 'Error occurred',
              html:
                '<b>Error message: </b><br>' +
                '<code>' +
                'Calculating arc diagrams failed' +
                '</code>',
              icon: 'error',
              showCloseButton: false,
              showConfirmButton: false,
              showCancelButton: true,
              cancelButtonText: 'close',
            });
            return result;
          }
          return new ArcDiagramComputationResult(
            result['pairs'],
            result['maximal_values']
          );
        })
      );

      return true;
    }

    return false;
  }

  public computeArcDiagrams(
    bids: string[] | number[],
    filterParams: FilterParams
  ): boolean {
    const resubscribe = this.connect();
    const rid = this.infoService.setRequest('repetitions mining', () =>
      this.cancelArcDiagramComputationRequests()
    );
    this.runningRequests.push(rid);
    this.socket.next({
      name: 'repetition_mining',
      bids,
      filters: {
        activitiesToInclude: Array.from(
          filterParams ? filterParams.activitiesSelection.selectedItems : []
        ),
      },
    });

    return resubscribe;
  }

  private cancelArcDiagramComputationRequests(): void {
    this.socket.next({ isCancellationRequested: true });
    this.runningRequests.forEach((r: number) =>
      this.infoService.removeRequest(r)
    );
    this.runningRequests = [];
    this.socket.unsubscribe();
  }
}
