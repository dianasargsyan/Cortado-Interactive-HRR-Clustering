import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ArcDiagramFilterComponent } from './filter.component';

describe('ArcDiagramFilterComponent', () => {
  let component: ArcDiagramFilterComponent;
  let fixture: ComponentFixture<ArcDiagramFilterComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ArcDiagramFilterComponent],
    });
    fixture = TestBed.createComponent(ArcDiagramFilterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
