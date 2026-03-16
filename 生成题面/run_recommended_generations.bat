@echo off
setlocal

pushd "%~dp0"

set "SOURCE_DIR=..\finiteness_verification\output\phase1\voted_with_transform"

python main.py --source-dir "%SOURCE_DIR%" --problem-ids CF103D --variants 1 --theme cyber_city --seed 103
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids CF1257D --variants 1 --theme interstellar_logistics --seed 107
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids CF1461E --variants 1 --theme cyber_city --seed 309
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids CF1601C --variants 1 --theme campus_ops --seed 1786
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids CF1687C --variants 1 --theme arcane_lab --seed 254
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids CF1799D2 --variants 1 --theme cyber_city --seed 176
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids P7312 --variants 1 --theme interstellar_logistics --seed 120
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids GYM105472B --variants 1 --theme interstellar_logistics --seed 2
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids P8156 --variants 1 --theme arcane_lab --seed 7
if errorlevel 1 goto :fail

python main.py --source-dir "%SOURCE_DIR%" --problem-ids P2967 --variants 1 --theme campus_ops --seed 27
if errorlevel 1 goto :fail

popd
echo All generation commands completed successfully.
exit /b 0

:fail
set "EXIT_CODE=%ERRORLEVEL%"
popd
echo Generation stopped with error code %EXIT_CODE%.
exit /b %EXIT_CODE%
