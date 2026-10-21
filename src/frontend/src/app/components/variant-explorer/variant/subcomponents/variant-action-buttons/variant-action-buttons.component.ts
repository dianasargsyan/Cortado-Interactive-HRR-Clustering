import {
  Component,
  EventEmitter,
  Input,
  Output,
  QueryList,
} from '@angular/core';
import { VariantService } from 'src/app/services/variantService/variant.service';
import { IVariant } from '../../../../../objects/Variants/variant_interface';
import { Subject } from 'rxjs';
import { VariantVisualisationComponent } from '../variant-visualisation/variant-visualisation.component';

@Component({
  selector: 'app-variant-action-buttons',
  templateUrl: './variant-action-buttons.component.html',
  styleUrls: ['./variant-action-buttons.component.css'],
})
export class VariantActionButtonsComponent {
  @Input()
  private variant: IVariant;
  @Input()
  protected variantVisualisations: QueryList<VariantVisualisationComponent>;
  @Output()
  showArcDiagram = new EventEmitter<number[]>();

  constructor(private variantService: VariantService) {}

  private _destroy$ = new Subject();

  deleteVariant() {
    this.variantService.deleteVariant(this.variant.bid);
  }

  showArcDiagramBtnClicked() {
    this.showArcDiagram.emit([this.variant.bid]);
  }
}
