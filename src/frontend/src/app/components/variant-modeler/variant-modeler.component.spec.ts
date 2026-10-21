import { ComponentFixture, TestBed } from '@angular/core/testing';
import { VariantModelerComponent } from './variant-modeler.component';

describe('VariantModelerComponent', () => {
  let component: VariantModelerComponent;
  let fixture: ComponentFixture<VariantModelerComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [VariantModelerComponent],
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(VariantModelerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
