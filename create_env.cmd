@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
  echo Install uv first: https://docs.astral.sh/uv/getting-started/installation/
  exit /b 1
)
uv venv --python 3.12 --allow-existing .venv
if errorlevel 1 exit /b 1
uv pip install --python .venv\Scripts\python.exe torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 exit /b 1
uv pip install --python .venv\Scripts\python.exe -r requirements.txt -r requirements_launcher.txt -r requirements_dev.txt
if errorlevel 1 exit /b 1
uv pip install --python .venv\Scripts\python.exe --no-deps "wevisone-vl @ git+https://github.com/Tencent/WeVisOne-VL.git@40f735b8daed437ece982db9718e9c9856f52a79" -e .
if errorlevel 1 exit /b 1
echo Environment ready. Download WeVisOne-VL-4B with .venv\Scripts\python tools\download_models.py
