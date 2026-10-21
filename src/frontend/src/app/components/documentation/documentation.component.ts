import {
  Component,
  Inject,
  Input,
  NgZone,
  OnDestroy,
  OnInit,
  ViewEncapsulation,
} from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { Observable, Subject } from 'rxjs';
import { first, takeUntil } from 'rxjs/operators';

declare let Gumshoe: any;

declare var $: any;

@Component({
  selector: 'app-documentation',
  templateUrl: './documentation.component.html',
  styleUrls: ['./documentation.component.scss'],
  encapsulation: ViewEncapsulation.None,
})
export class DocumentationComponent implements OnInit, OnDestroy {
  @Input()
  showDocumentation: Observable<string>;
  headings: NodeListOf<Element>;
  // tslint:disable-next-line:variable-name
  private _destroy$ = new Subject();
  private scrollSpy: typeof Gumshoe;

  constructor(
    @Inject(DOCUMENT) private document: Document,
    private zone: NgZone
  ) {}

  ngOnInit() {
    this.showDocumentation
      .pipe(takeUntil(this._destroy$))
      .subscribe((heading) => {
        this.showModal(heading);
      });
  }

  showModal(heading): void {
    $('#documentation-modal-dialog').modal('show');
    setTimeout(() => {
      if (heading) {
        this.navToSectionByHeading(heading);
      }
      if (this.scrollSpy) {
        this.scrollSpy.detect();
      }
    }, 180);
  }

  onLoad() {
    setTimeout(() => {
      this.headings = this.document
        .querySelector('main')
        .querySelectorAll('h1, h2');
      this.setScrollSpy();
    });
    const tables = this.document
      .querySelector('main')
      .querySelectorAll('table, th, td');

    // add class for styling the tables
    for (let i = 0; i < tables.length; i++) {
      tables[i].classList.add('markdown-table');
    }
  }

  onScroll(): void {
    if (this.scrollSpy) {
      this.scrollSpy.detect();
    }
  }

  blink(element) {
    let f = document.getElementById(element);
    setTimeout(function () {
      f.style.background = f.style.background == 'lightgray' ? '' : 'lightgray';
    }, 200);
    setTimeout(function () {
      f.style.background = f.style.background == 'lightgray' ? '' : 'lightgray';
    }, 1200);
  }

  navToSection(element) {
    element.scrollIntoView();
    return false;
  }

  navToSectionByHeading(heading: string) {
    let elementId;
    // tslint:disable-next-line:prefer-for-of
    for (let i = 0; i < this.headings.length; i++) {
      if (this.headings[i].innerHTML === heading) {
        elementId = this.headings[i].id;
        break;
      }
    }
    if (elementId) {
      document.querySelector('#' + elementId).scrollIntoView();
      // this.blink(elementId);
    }
  }

  setScrollSpy(): void {
    if (this.scrollSpy) {
      this.scrollSpy.setup();
      return;
    }
    this.zone.onStable.pipe(first()).subscribe(() => {
      this.scrollSpy = new Gumshoe('#table-of-contents a', {
        offset: 90,
      });
      this.scrollSpy.setup();
    });
  }

  ngOnDestroy(): void {
    this.destroyScrollSpy();
  }

  destroyScrollSpy(): void {
    if (this.scrollSpy) {
      this.scrollSpy.destroy();
    }
  }
}
