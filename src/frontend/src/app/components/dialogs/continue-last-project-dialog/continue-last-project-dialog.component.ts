import { Component, Input } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-continue-last-project-dialog',
  templateUrl: './continue-last-project-dialog.component.html',
  styleUrls: ['./continue-last-project-dialog.component.css'],
})
export class ContinueLastProjectDialogComponent {
  @Input() projectName: string;
  constructor(public modal: NgbActiveModal) {}
}
