!macro customInstall
  File /oname=$PLUGINSDIR\VC_redist.x64.exe "${BUILD_RESOURCES_DIR}\VC_redist.x64.exe"
  ExecWait "$PLUGINSDIR\VC_redist.x64.exe"
!macroend
