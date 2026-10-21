import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ProcessTreeToolboxComponent } from './process-tree-toolbox.component';

describe('ProcessTreeToolboxComponent', () => {
  let component: ProcessTreeToolboxComponent;
  let fixture: ComponentFixture<ProcessTreeToolboxComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ProcessTreeToolboxComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ProcessTreeToolboxComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
