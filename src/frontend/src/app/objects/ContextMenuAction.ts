export type ContextMenuAction<T> = {
  event: MouseEvent | KeyboardEvent;
  value?: T;
};
