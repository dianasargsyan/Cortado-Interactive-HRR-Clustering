import { TestBed } from '@angular/core/testing';

import { ArcDiagramService } from './arc-diagram.service';

describe('ArcDiagramService', () => {
  let service: ArcDiagramService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ArcDiagramService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
