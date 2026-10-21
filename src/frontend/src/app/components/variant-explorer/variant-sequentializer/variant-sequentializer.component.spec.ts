import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VariantSequentializerComponent } from './variant-sequentializer.component';
import { VariantSequentializerComponent } from './variant-sequentializer.component';

describe('VariantSequentializerComponent', () => {
  let component: VariantSequentializerComponent;
  let fixture: ComponentFixture<VariantSequentializerComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [VariantSequentializerComponent],
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(VariantSequentializerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
