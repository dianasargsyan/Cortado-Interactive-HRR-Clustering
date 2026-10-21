import { Component } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { VariantSelectionMethod } from 'src/app/objects/VariantSelectionMethod';
import { DocumentationService } from '../../documentation/documentation.service';
import { LogExportConfig } from 'src/app/objects/LogExportConfig/LogExportConfig';
import { VariantService } from 'src/app/services/variantService/variant.service';
import { InfixType } from 'src/app/objects/Variants/infix_selection';

@Component({
  selector: 'app-log-exporter-dialog',
  templateUrl: './log-exporter-dialog.component.html',
  styleUrls: ['./log-exporter-dialog.component.css'],
})
export class LogExporterDialogComponent {
  activeIndex = 0;
  lastPageIndex = 6;

  skipUserCreatedVariants = false;
  skipTraceFragments = false;

  includeUserCreatedVariantsForced = false;

  VariantSelectionMethod = VariantSelectionMethod;

  logExportConfig: LogExportConfig;

  constructor(
    public modal: NgbActiveModal,
    private documentationService: DocumentationService,
    private variantService: VariantService
  ) {
    this.logExportConfig = {
      variantSelectionMethod: VariantSelectionMethod.ALL,
      includeTraceFragments: false,
      includeUserCreatedVariants: false,
      sequentializeVariants: false,
      exportAsIntervalLog: true,
      includeOriginalLogInfo: true,
    };

    this.skipUserCreatedVariants = !variantService.variants.some(
      (v) => v.userDefined
    );
    this.skipTraceFragments = !variantService.variants.some(
      (v) => v.infixType != InfixType.NOT_AN_INFIX
    );
  }

  openDocumentation() {
    this.documentationService.showDocumentationDialog('Log Export');
    this.modal.dismiss('Documentation opened');
  }

  onExport() {
    this.modal.close(this.logExportConfig);
  }

  onIncludeFragementsToggle() {
    if (
      this.logExportConfig.includeTraceFragments &&
      !this.logExportConfig.includeUserCreatedVariants
    ) {
      this.logExportConfig.includeUserCreatedVariants = true;
      this.includeUserCreatedVariantsForced = true;
    }
    if (
      !this.logExportConfig.includeTraceFragments &&
      this.includeUserCreatedVariantsForced
    ) {
      this.logExportConfig.includeUserCreatedVariants = false;
      this.includeUserCreatedVariantsForced = false;
    }
  }

  onNext(nav) {
    let newIndex = this.activeIndex + 1;
    if (newIndex == 1 && this.skipUserCreatedVariants) newIndex += 1;
    if (newIndex == 2 && this.skipTraceFragments) newIndex += 1;
    nav.select(newIndex);
  }

  onBack(nav) {
    let newIndex = this.activeIndex - 1;
    if (newIndex == 2 && this.skipTraceFragments) newIndex -= 1;
    if (newIndex == 1 && this.skipUserCreatedVariants) newIndex -= 1;
    nav.select(newIndex);
  }
}
