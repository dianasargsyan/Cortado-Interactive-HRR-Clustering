import { Directive, ElementRef, Input, Renderer2 } from '@angular/core';
import { Arc, Level, Pair } from './data';
import * as d3 from 'd3';
import { IVariant } from '../../objects/Variants/variant_interface';
import { VariantDrawerDirective } from '../variant-drawer/variant-drawer.directive';
import { FilterConfig } from './filter-config';
import { setChevronIdsForArcDiagrams } from '../../utils/render-utils';

@Directive({
  selector: '[appArcDiagram]',
  exportAs: 'arcDiagram',
})
export class ArcDiagramDirective {
  constructor(elRef: ElementRef, renderer: Renderer2) {
    this.svgHtmlElement = elRef;
    renderer.setStyle(this.svgHtmlElement.nativeElement, 'display', 'none');
  }

  svgHtmlElement: ElementRef;

  arcs: Arc[];

  @Input()
  variant: IVariant;

  @Input()
  filterConfig: FilterConfig;

  private config = {
    width: 800,
    transparency: 0.4,
    hoverTransparency: 1,
    hoverColor: 'red',
    LoD: 1,
    arcColor: 'lightgrey',
    strokeWidth: '1',
    baseHeight: 50,
    step: 30,
    barHeight: 10,
    barRoundness: 4,
  };

  // private containsDisallowedActivities(activities: Set<string>, filterParams: FilterParams) {
  //   let activitiesToInclude = filterParams.activitiesSelection.selectedItems;
  //   for( let act of activities) {
  //     if(!activitiesToInclude.has(act)) return true;
  //   }
  //   return false;
  // }

  /** Method to parse the input of the textfield or the file
   * @param pairs The array of pairs to be parsed and visualized as arcs
   * @return Struct of characters and essential matching pair arcs to draw
   */
  public parseInput = (pairs: Pair[]) => {
    let arcs: Arc[] = [];
    let maxDistance = -1;
    for (let i = 0; i < pairs.length; i++) {
      let pair = pairs[i];
      const arc = new Arc(
        pair.positions.bfs[0],
        pair.length,
        pair.positions.bfs[1],
        pair.matches,
        JSON.stringify(pair.pattern),
        pair.activities,
        pair.size
      );
      arcs.push(arc);
      if (arc.distanceBetweenPairs > maxDistance) {
        maxDistance = arc.distanceBetweenPairs;
      }
    }
    return { arcs, maxDistance };
  };

