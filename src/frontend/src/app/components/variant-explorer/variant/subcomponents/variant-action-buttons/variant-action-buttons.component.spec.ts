import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VariantActionButtonsComponent } from './variant-action-buttons.component';

describe('VariantDeleteButtonComponent', () => {
  let component: VariantActionButtonsComponent;
  let fixture: ComponentFixture<VariantActionButtonsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [VariantActionButtonsComponent],
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(VariantActionButtonsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
