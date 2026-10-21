#!/bin/sh

cd ./../src/backend
pip install -r requirements.txt
python3 -O -m PyInstaller --noconfirm --clean cortado-backend.spec

cd ./../frontend
npm install
npm run build-prod
npm run build-electron-linux
