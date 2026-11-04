@echo off
REM Find an interpreter rather than remembering one. The path Python was
REM installed to on the machine this was written on does not exist on anyone
REM else's, and a shortcut that points at it fails with a message about a
REM missing file rather than a missing Python.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -X utf8 "%~dp0ctx.py" %*
) else (
  python -X utf8 "%~dp0ctx.py" %*
)
