import {
  AfterViewInit,
  ApplicationInitStatus,
  APP_INITIALIZER,
  Component,
  HostListener,
  Inject,
  OnDestroy,
  OnInit,
  ViewChild,
  ElementRef,
} from '@angular/core';
import { GoldenLayoutHostComponent } from './components/golden-layout-host/golden-layout-host.component';
import { DropZoneDirective } from './directives/drop-zone/drop-zone.directive';
import { GoldenLayoutComponentService } from './services/goldenLayoutService/golden-layout-component.service';
import * as d3 from 'd3';
import { EditorService } from './services/editorService/editor.service';
import { DropzoneConfig } from './components/drop-zone/drop-zone.component';
import { ConformanceCheckingService } from './services/conformanceChecking/conformance-checking.service';
import { addPatternDefinitions } from './utils/render-utils';
@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements AfterViewInit, OnDestroy, OnInit {
  title = 'interactive-process-mining-angular-app';

  @ViewChild('goldenLayoutHost')
  private _goldenLayoutHostComponent: GoldenLayoutHostComponent;
  private _windowResizeListener = () => this.handleWindowResizeEvent();

  dropZoneConfig: DropzoneConfig;
  goldenLayoutHostOutOfFocus: boolean = false;
  elementRef: ElementRef;

  constructor(
    elementRef: ElementRef<HTMLElement>,
    private goldenLayoutComponentService: GoldenLayoutComponentService,
    private monacoEditorService: EditorService,
    private conformanceCheckingService: ConformanceCheckingService,
    @Inject(APP_INITIALIZER) public appInit: ApplicationInitStatus
  ) {
    this.elementRef = elementRef;
  }

  ngOnInit(): void {
    this.monacoEditorService.load();

    this.dropZoneConfig = new DropzoneConfig(
      '.xes .ptml',
      'false',
      'false',
      '<large> Import <strong>Event Log</strong> (.xes) or <strong>Process Tree</strong> (.ptml) files</large>'
    );
  }

  toggleBlur(event) {
    this.goldenLayoutHostOutOfFocus = event;
  }

  _sideBarWidth: number = 30;

  ngAfterViewInit() {
    globalThis.addEventListener('resize', this._windowResizeListener);
    this._goldenLayoutHostComponent.initializeLayout();
    this.goldenLayoutComponentService.goldenLayoutHostComponent =
      this._goldenLayoutHostComponent;
    setTimeout(() => this.resizeGoldenLayout(), 0);

    this.goldenLayoutComponentService.goldenLayoutHostComponent =
      this._goldenLayoutHostComponent;

    const parent = d3.select(this.elementRef.nativeElement);
    addPatternDefinitions(parent, this.conformanceCheckingService);
  }

  // Put the dropzone in front if a File Drag enters
  @HostListener('window:dragenter', ['$event'])
  window_dragenter(event) {
    if ((event.dataTransfer.types as Array<string>).includes('Files')) {
      DropZoneDirective.windowDrag = true;
    }
  }

  // If the File Drag leaves the window, put the Dropzone back again
  @HostListener('window:dragleave', ['$event'])
  window_dragleave(event: DragEvent) {
    if (event.screenX === 0 && event.screenY === 0) {
      DropZoneDirective.windowDrag = false;
    }
  }

  ngOnDestroy() {
    globalThis.removeEventListener('resize', this._windowResizeListener);
  }

  private handleWindowResizeEvent() {
    this.resizeGoldenLayout();
  }

  private resizeGoldenLayout() {
    const bodyWidth = document.body.offsetWidth;
    const bodyHeight = document.body.offsetHeight;
    this._goldenLayoutHostComponent.setSize(bodyWidth, bodyHeight);
  }
}
