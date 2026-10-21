import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VariantInfoExplorerComponent } from './variant-info-explorer.component';

describe('VariantInfoExplorerComponent', () => {
  let component: VariantInfoExplorerComponent;
  let fixture: ComponentFixture<VariantInfoExplorerComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [VariantInfoExplorerComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(VariantInfoExplorerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
