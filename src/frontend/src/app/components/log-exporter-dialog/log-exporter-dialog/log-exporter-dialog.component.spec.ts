import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LogExporterDialogComponent } from './log-exporter-dialog.component';

describe('LogExporterDialogComponent', () => {
  let component: LogExporterDialogComponent;
  let fixture: ComponentFixture<LogExporterDialogComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [LogExporterDialogComponent],
    });
    fixture = TestBed.createComponent(LogExporterDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
