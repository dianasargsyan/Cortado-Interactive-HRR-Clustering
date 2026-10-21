# PLEASE NOTE:
# run with admin rights and make sure the correct venv of python is activated

Write-Output Get-Location
$originalPath = (Get-Item .).FullName

Write-Output "BUILD BACKEND"
cd ./../src/backend
pip install -r requirements.txt
python -O -m PyInstaller --noconfirm --clean cortado-backend.spec

Write-Output "BUILD FRONTEND"
cd ./../frontend
npm install
Remove-Item -Recurse ./app-dist/
npm run build-prod
npm run build-electron-windows
Get-Location

Write-Output "OPEN WINDOWS EXPLORER"
Invoke-Item ./../frontend/app-dist/

Write-Output "RESET PATH"
cd $originalPath
