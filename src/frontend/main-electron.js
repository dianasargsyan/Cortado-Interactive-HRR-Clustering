const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
var fs = require("fs");
const {
  showSaveDialog,
  saveToUserFolder,
  readFromUserFolder,
} = require("./util");
const nativeImage = require("electron").nativeImage;
const url = require("url");
const path = require("path");
const kill = require("tree-kill");
const ChildProcess = require("child_process");
const Store = require("electron-store");
const executablePath = app.getPath("exe");
const downloadFolder = app.getPath("downloads");
const backendWorkDir = path.join(
  path.dirname(executablePath),
  process.platform === "darwin" ? ".." : "", // electron-builder puts the executable in `MacOS/` folder,
  // so must move one level up to find `cortado-backend`
  "cortado-backend"
);
const rawBackendExecutablePath = path.join(
  backendWorkDir,
  process.platform === "win32" ? "cortado-backend.exe" : "cortado-backend"
);

const backendExecutablePath = `"${rawBackendExecutablePath}"`;

const lastAcceptedVersionKey = "lastAcceptedVersion";
const isDevelopment = process.env.NODE_ENV === "development";

let mainCortadoWin;
let backendProcess;

let closeAttempts = 0;
let lastCloseAttempt = 0;
const closeAttemptThresholdInMs = 3000;

WS_PORT = 40000;
const portfinder = require("portfinder");

function startBackend() {
  let portArgument = "--WEBSERVER_PORT " + WS_PORT;
  return ChildProcess.spawn(backendExecutablePath, [portArgument], {
    shell: true,
    detached: true,
    windowsHide: false,
    cwd: backendWorkDir,
  });
}

ipcMain.on("restartBackend", () => {
  if (isDevelopment) {
    console.log(
      "DEV: Backend restart requested but backend is not managed while in development mode."
    );
  } else {
    console.log("Restarting Backend");
    killBackendProcess();
    backendProcess = startBackend();
  }
});

ipcMain.handle(
  "showSaveDialog",
  (_, fileName, fileExtension, base64File, buttonLabel, title) =>
    showSaveDialog(
      downloadFolder,
      dialog,
      fs,
      mainCortadoWin,
      fileName,
      fileExtension,
      base64File,
      buttonLabel,
      title
    )
);

function createMainApplicationWindow() {
  mainCortadoWin = new BrowserWindow({
    minHeight: 600,
    minWidth: 900,
    width: 1000,
    height: 800,
    frame: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: true,
      contextIsolation: true,
    },
    darkTheme: true,
  });
  mainCortadoWin.removeMenu();

  //mainCortadoWin.webContents.openDevTools()
  //mainCortadoWin.loadURL('data:text/html;charset=utf-8,' + backendExecutablePathWindows);

  if (isDevelopment) {
    mainCortadoWin.loadURL("http://localhost:4444");
    mainCortadoWin.webContents.openDevTools();
  } else {
    mainCortadoWin.loadFile("dist/index.html");
  }

  mainCortadoWin.on("closed", function () {
    mainCortadoWin = null;
    app.quit();
  });

  mainCortadoWin.on("close", async (e) => {
    const now = Date.now();
    if (now - lastCloseAttempt > closeAttemptThresholdInMs) closeAttempts = 0;
    if (closeAttempts < 2) {
      e.preventDefault(); // Prevents default close behavior
      // ask projectService for unsaved Changes
      // response on "unsaved-changes"
      mainCortadoWin.webContents.send("check-unsaved-changes");
      closeAttempts++;
      lastCloseAttempt = now;
    }
  });

  // prevent external links from being opened in an electron window
  mainCortadoWin.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

function killBackendProcess() {
  if (backendProcess) {
    if (process.platform == "win32") {
      kill(backendProcess.pid);
    } else {
      ChildProcess.execSync("killall -9 cortado-backend", { shell: "/bin/sh" });
    }
  }
}

app.whenReady().then(function () {
  if (!isDevelopment) {
    // Find free port
    portfinder.getPort(
      {
        port: 40000, // minimum port
        stopPort: 49999, // maximum port
      },
      function (err, port) {
        WS_PORT = port;
        createMainApplicationWindow();
        backendProcess = startBackend();
      }
    );
  } else {
    createMainApplicationWindow();
  }
});

app.on("quit", function () {
  if (!isDevelopment) {
    killBackendProcess();
  }
});

app.on("window-all-closed", function () {
  //On macOS specific close process
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", function () {
  //macOS specific
  if (mainCortadoWin === null) {
    createMainApplicationWindow();
  }
});

ipcMain.on("unsaved-changes", async (_event, res) => {
  if (!res) mainCortadoWin.destroy();
  else {
    const { response } = await dialog.showMessageBox(mainCortadoWin, {
      type: "warning",
      title: "Save Project?",
      message: "Save Cortado project before closing?",
      detail: "All progress will be lost if you don't save it.",
      buttons: ["Don't Save", "Cancel", "Save"],
      defaultId: 2,
    });

    if (response === 0) mainCortadoWin.destroy();
    else if (response === 2) {
      mainCortadoWin.webContents.send("save-project");
    }
  }
});

ipcMain.on("saveToUserFolder", (_, fileName, fileExtension, data) =>
  saveToUserFolder(app.getPath("userData"), fileName, fileExtension, data)
);

ipcMain.handle("readFromUserFolder", (_, fileName, fileExtension) =>
  readFromUserFolder(app.getPath("userData"), fileName, fileExtension)
);

ipcMain.handle("getWSPort", (_) => {
  return WS_PORT;
});

ipcMain.on("quit", () => {
  mainCortadoWin.destroy();
});
