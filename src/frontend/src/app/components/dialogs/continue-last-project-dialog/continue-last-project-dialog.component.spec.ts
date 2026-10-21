import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ContinueLastProjectDialogComponent } from './continue-last-project-dialog.component';

describe('ContinueLastProjectDialogComponent', () => {
  let component: ContinueLastProjectDialogComponent;
  let fixture: ComponentFixture<ContinueLastProjectDialogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ContinueLastProjectDialogComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ContinueLastProjectDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
