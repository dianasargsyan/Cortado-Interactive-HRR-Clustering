import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VariantMinerActivitiesFIlterComponent } from './variant-miner-activities-filter.component';

describe('VariantMinerActivitiesFIlterComponent', () => {
  let component: VariantMinerActivitiesFIlterComponent;
  let fixture: ComponentFixture<VariantMinerActivitiesFIlterComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [VariantMinerActivitiesFIlterComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(VariantMinerActivitiesFIlterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
