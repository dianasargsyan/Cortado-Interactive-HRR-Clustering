import { VariantDrawerDirective } from '../directives/variant-drawer/variant-drawer.directive';
import * as d3 from 'd3';
import { Selection } from 'd3';
import { PT_Constant } from '../constants/process_tree_drawer_constants';
import {
  GroupsWithChildElements,
  LeafNode,
  VariantElement,
  WaitingTimeNode,
} from '../objects/Variants/variant_element';
import { Variant } from '../objects/Variants/variant';
import { ElementRef } from '@angular/core';
import { ConformanceCheckingService } from '../services/conformanceChecking/conformance-checking.service';

export function textColorForBackgroundColor(
  backgroundColorInHex: string,
  unselectedElementInTraceInfixSelectionMode: boolean = false
): string {
  if (
    backgroundColorInHex === undefined ||
    unselectedElementInTraceInfixSelectionMode
  ) {
    return 'white';
  }
  if (!backgroundColorInHex.startsWith('#')) return 'black';
  return isDarkColor(backgroundColorInHex) ? 'white' : 'black';

  function isDarkColor(color: string): boolean {
    let res;
    if (color === undefined) {
      return true;
    }
    if (color.includes('rgb')) {
      res = rgbToArray(color);
    } else {
      res = hexToRgb(color);
    }
    if (0.2126 * res['r'] + 0.7152 * res['g'] + 0.0722 * res['b'] >= 135) {
      return false;
    } else {
      return true;
    }
  }

  function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result
      ? {
          r: parseInt(result[1], 16),
          g: parseInt(result[2], 16),
          b: parseInt(result[3], 16),
        }
      : null;
  }

  function rgbToArray(rgb) {
    let arr = rgb.slice(4, -1).split(',');
    return {
      r: arr[0],
      g: arr[1],
      b: arr[2],
    };
  }
}

export function applyInverseStrokeToPoly(poly: Selection<any, any, any, any>) {
  const datum = poly.data()[0];
  if (datum) {
    if (datum instanceof LeafNode) {
      const rgb_code = poly.attr('style').match(/[\d.]+/g);
      const inversed = rgb_code.map((d) => 255 - parseInt(d));

      poly.attr('style', poly.attr('style').split(';')[0]);
      poly.attr('stroke-width', 2);
      poly.attr(
        'stroke',
        `rgb(${inversed[0]}, ${inversed[1]}, ${inversed[2]})`
      );
    } else {
      poly
        .attr('stroke', '#dc3545')
        .attr('style', poly.attr('style').split(';')[0])
        .attr('stroke-width', 2);
    }
  }
}

export function computeLeafNodeWidth(
  nodeActivityLabels: string[],
  nodeWidthCache: Map<string, number>
): Map<string, number> {
  const dummy_container = d3
    .select('body')
    .append('svg')
    .style('top', '0px')
    .style('left', '0px')
    .style('position', 'absolute');

  const dummy_select = dummy_container.append('text').attr('font-size', '12px');

  let labels = nodeActivityLabels;
  labels.push('...');

  for (let nodeActivityLabel of labels) {
    // Compute the width by rendering a dummy node
    dummy_select.text(function (d: any) {
      if (nodeActivityLabel.length <= 20) {
        return nodeActivityLabel;
      } else {
        return nodeActivityLabel.substring(0, 20) + '...';
      }
    });

    // Retrieve the computed width
    let rendered_width = dummy_select.node().getComputedTextLength();

    // Compute the true node width as specified above
    rendered_width = Math.max(
      rendered_width + 10,
      PT_Constant.BASE_HEIGHT_WIDTH
    );

    // Add to Cache
    nodeWidthCache[nodeActivityLabel] = rendered_width;
  }

  // Delete the Dummy
  dummy_select.remove();
  dummy_container.remove();

  return nodeWidthCache;
}

export function computeActivityColor(
  self: VariantDrawerDirective,
  element: VariantElement,
  variant: Variant
) {
  let color;
  color = this.colorMap.get(element.asLeafNode().activity[0]);

  if (!color) {
    color = '#d3d3d3'; // lightgrey
  }

  return color;
}

