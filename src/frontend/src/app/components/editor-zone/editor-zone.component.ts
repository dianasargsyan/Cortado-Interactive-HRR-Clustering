import { EditorService } from './../../services/editorService/editor.service';
import {
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  AfterViewInit,
  Output,
  EventEmitter,
  OnDestroy,
  forwardRef,
  Input,
  ChangeDetectionStrategy,
} from '@angular/core';
import { take } from 'rxjs/operators';
import { vqlEditorOptions } from './editor-languages/vql-editor-options';
import {
  ControlValueAccessor,
  NG_VALIDATORS,
  NG_VALUE_ACCESSOR,
  ValidationErrors,
  Validator,
} from '@angular/forms';

import * as Monaco from 'monaco-editor';
declare var monaco: typeof Monaco;

@Component({
  selector: 'app-editor-zone',
  templateUrl: './editor-zone.component.html',
  styleUrls: ['./editor-zone.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => EditorZoneComponent),
      multi: true,
    },
    {
      provide: NG_VALIDATORS,
      useExisting: forwardRef(() => EditorZoneComponent),
      multi: true,
    },
  ],
})
export class EditorZoneComponent
  implements AfterViewInit, OnDestroy, ControlValueAccessor, Validator
{
  constructor(private monacoEditorService: EditorService) {}

  validate(): ValidationErrors {
    return !this.parsedError
      ? null
      : {
          monaco: {
            value: this.parsedError.split('|'),
          },
        };
  }

  get model() {
    return this._editor && this._editor.getModel();
  }

  get modelMarkers() {
    return (
      this.model &&
      monaco.editor.getModelMarkers({
        resource: this.model.uri,
      })
    );
  }

  writeValue(value: string): void {
    this._editorContent = value;
    if (this._editor && value) {
      this._editor.setValue(value);
    } else if (this._editor) {
      this._editor.setValue('');
    }
  }

  registerOnChange(fn: any): void {
    this._propagateChange = fn;
  }

  registerOnErrorStatusChange(fn: any): void {
    this._onErrorStatusChange = fn;
  }

  registerOnTouched(fn: any): void {
    this._onTouched = fn;
  }

  protected _options;
  protected _editorContent: string = '';

  parsedError: string;

  private _onTouched: () => void = () => {};
  private _onErrorStatusChange: () => void = () => {};
  private _propagateChange: (_: any) => any = () => {};

  private _editor: Monaco.editor.IStandaloneCodeEditor;

  @Output() editor: EventEmitter<any> = new EventEmitter();

  @ViewChild('editorContainer', { static: true }) _editorContainer: ElementRef;

  private initMonaco(): void {
    if (!this.monacoEditorService.loaded) {
      this.monacoEditorService.loadingFinished.pipe(take(1)).subscribe(() => {
        this.initMonaco();
      });
      return;
    }

    console.log('Creating Editor...');

    this._editor = monaco.editor.create(
      this._editorContainer.nativeElement,
      vqlEditorOptions
    );

    const model: Monaco.editor.ITextModel = this._editor.getModel();

    this.registerEditorListeners();
    this.editor.emit(this._editor);
  }

  ngAfterViewInit(): void {
    this.initMonaco();
  }

  registerOnChangeCallback(fn: (val: string) => void) {
    // Prevent the default context menu from appearing
    this._editor.onContextMenu((e) => {
      e.event.preventDefault();
    });

    this._editor.onDidChangeModelContent((event) => {
      fn(this._editor.getValue());
    });
  }

  registerValidatorFunction(fn) {
    this._editor.onDidChangeModelContent((event) => {
      fn(this._editor.getModel());
    });
  }

  registerEditorListeners() {
    this._editor.onDidChangeModelContent(() => {
      this._propagateChange(this._editor.getValue());
    });

    this._editor.onDidChangeModelDecorations(() => {
      const currentParsedError = this.modelMarkers
        .map(({ message }) => message)
        .join('|');

      this.parsedError = currentParsedError;
      this._onErrorStatusChange();
    });

    this._editor.onDidBlurEditorText(() => {
      this._onTouched();
    });

    // Add event listener for ending query with semicolon
    this._editor.onDidChangeModelContent((event) => {
      const model = this._editor.getModel();
      if (!model) return;

      // if query already has a semicolon do nothing
      if (model.getLinesContent().join().includes(';')) return;

      const lineCount = model.getLineCount();

      // Traverse the lines in reverse order until we find the last non-empty line
      let lastNonEmptyLineIndex: number;
      for (
        lastNonEmptyLineIndex = lineCount;
        lastNonEmptyLineIndex >= 0;
        lastNonEmptyLineIndex--
      ) {
        // do nothing if not a single line has content
        if (lastNonEmptyLineIndex == 0) return;
        if (model.getLineContent(lastNonEmptyLineIndex).trim().length > 0)
          break;
      }

      const appendSemicolonEdit = {
        range: new monaco.Range(
          lastNonEmptyLineIndex,
          model.getLineContent(lastNonEmptyLineIndex).length + 1,
          lastNonEmptyLineIndex,
          model.getLineContent(lastNonEmptyLineIndex).length + 1
        ),
        text: ';',
      };

      // Insert a semicolon at the end of the last line
      this._editor.executeEdits(
        '',
        [appendSemicolonEdit],
        [this._editor.getSelection()]
      );
    });
  }

  ngOnDestroy() {
    if (this._editor) {
      this._editor.dispose();
    }
  }
}
