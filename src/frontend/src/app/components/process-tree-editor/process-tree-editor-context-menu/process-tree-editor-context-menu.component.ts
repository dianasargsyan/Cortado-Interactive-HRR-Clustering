import { Component, ViewChild } from '@angular/core';
import { ContextMenuComponent } from '@perfectmemory/ngx-contextmenu';
import { ContextMenuAction } from 'src/app/objects/ContextMenuAction';
import { ProcessTree } from 'src/app/objects/ProcessTree/ProcessTree';
import { ProcessTreeService } from 'src/app/services/processTreeService/process-tree.service';

@Component({
  selector: 'app-process-tree-editor-context-menu',
  templateUrl: './process-tree-editor-context-menu.component.html',
  styleUrls: ['./process-tree-editor-context-menu.component.css'],
})
export class ProcessTreeEditorContextMenuComponent {
  @ViewChild('contextMenu', { static: true })
  public contextMenu?: ContextMenuComponent<any>;

  constructor(private processTreeService: ProcessTreeService) {
    this.pasteDisabled = this.pasteDisabled.bind(this);
  }

  copyDisabled(pt: ProcessTree) {
    return !pt;
  }

  onCopy(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.copySubtreeToBuffer(action.value);
  }

  cutDisabled(pt: ProcessTree) {
    return !pt;
  }

  onCut(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.copySubtreeToBuffer(action.value);
    this.processTreeService.deleteSelected(action.value);
  }

  pasteDisabled(pt: ProcessTree) {
    return !this.processTreeService.bufferedProcessTree || !pt || !!pt?.label;
  }

  onPaste(action: ContextMenuAction<ProcessTree>) {
    this.processTreeService.pasteSubtreeFromBuffer(action.value);
  }

  deleteDisabled(pt: ProcessTree) {
    return !pt;
  }

  onDelete(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.deleteSelected(action.value);
  }

  freezeDisabled(pt: ProcessTree) {
    return !pt;
  }

  onFreeze(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.freezeSubtree(action.value);
  }

  shiftLeftDisabled(pt: ProcessTree) {
    if (!pt) return true;
    if (!pt.parent) return true;
    if (pt.parent.children.indexOf(pt) == 0) return true;
    return false;
  }

  onShiftLeft(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.shiftSubtreeToLeft(action.value);
  }

  shiftUpDisabled(pt: ProcessTree) {
    if (!pt) return true;
    if (!pt.parent || !pt.parent.parent) return true;
    return false;
  }

  onShiftUp(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.shiftSubtreeUp(action.value);
  }

  shiftRightDisabled(pt: ProcessTree) {
    if (!pt) return true;
    if (!pt.parent) return true;
    if (pt.parent.children.indexOf(pt) == pt.parent.children.length - 1)
      return true;
    return false;
  }

  onShiftRight(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.shiftSubtreeToRight(action.value);
  }

  onMakeOptional(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.makeSubtreeOptional(action.value);
  }

  makeOptionalDisabled(pt: ProcessTree) {
    return !pt;
  }

  onMakeRepeatable(action: ContextMenuAction<ProcessTree>) {
    if (!action.value) return;
    this.processTreeService.makeSubtreeRepeatable(action.value);
  }

  makeRepeatableDisabled(pt: ProcessTree) {
    return !pt;
  }
}
