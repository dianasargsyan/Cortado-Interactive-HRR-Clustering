import { LogService } from 'src/app/services/logService/log.service';
import { Injectable } from '@angular/core';
import { Observable, BehaviorSubject } from 'rxjs';

import Swal from 'sweetalert2';
import {
  ProcessTree,
  ProcessTreeOperator,
} from 'src/app/objects/ProcessTree/ProcessTree';
import {
  markNodeAsFrozen,
  markNodeAsNonFrozen,
} from 'src/app/objects/ProcessTree/utility-functions/process-tree-freeze';
import {
  checkForLoadedTreeIntegrity,
  processTreesEqual,
} from 'src/app/objects/ProcessTree/utility-functions/process-tree-integrity-check';
import {
  renameProcessTreeLeafs,
  getSetOfActivitiesInProcessTree,
} from 'src/app/objects/ProcessTree/utility-functions/process-tree-transform';
import {
  delete_subtree,
  NodeInsertionStrategy,
  createNewRandomNode,
  insertNode,
} from 'src/app/objects/ProcessTree/utility-functions/process-tree-edit-tree';
import { computeLeafNodeWidth } from 'src/app/utils/render-utils';

@Injectable({
  providedIn: 'root',
})
export class ProcessTreeService {
  constructor(private logService: LogService) {
    this.logService.activitiesInEventLog$.subscribe((activites) => {
      this.nodeWidthCache = computeLeafNodeWidth(
        Object.keys(activites),
        this.nodeWidthCache
      );
    });

    this.logService.loadedEventLog$.subscribe((log) => {
      if (log && log !== 'preload') {
        this.nodeWidthCache = computeLeafNodeWidth(
          Object.keys(this.logService.activitiesInEventLog),
          this.nodeWidthCache
        );
      }
    });
  }

  private _selectedRootNodeID = new BehaviorSubject<number>(null);

  get selectedRootNodeID$(): Observable<number> {
    return this._selectedRootNodeID.asObservable();
  }

  set selectedRootNodeID(node: number) {
    this._selectedRootNodeID.next(node);
  }

  get selectedRootNodeID(): number {
    return this._selectedRootNodeID.getValue();
  }

  private _nodeWidthCache = new BehaviorSubject<Map<string, number>>(
    new Map<string, number>()
  );

  get nodeWidthCache$(): Observable<Map<string, number>> {
    return this._nodeWidthCache.asObservable();
  }

  get nodeWidthCache() {
    return this._nodeWidthCache.getValue();
  }

  set nodeWidthCache(map: Map<string, number>) {
    this._nodeWidthCache.next(map);
  }

  private _correctTreeSyntax = new BehaviorSubject<boolean>(false);

  get correctTreeSyntax$(): Observable<boolean> {
    return this._correctTreeSyntax.asObservable();
  }

  set correctTreeSyntax(flag: boolean) {
    this._correctTreeSyntax.next(flag);
  }

  get correctTreeSyntax(): boolean {
    return this._correctTreeSyntax.getValue();
  }

  private _currentTreeString = new BehaviorSubject<string>('');

  get currentTreeString$(): Observable<string> {
    return this._currentTreeString.asObservable();
  }

  set currentTreeString(syntaxObj: any) {
    this._currentTreeString.next(syntaxObj);
  }

  get currentTreeString() {
    return this._currentTreeString.getValue();
  }

  private _selectedTree: BehaviorSubject<ProcessTree> =
    new BehaviorSubject<ProcessTree>(undefined);

  get selectedTree$(): Observable<any> {
    return this._selectedTree.asObservable();
  }

  get selectedTree(): any {
    return this._selectedTree.getValue();
  }

  set selectedTree(pt: ProcessTree) {
    this._selectedTree.next(pt);
  }

  private _currentDisplayedProcessTree = new BehaviorSubject<ProcessTree>(null);

  get currentDisplayedProcessTree$(): Observable<ProcessTree> {
    return this._currentDisplayedProcessTree.asObservable();
  }

  get currentDisplayedProcessTree(): ProcessTree {
    return this._currentDisplayedProcessTree.getValue();
  }

  private _activitiesInCurrentTree = new BehaviorSubject<Set<string>>(
    new Set<string>()
  );

  private processTreeBuffer = new BehaviorSubject<ProcessTree>(null);

