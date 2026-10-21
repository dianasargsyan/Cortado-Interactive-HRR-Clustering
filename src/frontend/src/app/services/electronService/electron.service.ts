import { Injectable } from '@angular/core';
import { blobToBase64 } from 'src/app/utils/util';
import { Subject } from 'rxjs';
import { ElectronInterface } from './electron-interface';

@Injectable()
export class ElectronService implements ElectronInterface {
  private electronApi = (<any>window).electronAPI;

  public checkUnsavedChanges$ = new Subject<void>();
  public saveProject$ = new Subject<void>();

  constructor() {
    this.electronApi?.onCheckUnsavedChanges(() => {
      this.checkUnsavedChanges$.next();
    });

    this.electronApi?.onSaveProject(() => {
      this.saveProject$.next();
    });
  }

  public async showSaveDialog(
    fileName: string,
    fileExtension: string,
    blob: Blob,
    buttonLabel: string,
    title: string
  ): Promise<string> {
    let base64File = await blobToBase64(blob);

    // returns filePath of savedFile or undefined if aborted
    return this.electronApi.showSaveDialog(
      fileName,
      fileExtension,
      base64File,
      buttonLabel,
      title
    );
  }

  public saveToUserFolder(
    fileName: string,
    fileExtension: string,
    data: string
  ): Promise<undefined> {
    return this.electronApi.saveToUserFolder(fileName, fileExtension, data);
  }

  public readFromUserFolder(
    fileName: string,
    fileExtension: string
  ): Promise<string> {
    return this.electronApi.readFromUserFolder(fileName, fileExtension);
  }

  public async getWSPort(): Promise<number> {
    return this.electronApi.getWSPort();
  }

  public unsavedChangesStatus(unsavedChanges: boolean) {
    this.electronApi.unsavedChanges(unsavedChanges);
  }

  public quit(): void {
    this.electronApi.quit();
  }
}
