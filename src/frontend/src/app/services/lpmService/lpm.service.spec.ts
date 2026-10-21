import { TestBed } from '@angular/core/testing';

import { LpmService } from './lpm.service';

describe('LpmService', () => {
  let service: LpmService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LpmService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
