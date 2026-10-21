import {
  AfterViewInit,
  Component,
  ElementRef,
  Inject,
  OnDestroy,
  OnInit,
  Renderer2,
  ViewChild,
} from '@angular/core';
import { ComponentContainer, LogicalZIndex } from 'golden-layout';
import { Subject } from 'rxjs';
import { LayoutChangeDirective } from 'src/app/directives/layout-change/layout-change.directive';
import { LocalProcessModelWithPatterns } from 'src/app/objects/LocalProcessModelWithPatterns';
import { InfixType } from 'src/app/objects/Variants/infix_selection';
import { ColorMapService } from 'src/app/services/colorMapService/color-map.service';
import { LazyLoadingServiceService } from 'src/app/services/lazyLoadingService/lazy-loading.service';
import { LpmService } from 'src/app/services/lpmService/lpm.service';

@Component({
  selector: 'app-lpm-explorer',
  templateUrl: './lpm-explorer.component.html',
  styleUrls: ['./lpm-explorer.component.scss'],
})
export class LpmExplorerComponent
  extends LayoutChangeDirective
  implements OnInit, OnDestroy, AfterViewInit
{
  lpms: LocalProcessModelWithPatterns[] = [];

  @ViewChild('lpmExplorer')
  lpmExplorerDiv: ElementRef<HTMLDivElement>;

  InfixType = InfixType;

  private _destroy$ = new Subject();

  constructor(
    @Inject(LayoutChangeDirective.GoldenLayoutContainerInjectionToken)
    private container: ComponentContainer,
    elRef: ElementRef,
    renderer: Renderer2,
    public lpmService: LpmService,
    public colorMapService: ColorMapService,
    public lazyLoadingService: LazyLoadingServiceService
  ) {
    super(elRef.nativeElement, renderer);
  }
  ngAfterViewInit(): void {
    this.lazyLoadingService.initializeLpmExplorer(this.lpmExplorerDiv);
  }

  ngOnInit(): void {
    this.lpmService.localProcessModels$.subscribe((models) => {
      this.lpms = models;
    });
  }

  handleResponsiveChange(
    left: number,
    top: number,
    width: number,
    height: number
  ): void {}
  handleVisibilityChange(visibility: boolean): void {}
  handleZIndexChange(
    logicalZIndex: LogicalZIndex,
    defaultZIndex: string
  ): void {}

  exportLocalProcessModels() {
    console.log('implement lpm export here');
  }

  ngOnDestroy(): void {
    this._destroy$.next();
    this.lazyLoadingService.destoryLpmExplorerObserver();
  }
}

export namespace LpmExplorerComponent {
  export const componentName = 'LpmExplorerComponent';
}
