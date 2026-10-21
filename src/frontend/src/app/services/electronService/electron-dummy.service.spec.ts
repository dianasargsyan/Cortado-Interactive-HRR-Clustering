import { TestBed } from '@angular/core/testing';

import { ElectronDummyService } from './electron-dummy.service';

describe('ElectronDummyService', () => {
  let service: ElectronDummyService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ElectronDummyService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
