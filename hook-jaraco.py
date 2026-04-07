# PyInstaller hook for jaraco
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('jaraco')