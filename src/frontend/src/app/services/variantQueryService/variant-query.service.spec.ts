import { TestBed } from '@angular/core/testing';

import { VariantQueryService } from './variant-query.service';

describe('VariantQueryService', () => {
  let service: VariantQueryService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(VariantQueryService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