  get bufferedProcessTree() {
    return this.processTreeBuffer.getValue();
  }

  public deleteActivityFromProcessTreeActivities(activityName: string): any {
    if (this.activitiesInCurrentTree) {
      this.activitiesInCurrentTree.delete(activityName);
    }
  }

  public renameActivityInProcessTree(
    activityName: string,
    newActivityName: string
  ): any {
    if (
      this.activitiesInCurrentTree &&
      this.activitiesInCurrentTree.delete(activityName)
    )
      this.activitiesInCurrentTree.add(newActivityName);

    if (this.currentDisplayedProcessTree) {
      this.currentDisplayedProcessTree = renameProcessTreeLeafs(
        this.currentDisplayedProcessTree,
        activityName,
        newActivityName
      );
    }
  }

  get activitiesInCurrentTree$(): Observable<Set<string>> {
    return this._activitiesInCurrentTree.asObservable();
  }

  get activitiesInCurrentTree(): Set<string> {
    return this._activitiesInCurrentTree.getValue();
  }

  set activitiesInCurrentTree(activities) {
    this._activitiesInCurrentTree.next(activities);
  }

  set currentDisplayedProcessTree(tree: any) {
    if (tree && !(tree instanceof ProcessTree)) {
      tree = ProcessTree.fromObj(tree);
    }

    this.activitiesInCurrentTree = getSetOfActivitiesInProcessTree(tree);
    const activites = Object.keys(this.logService.activitiesInEventLog);

    if (checkForLoadedTreeIntegrity(tree, activites).size > 0) {
      const unknownActivities = Array.from(
        checkForLoadedTreeIntegrity(tree, activites)
      );
      this.nodeWidthCache = computeLeafNodeWidth(
        unknownActivities,
        this.nodeWidthCache
      );

      Swal.fire({
        title:
          '<tspan class = "text-warning">Current process tree contains unkown activites</tspan>',
        html:
          '<b>Error Message: </b><br>' +
          '<code> The loaded tree contains activities \
              that do not appear in the currently loaded log.\
              </code> <br> <br> Unknown Activites: ' +
          '<tspan class = "text-danger">' +
          unknownActivities.join(', ') +
          '</tspan>',
        icon: 'warning',
        showCloseButton: false,
        showConfirmButton: false,
        showCancelButton: true,
        cancelButtonText: 'close',
      });
    }

    this._currentDisplayedProcessTree.next(tree);
  }

  public set_currentDisplayedProcessTree_with_Cache(tree: any) {
    if (tree && !(tree instanceof ProcessTree)) {
      tree = ProcessTree.fromObj(tree);
    }
    this._currentDisplayedProcessTree.next(tree);
    this.activitiesInCurrentTree = getSetOfActivitiesInProcessTree(tree);

    // add activities in the tree to nodeWidthCache in processTreeService
    this.nodeWidthCache = computeLeafNodeWidth(
      Array.from(this.activitiesInCurrentTree),
      this.nodeWidthCache
    );

    this.cacheCurrentTree(tree);
  }

  previousTreeObjects: ProcessTree[] = [];

  private _treeCacheLength = new BehaviorSubject<number>(0);
  private _treeCacheIndex = new BehaviorSubject<number>(0);

  get treeCacheLength$(): Observable<number> {
    return this._treeCacheLength.asObservable();
  }

  set treeCacheLength(node: number) {
    this._treeCacheLength.next(node);
  }

  get treeCacheLength(): number {
    return this._treeCacheLength.getValue();
  }

  get treeCacheIndex$(): Observable<number> {
    return this._treeCacheIndex.asObservable();
  }

  set treeCacheIndex(node: number) {
    this._treeCacheIndex.next(node);
  }

  get treeCacheIndex(): number {
    return this._treeCacheIndex.getValue();
  }

