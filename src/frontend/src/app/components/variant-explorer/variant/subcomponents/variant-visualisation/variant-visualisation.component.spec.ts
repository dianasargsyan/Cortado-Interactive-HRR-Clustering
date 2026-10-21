import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VariantVisualisationComponent } from './variant-visualisation.component';

describe('VariantVisualisationComponent', () => {
  let component: VariantVisualisationComponent;
  let fixture: ComponentFixture<VariantVisualisationComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [VariantVisualisationComponent],
    });
    fixture = TestBed.createComponent(VariantVisualisationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
