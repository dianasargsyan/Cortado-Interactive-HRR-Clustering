import { Injectable } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { LogExporterDialogComponent } from 'src/app/components/log-exporter-dialog/log-exporter-dialog/log-exporter-dialog.component';
import { LogExportConfig } from 'src/app/objects/LogExportConfig/LogExportConfig';
import { VariantSelectionMethod } from 'src/app/objects/VariantSelectionMethod';
import { BackendService } from '../backendService/backend.service';
import { ElectronService } from '../electronService/electron.service';
import { take } from 'rxjs/operators';
import { VariantService } from '../variantService/variant.service';
import { InfixType } from 'src/app/objects/Variants/infix_selection';

@Injectable({
  providedIn: 'root',
})
export class LogExportService {
  constructor(
    private backendService: BackendService,
    private variantService: VariantService,
    private modalService: NgbModal,
    private electronService: ElectronService
  ) {}

  showLogExportDialog() {
    this.modalService
      .open(LogExporterDialogComponent, { size: 'lg' })
      .result.then(
        (config: LogExportConfig) => this.exportLog(config),
        () => {}
      );
  }

  exportLog(config: LogExportConfig) {
    const variants = this.variantService.variants;
    const bids = variants
      .filter((variant) => {
        switch (config.variantSelectionMethod) {
          case VariantSelectionMethod.ALL:
            return true;

          case VariantSelectionMethod.SELECTED:
            return variant.isSelected;

          case VariantSelectionMethod.FITTING:
            return variant.deviations == 0;

          case VariantSelectionMethod.NON_FITTING:
            return variant.deviations > 0;

          case VariantSelectionMethod.DISPLAYED:
            return variant.isDisplayed;
        }
      })
      .filter(
        (variant) => !variant.userDefined || config.includeUserCreatedVariants
      )
      .filter(
        (variant) =>
          variant.infixType == InfixType.NOT_AN_INFIX ||
          config.includeTraceFragments
      )
      .map((variant) => variant.bid);

    this.backendService
      .exportEventLog(
        bids,
        config.sequentializeVariants,
        config.exportAsIntervalLog,
        config.includeOriginalLogInfo
      )
      .pipe(take(1))
      .subscribe((blob) => {
        this.electronService.showSaveDialog(
          'log',
          'xes',
          blob,
          'Save event log',
          'Export event log'
        );
      });
  }
}
