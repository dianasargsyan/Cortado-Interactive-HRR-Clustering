import { TestBed } from '@angular/core/testing';

import { LogExportService } from './log-export.service';

describe('LogExportService', () => {
  let service: LogExportService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LogExportService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
