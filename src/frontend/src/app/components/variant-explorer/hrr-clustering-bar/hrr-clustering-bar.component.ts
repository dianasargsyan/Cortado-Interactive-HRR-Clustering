import { Component } from '@angular/core';
import { HRRClusteringResult } from 'src/app/objects/HRRClustering';
import { HRRClusteringService } from 'src/app/services/hrrClusteringService/hrr-clustering.service';

@Component({
  selector: 'app-hrr-clustering-bar',
  templateUrl: './hrr-clustering-bar.component.html',
  styleUrls: ['./hrr-clustering-bar.component.scss'],
})
export class HRRClusteringBarComponent {
  levels = [
    { value: 0, name: 'off' },
    { value: 0.5, name: 'half' },
    { value: 1, name: 'full' },
  ];

  constructor(public hrrClusteringService: HRRClusteringService) {}

  setNClusters(value: string) {
    this.hrrClusteringService.setNClusters(Math.round(Number(value)));
  }

  status(result: HRRClusteringResult): string {
    if (this.hrrClusteringService.restored) {
      return 'Restored the clustering of this state';
    }
    const seconds = result.seconds.total.toFixed(2);
    if (result.fromScratch) {
      return `Clustered from scratch in ${seconds} s`;
    }
    const moved = result.moved === 1 ? 'variant' : 'variants';
    return `Reclustered in ${seconds} s; ${result.moved} ${moved} changed cluster`;
  }
}
