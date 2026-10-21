import {
  ChangeDetectionStrategy,
  Component,
  Input,
  OnInit,
} from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { ClusteringAlgorithm } from 'src/app/objects/ClusteringAlgorithm';
import { VariantService } from 'src/app/services/variantService/variant.service';
import { DocumentationService } from '../../documentation/documentation.service';
import { ConstraintService } from 'src/app/services/constraintService/constraint.service';
import { HRRClusteringService } from 'src/app/services/hrrClusteringService/hrr-clustering.service';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-clustering-settings-dialog',
  templateUrl: './clustering-settings-dialog.component.html',
  styleUrls: ['./clustering-settings-dialog.component.scss'],
})
export class ClusteringSettingsDialogComponent implements OnInit {
  @Input()
  numberOfVariants!: number;

  selectedClusteringAlgorithm: ClusteringAlgorithm =
    ClusteringAlgorithm.AGGLOMERATIVE_EDIT_DISTANCE_CLUSTERING;

  options: ClusteringAlgorithm[] = Object.values(ClusteringAlgorithm);

  maxDistance: number = 1;
  nClusters: number = 1;
  order: number = 1;
  nesting: number = 1;

  levels = [
    { value: 0, name: 'off' },
    { value: 0.5, name: 'half' },
    { value: 1, name: 'full' },
  ];

  constructor(
    public modal: NgbActiveModal,
    private variantService: VariantService,
    private documentationService: DocumentationService,
    public constraintService: ConstraintService,
    private hrrClusteringService: HRRClusteringService
  ) {}

  ngOnInit(): void {
    const clusteringConfig = this.variantService.clusteringConfig;
    if (clusteringConfig) {
      this.selectedClusteringAlgorithm = clusteringConfig.algorithm;

      if (
        this.selectedClusteringAlgorithm ===
        ClusteringAlgorithm.AGGLOMERATIVE_EDIT_DISTANCE_CLUSTERING
      ) {
        this.maxDistance = clusteringConfig.params.maxDistance;
      } else if (
        this.selectedClusteringAlgorithm ===
        ClusteringAlgorithm.LABEL_VECTOR_CLUSTERING
      ) {
        this.nClusters = clusteringConfig.params.nClusters;
      } else if (
        this.selectedClusteringAlgorithm === ClusteringAlgorithm.HRR_CLUSTERING
      ) {
        const settings = this.hrrClusteringService.settings;
        this.nClusters = settings.nClusters;
        this.order = settings.order;
        this.nesting = settings.nesting;
      }
    }
  }

  getDisplayName(algo: ClusteringAlgorithm) {
    switch (algo) {
      case ClusteringAlgorithm.AGGLOMERATIVE_EDIT_DISTANCE_CLUSTERING:
        return 'Agglomerative edit distance clustering';
      case ClusteringAlgorithm.LABEL_VECTOR_CLUSTERING:
        return 'Label vector clustering';
      case ClusteringAlgorithm.HRR_CLUSTERING:
        return 'HRR clustering (COP-KMeans)';
    }
  }

  usesNumberOfClusters(): boolean {
    return (
      this.selectedClusteringAlgorithm ===
        ClusteringAlgorithm.LABEL_VECTOR_CLUSTERING ||
      this.selectedClusteringAlgorithm === ClusteringAlgorithm.HRR_CLUSTERING
    );
  }

  onApply() {
    const params: any = {};

    if (
      this.selectedClusteringAlgorithm ==
      ClusteringAlgorithm.AGGLOMERATIVE_EDIT_DISTANCE_CLUSTERING
    ) {
      params['maxDistance'] = this.maxDistance;
    } else if (
      this.selectedClusteringAlgorithm ==
      ClusteringAlgorithm.LABEL_VECTOR_CLUSTERING
    ) {
      params['nClusters'] = this.nClusters;
    } else if (
      this.selectedClusteringAlgorithm == ClusteringAlgorithm.HRR_CLUSTERING
    ) {
      params['nClusters'] = this.nClusters;
      params['order'] = this.order;
      params['nesting'] = this.nesting;
    }

    const mustLink = this.constraintService.mustLink;
    const cannotLink = this.constraintService.cannotLink;

    this.variantService.clusteringConfig = {
      algorithm: this.selectedClusteringAlgorithm,
      params,
      constraints:
        mustLink.length > 0 || cannotLink.length > 0
          ? { mustLink, cannotLink }
          : undefined,
    };

    this.modal.close();
  }

  onReset() {
    this.variantService.clusteringConfig = null as any;
    this.modal.dismiss('reset');
  }

  openDocumentation(heading: string) {
    this.documentationService.showDocumentationDialog(heading);
    this.modal.dismiss('cancel click');
  }
}