  cacheCurrentTree(root: ProcessTree): void {
    if (processTreesEqual(root, this.previousTreeObjects[this.treeCacheIndex]))
      return;
    if (this.treeCacheIndex < this.previousTreeObjects.length - 1) {
      // before change, undo was pressed --> remove newer versions since older version of process tree was changed
      this.previousTreeObjects = this.previousTreeObjects.slice(
        0,
        this.treeCacheIndex + 1
      );
    }

    const lastTreeObject =
      this.previousTreeObjects[this.previousTreeObjects.length - 1];

    if (root) {
      if (lastTreeObject !== null) {
        this.previousTreeObjects.push(root.copy(true));
      } else {
        this.previousTreeObjects[this.previousTreeObjects.length - 1] =
          root.copy(true);
        this.treeCacheIndex--;
      }
    } else {
      this.previousTreeObjects.push(null);
    }

    if (this.treeCacheIndex) {
      this.treeCacheIndex += 1;
    } else {
      this.treeCacheIndex = this.previousTreeObjects.length - 1;
    }

    this.treeCacheLength = this.previousTreeObjects.length;
  }

  getFrozenList(previousTree) {
    let frozen_list = [];
    if (previousTree.frozen) {
      frozen_list.push(previousTree.id);
    }
    for (const child of previousTree.children) {
      frozen_list = frozen_list.concat(this.getFrozenList(child));
    }
    return frozen_list;
  }

  getFrozenTree(treeToLoad, previousTree) {
    let frozen_list = this.getFrozenList(previousTree);
    var nodesToCheck = [];
    nodesToCheck.push(treeToLoad);
    while (nodesToCheck.length > 0) {
      let nodeToCheck = nodesToCheck.pop();
      if (frozen_list.includes(nodeToCheck.id)) {
        markNodeAsFrozen(nodeToCheck);
      }
      nodesToCheck = nodesToCheck.concat(nodeToCheck.children);
    }
  }

  undo() {
    if (
      this.treeCacheIndex &&
      this.treeCacheIndex > 0 &&
      this.previousTreeObjects.length > 1
    ) {
      this.treeCacheIndex--;

      let treeToLoad = null;
      if (this.previousTreeObjects[this.treeCacheIndex]) {
        treeToLoad = this.previousTreeObjects[this.treeCacheIndex].copy();
        this.getFrozenTree(
          treeToLoad,
          this.previousTreeObjects[this.treeCacheIndex + 1]
        );
      }

      this.selectedRootNodeID = null;
      this.currentDisplayedProcessTree = treeToLoad;
    }
  }

  redo() {
    if (this.treeCacheIndex < this.previousTreeObjects.length - 1) {
      this.treeCacheIndex++;

      let treeToLoad = null;
      if (this.previousTreeObjects[this.treeCacheIndex]) {
        treeToLoad = this.previousTreeObjects[this.treeCacheIndex].copy();
        this.getFrozenTree(
          treeToLoad,
          this.previousTreeObjects[this.treeCacheIndex - 1]
        );
      }

      this.selectedRootNodeID = null;

      this.currentDisplayedProcessTree = treeToLoad;
    }
  }

  deleteTreeHistory() {
    this.previousTreeObjects = [];
    this.treeCacheIndex = 0;
    this.treeCacheLength = 0;
  }

  freezeSubtree(node: ProcessTree) {
    if (!node.frozen) {
      markNodeAsFrozen(node);
    } else {
      markNodeAsNonFrozen(node);
    }

    this.currentDisplayedProcessTree = this.currentDisplayedProcessTree;
    this.selectedRootNodeID = null;
  }

  shiftSubtreeUp(tree: ProcessTree): void {
    if (tree.parent && tree.parent.parent) {
      const siblings = tree.parent.children;
      const idxInParentChildList = siblings.indexOf(tree);

      const parentSiblings = tree.parent.parent.children;
      const parentIdxInItsSiblingsList = parentSiblings.indexOf(tree.parent);

      // Remove tree as child from old parent
      siblings.splice(idxInParentChildList, 1);

      // Add tree as sibling to old parent
      tree.parent = tree.parent.parent;
      parentSiblings.splice(parentIdxInItsSiblingsList + 1, 0, tree);

      this.set_currentDisplayedProcessTree_with_Cache(
        this.currentDisplayedProcessTree
      );
    }
  }

  shiftSubtreeToLeft(tree: ProcessTree): void {
    if (tree.parent) {
      const siblings = tree.parent.children;
      const idxInParentChildList = siblings.indexOf(tree);
      if (idxInParentChildList > 0) {
        const childToRight = siblings[idxInParentChildList - 1];
        const childToLeft = siblings[idxInParentChildList];
        siblings[idxInParentChildList] = childToRight;
        siblings[idxInParentChildList - 1] = childToLeft;

        this.set_currentDisplayedProcessTree_with_Cache(
          this.currentDisplayedProcessTree
        );
      }
    }
  }

