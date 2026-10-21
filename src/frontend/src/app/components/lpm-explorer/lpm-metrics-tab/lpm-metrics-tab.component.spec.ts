import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LpmMetricsTabComponent } from './lpm-metrics-tab.component';

describe('LpmMetricsTabComponent', () => {
  let component: LpmMetricsTabComponent;
  let fixture: ComponentFixture<LpmMetricsTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [LpmMetricsTabComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(LpmMetricsTabComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
