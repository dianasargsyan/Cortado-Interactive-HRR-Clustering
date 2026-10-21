import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class DocumentationService {
  showDocumentationEvent: Subject<string> = new Subject<string>();
  showDocumentationDialog(heading: string = null) {
    this.showDocumentationEvent.next(heading);
  }
}