export function setChevronIdsForArcDiagrams(
  variant: VariantElement,
  drawer: VariantDrawerDirective
) {
  setDfsIds(variant, drawer.svgSelection, true);
  setBfsIds(drawer.svgHtmlElement);
}

const setDfsIds = (
  element: VariantElement,
  svgElement: Selection<any, any, any, any>,
  outerElement: boolean = false
) => {
  if (!outerElement) {
    svgElement.classed(`dfs-group-${element.id}`, true);
  } else {
    svgElement = svgElement
      .select('.variant-element-group')
      .classed('dfs-group-0', true);
  }

  if (element instanceof LeafNode || element instanceof WaitingTimeNode) {
    return;
  } else {
    (element as GroupsWithChildElements).elements.forEach((child, index) => {
      const svg = d3.select(
        svgElement
          .selectAll(`.dfs-group-${element.id} > .variant-element-group`)
          .nodes()[index]
      );
      setDfsIds(child, svg);
    });
  }
};

const setBfsIds = (svgElement: ElementRef<any>) => {
  let outerElement = svgElement.nativeElement.querySelector('.dfs-group-0');

  if (outerElement) {
    d3.select(
      outerElement.querySelectorAll(':scope > .variant-element-group')
    ).each(function (d, i) {
      let offset = 1;
      this.forEach((child) => {
        d3.select(child).classed(`bfs-group-${offset++}`, true);
      });
    });
  }
};

export function addPatternDefinitions(
  parentElement: Selection<any, any, any, any>,
  conformanceCheckingService: ConformanceCheckingService
) {
  const svg = parentElement.append('svg');

  const defs = svg.append('defs');
  const whiteStripePattern = defs
    .append('pattern')
    .attr('id', 'whiteStriped')
    .attr('width', '6')
    .attr('height', '8')
    .attr('patternUnits', 'userSpaceOnUse')
    .attr('patternTransform', 'rotate(45)');
  whiteStripePattern
    .append('rect')
    .attr('width', '4')
    .attr('height', '8')
    .attr('transform', 'translate(2,0)')
    .attr('fill', '#FFFFFF');
  whiteStripePattern
    .append('rect')
    .attr('width', '2')
    .attr('height', '8')
    .attr('transform', 'translate(0,0)')
    .attr('fill', '#EEEEEE');

  const modelConformanceStripePattern = defs
    .append('pattern')
    .attr('id', 'modelConformanceStriped')
    .attr('width', '6')
    .attr('height', '8')
    .attr('patternUnits', 'userSpaceOnUse')
    .attr('patternTransform', 'rotate(45)');
  modelConformanceStripePattern
    .append('rect')
    .attr('width', '4')
    .attr('height', '8')
    .attr('transform', 'translate(2,0)')
    .attr('fill', conformanceCheckingService.modelConformanceStripeColors[0]);
  modelConformanceStripePattern
    .append('rect')
    .attr('width', '2')
    .attr('height', '8')
    .attr('transform', 'translate(0,0)')
    .attr('fill', conformanceCheckingService.modelConformanceStripeColors[1]);

  const variantConformanceStripePattern = defs
    .append('pattern')
    .attr('id', 'variantConformanceStriped')
    .attr('width', '6')
    .attr('height', '8')
    .attr('patternUnits', 'userSpaceOnUse')
    .attr('patternTransform', 'rotate(45)');
  variantConformanceStripePattern
    .append('rect')
    .attr('width', '4')
    .attr('height', '8')
    .attr('transform', 'translate(2,0)')
    .attr('fill', conformanceCheckingService.variantConformanceStripeColors[0]);
  variantConformanceStripePattern
    .append('rect')
    .attr('width', '2')
    .attr('height', '8')
    .attr('transform', 'translate(0,0)')
    .attr('fill', conformanceCheckingService.variantConformanceStripeColors[1]);
}
