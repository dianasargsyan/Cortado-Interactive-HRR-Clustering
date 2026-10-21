import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ProcessTreeEditorContextMenuComponent } from './process-tree-editor-context-menu.component';

describe('ProcessTreeEditorContextMenuComponent', () => {
  let component: ProcessTreeEditorContextMenuComponent;
  let fixture: ComponentFixture<ProcessTreeEditorContextMenuComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ProcessTreeEditorContextMenuComponent],
    });
    fixture = TestBed.createComponent(ProcessTreeEditorContextMenuComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