  /** Draw the arc diagram
   */
  public draw = (variantDrawer: VariantDrawerDirective, arcsToDraw?: Arc[]) => {
    setChevronIdsForArcDiagrams(this.variant.variant, variantDrawer);

    if (!arcsToDraw) {
      arcsToDraw = this.arcs;
    }
    // clear the chart and redraw everything
    // $('#chart').empty();
    let arcs: Arc[] = [];

    //filter the data for LoD
    for (let j = 0; j < arcsToDraw.length; j++) {
      if (arcsToDraw[j].numberEle >= this.config.LoD) arcs.push(arcsToDraw[j]);
    }

    this.config.width = this.variant.variant.width;

    const levels: Level[] = [];
    let idx = 0;
    for (let i = arcs.length - 1; i >= 0; i--) {
      const arc = arcs[i];
      if (
        !levels.some(
          (lvl) => lvl.distanceBetweenPairs === arc.distanceBetweenPairs
        )
      ) {
        levels.push(new Level(arc.distanceBetweenPairs, idx++));
      }
    }

    const height = this.config.baseHeight + this.config.step * (idx - 1);

    const variantEl = d3.select(variantDrawer.svgHtmlElement.nativeElement);

    const chart = d3
      .select(this.svgHtmlElement.nativeElement)
      .attr('width', this.config.width)
      .attr('height', height)
      .style('display', 'block');

    chart.select('#arcGroup').selectAll('*').remove();

    //plot the arcs like defined in the arcs array of the parsed data
    const arcSvg = chart.select('#arcGroup');

    // source base bar
    const arcGroups = arcSvg.selectAll('path').data(arcs).enter().append('g');

    const config = this.config;

    function appendBarBasedOn(dest: string) {
      arcGroups
        .append('rect')
        .attr('x', function (d: Arc) {
          const startLeafCoords = variantEl
            .select(`g.bfs-group-${d[`${dest}Pos`]}`)
            .attr('transform')
            .split(/[\s,()]+/);
          return parseFloat(startLeafCoords[1]);
        })
        .attr('y', function (d: Arc) {
          const level = levels.find(
            (lvl) =>
              lvl.distanceBetweenPairs ===
              d.targetPos - d.sourcePos - d.numberEle
          );
          return height - level.fromBottom * config.step - config.barHeight;
        })
        .attr('width', function (d: Arc) {
          const width = variantEl
            .select(`g.bfs-group-${d[`${dest}Pos`] + d.numberEle - 1}>polygon`)
            .attr('points')
            .split(' ')[1]
            .split(',')[0];
          const endLeafCoords = variantEl
            .select(`g.bfs-group-${d[`${dest}Pos`] + d.numberEle - 1}`)
            .attr('transform')
            .split(/[\s,()]+/);
          const startLeafCoords = variantEl
            .select(`g.bfs-group-${d[`${dest}Pos`]}`)
            .attr('transform')
            .split(/[\s,()]+/);
          return (
            parseFloat(endLeafCoords[1]) +
            parseFloat(width) -
            parseFloat(startLeafCoords[1])
          );
        })
        .attr('height', config.barHeight)
        .attr('rx', config.barRoundness)
        .attr('ry', config.barRoundness)
        .attr('class', `${dest}-rect`)
        .style('fill', config.arcColor)
        .style('fill-opacity', config.transparency)
        .style('cursor', 'pointer');
    }

    appendBarBasedOn('source');
    appendBarBasedOn('target');

    let areOtherArcsHidden = false;

    // arc between the source and target bar
    arcGroups
      .each(function () {
        const sbbox = (this.firstElementChild as SVGGraphicsElement).getBBox();
        let scx = sbbox.width / 2 + sbbox.x;
        const tbbox = (this.lastElementChild as SVGGraphicsElement).getBBox();
        let tcx = tbbox.width / 2 + tbbox.x;

        d3.select(this)
          .append('path')
          .attr('d', function (d: Arc) {
            const path = d3.path();

            const baseHeight = levels.find(
              (lvl) =>
                lvl.distanceBetweenPairs ===
                d.targetPos - d.sourcePos - d.numberEle
            )?.fromBottom;
            const levelHeight =
              height - baseHeight * config.step - config.barHeight;

            path.moveTo(scx, levelHeight);

            path.quadraticCurveTo(
              (scx + tcx) / 2,
              levelHeight - config.step,
              tcx,
              levelHeight
            );

            return path.toString();
          })
          .style('stroke', config.arcColor)
          .style('fill', 'none')
          .style('stroke-linecap', 'round')
          .style('stroke-opacity', config.transparency)
          .style('cursor', 'pointer');
      })
      .on('mouseover', function (_, i) {
        // highlight all corresponding bars and arcs
        arcGroups.selectAll('rect,path').each(highlightArcComponents);

        function highlightArcComponents(x: Arc) {
          if (i.text == x.text) {
            d3.select(this)
              .style('fill', function () {
                return this.tagName == 'rect' ? config.hoverColor : 'none';
              })
              .style('stroke', function () {
                return this.tagName == 'path' ? config.hoverColor : 'none';
              });
          }
          let highlightTransparency =
            i == x ? config.hoverTransparency : config.transparency;
          d3.select(this)
            .style('fill-opacity', highlightTransparency)
            .style('stroke-opacity', highlightTransparency);
        }

        // blur out all the chevrons
        variantEl
          .selectAll('g.variant-element-group')
          .style('fill-opacity', config.transparency);

        arcs.forEach(highlightMatchingChevrons);

        function highlightMatchingChevrons(x: Arc) {
          if (i.text == x.text) {
            x.matches.forEach((dfsId: number) => {
              if (dfsId == 0) {
                return;
              }
              let el = variantEl.select(`g.dfs-group-${dfsId}`);
              if (i == x) {
                el.style('fill-opacity', config.hoverTransparency);
              }
              el.select('polygon')
                .style('stroke', config.hoverColor)
                .style('stroke-width', config.strokeWidth);
            });
          }
        }
      })
      .on('mouseout', function () {
        arcGroups
          .selectAll('rect')
          .style('fill-opacity', config.transparency)
          .style('fill', config.arcColor);
        arcGroups
          .selectAll('path')
          .style('stroke-opacity', config.transparency)
          .style('stroke', config.arcColor);
        variantEl
          .selectAll('g')
          .style('fill-opacity', config.hoverTransparency)
          .selectAll('polygon')
          .style('stroke', 'none');
      })
      .on('click', function (d, i) {
        // move all patterns to the same level as that of the clicked one
        arcGroups.selectAll('rect,path').each(function (x: Arc) {
          moveArcComponents(this, x, areOtherArcsHidden);
        });
        areOtherArcsHidden = !areOtherArcsHidden;

        function moveArcComponents(el, x: Arc, reset: boolean) {
          if (i.text == x.text && i != x && !reset) {
            d3.select(el.parentNode)
              .transition()
              .duration(500)
              .attr('transform', function () {
                return `translate(0, ${
                  d.target.getAttribute('y') - this.firstChild.getAttribute('y')
                })`;
              });
          }
          if (reset) {
            d3.select(el.parentNode)
              .transition()
              .duration(500)
              .attr('transform', null);
          }
          if (i.text != x.text) {
            d3.select(el).style('visibility', reset ? 'visible' : 'hidden');
          }
        }
      });
  };
}
