#!/bin/sh

cd ./../src/backend
pip3 install -r requirements.txt
pip3 uninstall -y cvxopt
pip3 uninstall -y pm4pycvxopt
python3 -O -m PyInstaller --noconfirm --clean cortado-backend-macos.spec

cd ./../frontend
npm install
npm run build-prod
npm run build-electron-macos
open ./app-dist
