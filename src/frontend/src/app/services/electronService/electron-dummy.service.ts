import { Injectable } from '@angular/core';
import { ElectronInterface } from './electron-interface';
import { Subject } from 'rxjs';
import { saveAs } from 'file-saver';
import { ROUTES } from '../../constants/backend_route_constants';

@Injectable({
  providedIn: 'root',
})
export class ElectronDummyService implements ElectronInterface {
  constructor() {}

  checkUnsavedChanges$: Subject<any>;
  saveProject$: Subject<any>;

  showSaveDialog(
    fileName: string,
    fileExtension: string,
    blob: Blob,
    buttonLabel: string,
    title: string
  ): Promise<string> {
    saveAs(blob, fileName + '.' + fileExtension);
    return null;
  }
  saveToUserFolder(
    fileName: string,
    fileExtension: string,
    data: string
  ): Promise<undefined> {
    throw new Error('Method not implemented.');
  }
  readFromUserFolder(fileName: string, fileExtension: string): Promise<string> {
    throw new Error('Method not implemented.');
  }

  getWSPort(): Promise<number> {
    const url = ROUTES.BASE_URL;
    const port = Number(url.match(/(?<=\:).+?(?=\/)/g)[0]);
    return Promise.resolve(port);
  }

  unsavedChangesStatus(unsavedChanges: boolean): void {
    throw new Error('Method not implemented.');
  }

  quit(): void {
    throw new Error('Method not implemented.');
  }
}
