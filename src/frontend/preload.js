const { contextBridge, ipcRenderer } = require("electron");

console.warn("Running Preload Script...");

contextBridge.exposeInMainWorld("electronAPI", {
  requestRestart: () => ipcRenderer.send("restartBackend"),
  showSaveDialog: (fileName, fileExtension, base64File, buttonLabel, title) =>
    ipcRenderer.invoke(
      "showSaveDialog",
      fileName,
      fileExtension,
      base64File,
      buttonLabel,
      title
    ),
  saveToUserFolder: (fileName, fileExtension, base64File) =>
    ipcRenderer.send("saveToUserFolder", fileName, fileExtension, base64File),
  readFromUserFolder: (fileName, fileExtension) =>
    ipcRenderer.invoke("readFromUserFolder", fileName, fileExtension),
  getWSPort: () => ipcRenderer.invoke("getWSPort"),
  onSaveProject: (callback) => ipcRenderer.on("save-project", callback),
  onCheckUnsavedChanges: (callback) =>
    ipcRenderer.on("check-unsaved-changes", callback),
  unsavedChanges: (unsavedChanges) =>
    ipcRenderer.send("unsaved-changes", unsavedChanges),
  quit: () => ipcRenderer.send("quit", value),
});

document.onreadystatechange = function () {
  if (document.readyState == "complete") {
    const $ = require("jquery"); // Make Jquery Aviable in the Window after load
  }
};
