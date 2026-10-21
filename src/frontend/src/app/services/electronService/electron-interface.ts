import { Subject } from 'rxjs';

export interface ElectronInterface {
  checkUnsavedChanges$: Subject<any>;
  saveProject$: Subject<any>;

  showSaveDialog(
    fileName: string,
    fileExtension: string,
    blob: Blob,
    buttonLabel: string,
    title: string
  ): Promise<string>;

  saveToUserFolder(
    fileName: string,
    fileExtension: string,
    data: string
  ): Promise<undefined>;

  readFromUserFolder(fileName: string, fileExtension: string): Promise<string>;

  getWSPort(): Promise<number>;

  unsavedChangesStatus(unsavedChanges: boolean): void;

  quit(): void;
}