  shiftSubtreeToRight(tree: ProcessTree): void {
    if (tree.parent) {
      const siblings = tree.parent.children;
      const idxInParentChildList = siblings.indexOf(tree);
      if (idxInParentChildList < siblings.length - 1) {
        const childToRight = siblings[idxInParentChildList];
        const childToLeft = siblings[idxInParentChildList + 1];
        siblings[idxInParentChildList + 1] = childToRight;
        siblings[idxInParentChildList] = childToLeft;

        this.set_currentDisplayedProcessTree_with_Cache(
          this.currentDisplayedProcessTree
        );
      }
    }
  }

  deleteSelected(tree_to_delete: ProcessTree) {
    // this.cacheCurrentTree(this.currentDisplayedProcessTree);
    const newTree = this.currentDisplayedProcessTree;

    if (this.currentDisplayedProcessTree === tree_to_delete) {
      this.set_currentDisplayedProcessTree_with_Cache(null);
    } else {
      this.set_currentDisplayedProcessTree_with_Cache(
        delete_subtree(newTree, tree_to_delete)
      );
    }

    this.selectedRootNodeID = null;
  }

  insertNewNode(
    selectedNode: ProcessTree,
    strat: NodeInsertionStrategy,
    operator: ProcessTreeOperator,
    label: string
  ) {
    const newNode: ProcessTree = createNewRandomNode(label, operator);
    //newNode.selected = true;

    if (this.currentDisplayedProcessTree) {
      insertNode(selectedNode, newNode, strat, operator, label);

      if (!newNode.parent || selectedNode.parent == newNode) {
        this.currentDisplayedProcessTree = newNode;
      }
      this.selectedRootNodeID = newNode.id;
      //this.selectedRootNodeID = selectedNode.id; //edited
      this.set_currentDisplayedProcessTree_with_Cache(
        this.currentDisplayedProcessTree
      );
    } else {
      // empty tree - just add a single node
      this.currentDisplayedProcessTree = newNode;
      this.selectedRootNodeID = newNode.id;
    }
  }

  copySubtreeToBuffer(processTree: ProcessTree) {
    this.processTreeBuffer.next(processTree.copy());
  }

  pasteSubtreeFromBuffer(parentNode: ProcessTree) {
    if (this.processTreeBuffer) {
      const copiedTree = this.bufferedProcessTree.copy(true, true);
      if (parentNode) {
        if (parentNode.label)
          throw new Error('Cannot insert children below activities.');

        copiedTree.parent = parentNode;
        parentNode.children.push(copiedTree);
      } else {
        this.currentDisplayedProcessTree = copiedTree;
      }
      this.set_currentDisplayedProcessTree_with_Cache(
        this.currentDisplayedProcessTree
      );
    }
  }

  makeSubtreeOptional(processTree: ProcessTree) {
    const choice = createNewRandomNode(null, ProcessTreeOperator.choice);
    const tau = createNewRandomNode(ProcessTreeOperator.tau, null);

    if (processTree.parent) {
      const siblings = processTree.parent.children;
      const idxInParentChildList = siblings.indexOf(processTree);

      siblings.splice(idxInParentChildList, 1, choice);
    } else {
      this.currentDisplayedProcessTree = choice;
    }

    choice.parent = processTree.parent;
    choice.children = [tau, processTree];
    processTree.parent = choice;
    tau.parent = choice;

    this.set_currentDisplayedProcessTree_with_Cache(
      this.currentDisplayedProcessTree
    );
  }

  makeSubtreeRepeatable(processTree: ProcessTree) {
    const loop = createNewRandomNode(null, ProcessTreeOperator.loop);
    const tau = createNewRandomNode(ProcessTreeOperator.tau, null);

    if (processTree.parent) {
      const siblings = processTree.parent.children;
      const idxInParentChildList = siblings.indexOf(processTree);

      siblings.splice(idxInParentChildList, 1, loop);
    } else {
      this.currentDisplayedProcessTree = loop;
    }
    loop.parent = processTree.parent;
    loop.children = [processTree, tau];
    processTree.parent = loop;
    tau.parent = loop;

    this.set_currentDisplayedProcessTree_with_Cache(
      this.currentDisplayedProcessTree
    );
  }
}
