import { Inject, Injectable } from '@angular/core';
import * as d3 from 'd3';
import { saveAs } from 'file-saver';
import { ElectronService } from '../electronService/electron.service';
import { HttpClient } from '@angular/common/http';
import { optimize } from 'svgo/dist/svgo.browser.js';
import { ConformanceCheckingService } from '../conformanceChecking/conformance-checking.service';
import { addPatternDefinitions } from 'src/app/utils/render-utils';

/***
A service that recieves SVG elements from member components and provides conversion and saving functionality.
***/

@Injectable({
  providedIn: 'root',
})
export class ImageExportService {
  constructor(
    private electronService: ElectronService,
    private http: HttpClient,
    private conformanceCheckingService: ConformanceCheckingService
  ) {}

  async export(
    filename: string,
    width?: number,
    height?: number,
    ...svgs: SVGGraphicsElement[]
  ) {
    let svg = await this.constructSVG(svgs);

    const base64EncodedFont = await this.getBase64EncodedFont(
      '/assets/fonts/Roboto/Roboto-Regular.ttf'
    );
    const fontFace = `@font-face {
        font-family: 'Roboto';
        src: url(data:font/truetype;base64,${base64EncodedFont}) format('truetype');
      }`;

    svg.mainSVG.append('style').attr('type', 'text/css').text(fontFace);

    if (height) svg.svg_width = width;
    if (width) svg.svg_height = height;

    svg.store(filename, this.electronService);
  }

  constructSVG(svgs: SVGGraphicsElement[]): SVG {
    let svg = new SVG();
    svg.appendDefs(this.conformanceCheckingService);
    svg.appendRight(svgs);
    return svg;
  }

  // TODO Implement in new Issue
  convert_svg_to_png() {}

  // TODO Implement in new Issue
  convert_svg_to_pdf() {}

  private convertBlobToBase64(blob: Blob): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64String = reader.result.toString().split(',')[1];
        resolve(base64String);
      };
      reader.onerror = () => {
        reject('Error converting blob to Base64');
      };
      reader.readAsDataURL(blob);
    });
  }

  async getBase64EncodedFont(fontFilePath: string): Promise<string> {
    const fontFile = await this.http
      .get(fontFilePath, { responseType: 'blob' })
      .toPromise();
    return this.convertBlobToBase64(fontFile);
  }
}

class SVG {
  readonly mainSVG;

  private width = 0;
  private height = 0;

  constructor() {
    this.mainSVG = d3
      .create('svg')
      .attr('xmlns', 'http://www.w3.org/2000/svg')
      .attr('font-family', 'Roboto, sans-serif');
  }

  public append(x: number, y: number, svgs: SVGGraphicsElement[]): SVG {
    let lastSVG;
    for (let svg of svgs) {
      const svgX = svg.getAttribute('x');
      const svgY = svg.getAttribute('y');

      lastSVG = this.mainSVG
        .append(svg.nodeName)
        .attr('x', svgX === null ? x : svgX)
        .attr('y', svgY === null ? y : svgY)
        .html(svg.innerHTML);

      for (let attr of svg.getAttributeNames()) {
        lastSVG.attr(attr, svg.getAttribute(attr));
      }

      y += Number.parseFloat(svg.getAttribute('height'));
      this.height = Math.max(this.height, y);
      this.width = Math.max(
        this.width,
        x + Number.parseFloat(svg.getAttribute('width'))
      );
    }
    return this;
  }

  public appendDefs(conformanceCheckingService: ConformanceCheckingService) {
    addPatternDefinitions(this.mainSVG, conformanceCheckingService);
  }

  public appendRight(svgs: SVGGraphicsElement[]) {
    return this.append(this.width, 0, svgs);
  }

  public appendBottom(svgs: SVGGraphicsElement[]) {
    return this.append(0, this.height, svgs);
  }

  public store(filename: string, electronService: ElectronService) {
    this.mainSVG.attr('height', this.height);
    this.mainSVG.attr('width', this.width);

    const blob = optimize(this.mainSVG.node().outerHTML).data;

    const file = new Blob([blob], {
      type: 'image/svg+xml',
    });
    //filename = filename.endsWith('.svg') ? filename : filename + '.svg';
    electronService.showSaveDialog(
      filename,
      'svg',
      file,
      'Save svg',
      'Save svg'
    );
    //saveAs(file, filename);
  }

  set svg_width(width: number) {
    this.width = width;
  }
  set svg_height(height: number) {
    this.height = height;
  }
}
