import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LpmExplorerRowComponent } from './lpm-explorer-row.component';

describe('LpmExplorerRowComponent', () => {
  let component: LpmExplorerRowComponent;
  let fixture: ComponentFixture<LpmExplorerRowComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [LpmExplorerRowComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(LpmExplorerRowComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
