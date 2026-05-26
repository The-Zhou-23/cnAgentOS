@echo off
echo Downloading static files...

set BASE=app\static\dist

if not exist "%BASE%" mkdir "%BASE%"

echo [1] Bootstrap CSS...
if not exist "%BASE%\bootstrap-5.3.8-dist\css" mkdir "%BASE%\bootstrap-5.3.8-dist\css"
if not exist "%BASE%\bootstrap-5.3.8-dist\css\bootstrap.min.css" (
    powershell -Command "Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css' -OutFile 'app\static\dist\bootstrap-5.3.8-dist\css\bootstrap.min.css'"
)

echo [2] Bootstrap JS...
if not exist "%BASE%\bootstrap-5.3.8-dist\js" mkdir "%BASE%\bootstrap-5.3.8-dist\js"
if not exist "%BASE%\bootstrap-5.3.8-dist\js\bootstrap.bundle.min.js" (
    powershell -Command "Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js' -OutFile 'app\static\dist\bootstrap-5.3.8-dist\js\bootstrap.bundle.min.js'"
)

echo [3] Font Awesome...
if not exist "%BASE%\fontawesome-free-5.15.4-web\css" mkdir "%BASE%\fontawesome-free-5.15.4-web\css"
if not exist "%BASE%\fontawesome-free-5.15.4-web\css\all.min.css" (
    powershell -Command "Invoke-WebRequest -Uri 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css' -OutFile 'app\static\dist\fontawesome-free-5.15.4-web\css\all.min.css'"
)

echo [4] Layui CSS...
if not exist "%BASE%\layui-v2.13.6\css" mkdir "%BASE%\layui-v2.13.6\css"
if not exist "%BASE%\layui-v2.13.6\css\layui.css" (
    powershell -Command "Invoke-WebRequest -Uri 'https://unpkg.com/layui@2.13.6/dist/css/layui.css' -OutFile 'app\static\dist\layui-v2.13.6\css\layui.css'"
)

echo [5] Layui JS...
if not exist "%BASE%\layui-v2.13.6\layui.js" (
    powershell -Command "Invoke-WebRequest -Uri 'https://unpkg.com/layui@2.13.6/dist/layui.js' -OutFile 'app\static\dist\layui-v2.13.6\layui.js'"
)

echo Done!
pause
