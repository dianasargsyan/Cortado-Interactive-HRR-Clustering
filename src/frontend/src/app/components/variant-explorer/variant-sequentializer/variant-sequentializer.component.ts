import { ZoomFieldComponent } from 'src/app/components/zoom-field/zoom-field.component';
import { VariantService } from 'src/app/services/variantService/variant.service';
import { BackendService } from 'src/app/services/backendService/backend.service';
import { VariantExplorerComponent } from 'src/app/components/variant-explorer/variant-explorer.component';
import { GoldenLayoutComponentService } from 'src/app/services/goldenLayoutService/golden-layout-component.service';
import { ColorMapService } from 'src/app/services/colorMapService/color-map.service';
import { ComponentContainer, LogicalZIndex } from 'golden-layout';
import { SharedDataService } from 'src/app/services/sharedDataService/shared-data.service';
import {
  Component,
  ElementRef,
  Inject,
  OnInit,
  Renderer2,
  ViewChild,
  HostListener,
  OnDestroy,
} from '@angular/core';

import { cloneDeep } from 'lodash';
import { select, Selection } from 'd3';
import * as objectHash from 'object-hash';
import * as d3 from 'd3';
import { LogService } from 'src/app/services/logService/log.service';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { VariantDrawerDirective } from 'src/app/directives/variant-drawer/variant-drawer.directive';
import { InfixType, setParent } from 'src/app/objects/Variants/infix_selection';
import { Variant } from 'src/app/objects/Variants/variant';
import {
  VariantElement,
  LeafNode,
  SequenceGroup,
  ParallelGroup,
} from 'src/app/objects/Variants/variant_element';
import { collapsingText, fadeInText } from 'src/app/animations/text-animations';
import { findPathToSelectedNode } from 'src/app/objects/Variants/utility_functions';
import { Observable, of, Subject } from 'rxjs';
import { first, takeUntil, tap } from 'rxjs/operators';
import {
  activityInsertionStrategy,
  VariantModelerComponent,
} from '../../variant-modeler/variant-modeler.component';
import { PatternEditorComponent } from './pattern-editor/pattern-editor.component';
declare var $;

@Component({
  selector: 'app-variant-sequentializer',
  templateUrl: './variant-sequentializer.component.html',
  styleUrls: ['./variant-sequentializer.component.css'],
})
export class VariantSequentializerComponent implements OnInit, OnDestroy {
  activityNames: Array<String> = [];

  public colorMap: Map<string, string>;

  @ViewChild('SourceEditor', { static: false })
  sourceEditor: PatternEditorComponent;
  @ViewChild('TargetEditor', { static: false })
  targetEditor: PatternEditorComponent;

  consistencyWarning = false;

  ifSource: boolean = true;
  redrawSignal: boolean = false;
  sourcePattern: VariantElement = null;
  targetPattern: VariantElement = null;

  collapse = false;

  zoom: any;

  redundancyWarning = false;
  private _destroy$ = new Subject();

  constructor(
    private variantService: VariantService,
    private backendService: BackendService,
    private logService: LogService,

    private colorMapService: ColorMapService
  ) {
    const a = 1;
  }

  ngOnInit(): void {
    this.variantService.showVariantSequentializerDialog
      .pipe(takeUntil(this._destroy$))
      .subscribe((_) => {
        this.showModal();
      });
  }

  ngOnDestroy(): void {
    this._destroy$.next();
  }

  showModal(): void {
    $('#variantSequentializerModalDialog').modal('show');
    this.redrawSignal = true;
    //this.logService.addActivityInEventLog('...');
    //this.colorMapService.createColorMap(Object.keys(this.logService.activitiesInEventLog));
    setTimeout(() => {
      this.sourceEditor.checkButtonCollapse();
      this.targetEditor.checkButtonCollapse();
    }, 10); //make sure the function to be after the rendering
  }

  hideModal(): void {
    $('#variantSequentializerModalDialog').modal('hide');
  }

  activityExist(leaf: LeafNode, variant: VariantElement) {
    const children = variant.getElements();
    if (variant instanceof LeafNode) {
      return leaf.asLeafNode().activity[0] === variant.asLeafNode().activity[0];
    } else {
      for (const child of children) {
        if (this.activityExist(leaf, child)) {
          return true;
        }
      }
      return false;
    }
  }

  checkPattern(source: VariantElement, target: VariantElement) {
    const children = source.getElements();
    if (source instanceof LeafNode) {
      console.log('check ' + source.asLeafNode().activity[0]);
      console.log('result ' + !this.activityExist(source, target));
      return this.activityExist(source, target);
    } else {
      for (const child of children) {
        if (!this.checkPattern(child, target)) {
          return false;
        }
      }
      return true;
    }
  }

  VariantToPattern(parent: VariantElement): String {
    const children = parent.getElements();
    if (parent instanceof LeafNode) {
      return "'" + parent.asLeafNode().activity[0] + "'";
    } else {
      var pattern = '';
      if (parent instanceof SequenceGroup) {
        if (parent.getElements().length > 1) {
          pattern = '->(' + pattern;
          for (const child of children) {
            pattern = pattern + ' ' + this.VariantToPattern(child);
          }
          pattern = pattern + ')';
        } else {
          for (const child of children) {
            pattern = pattern + ' ' + this.VariantToPattern(child);
          }
        }
      } else if (parent instanceof ParallelGroup) {
        pattern = '+(' + pattern;
        for (const child of children) {
          pattern = pattern + ' ' + this.VariantToPattern(child);
        }
        pattern = pattern + ')';
      }
    }
    return pattern;
  }

  handleSourceChange(event) {
    this.sourcePattern = event.variant;
  }
  handleTargetChange(event) {
    this.targetPattern = event.variant;
  }

  apply(): void {
    if (
      this.checkPattern(
        this.sourceEditor.currentVariant,
        this.targetEditor.currentVariant
      )
    ) {
      this.backendService.applyVariantSequentializer(
        this.sourceEditor.currentVariant.serialize(),
        this.targetEditor.currentVariant.serialize()
      );
      this.hideModal();
    } else {
      this.consistencyWarning = true;
      setTimeout(() => (this.consistencyWarning = false), 2500);
    }
  }
}
