import { Component, Input } from '@angular/core';
import { ColorMap, ZERO_VALUE_COLOR } from 'src/app/objects/ColorMap';

@Component({
  selector: 'app-color-map',
  templateUrl: './color-map.component.html',
  styleUrls: ['./color-map.component.scss'],
})
export class ColorMapComponent {
  @Input()
  colorMapValues: ColorMapValue[];
  @Input()
  timeBasedLabel: Boolean = true;
  @Input()
  prefixes: string[] = [];
  @Input()
  suffix: string = '';
  @Input()
  excludeUpperLabel: Boolean = false;
  @Input()
  firstColorStriped: Boolean = false;
  @Input()
  stripeColor: string = '#EEEEEE';
  @Input()
  stripeBackgroundColor: string = 'white';
  @Input()
  firstColorDetached: Boolean = false;
  @Input()
  lastColorDetached: Boolean = false;

  getCssStripes(
    backgroundColor = this.stripeBackgroundColor,
    stripeColor = this.stripeColor,
    stripeSpacing = 3,
    stripeThickness = 2
  ) {
    return getCssStripes(
      backgroundColor,
      stripeColor,
      stripeSpacing,
      stripeThickness
    );
  }

  constructor() {}
}

export interface ColorMapValue {
  lowerBound: number;
  color: string;
}

export function buildColorValues(
  colorScale,
  values?: number[]
): ColorMapValue[] {
  let thresholds = colorScale.domain();
  if (values) {
    let min = Math.min(...values);
    let max = Math.max(...values);

    if (min != max) {
      thresholds = [min, ...thresholds, max];
      if (min !== 0) thresholds.unshift(0); // Add artifical zero
    } else thresholds = [min];
  }
  let colors = colorScale.range();
  colors = [...colors, null];
  return thresholds.map((t, i) => {
    let color = t == 0 ? ZERO_VALUE_COLOR : colors[i - 1];

    return {
      lowerBound: t,
      color: color,
    };
  });
}

export function getCssStripes(
  backgroundColor = 'white',
  stripeColor = '#EEEEEE',
  stripeSpacing = 3,
  stripeThickness = 2
) {
  return `repeating-linear-gradient(
      -45deg,
      ${backgroundColor} 0px,
      ${backgroundColor} ${stripeSpacing}px,
      ${stripeColor} ${stripeSpacing + 1}px,
      ${stripeColor} ${stripeSpacing + stripeThickness + 1}px,
      ${backgroundColor} ${stripeSpacing + stripeThickness + 2}px
      )`;
}
