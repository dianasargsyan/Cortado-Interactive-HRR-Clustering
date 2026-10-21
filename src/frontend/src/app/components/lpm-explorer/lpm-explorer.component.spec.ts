import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LpmExplorerComponent } from './lpm-explorer.component';

describe('LpmExplorerComponent', () => {
  let component: LpmExplorerComponent;
  let fixture: ComponentFixture<LpmExplorerComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [LpmExplorerComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(LpmExplorerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
