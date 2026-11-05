# Build with: .venv\Scripts\pyinstaller.exe Trojan-AI.spec
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("ddgs")

a = Analysis(
    ["backend_server.py"],
    pathex=["."],
    binaries=[],
    datas=["voice.py", "trojanassiastant.py"],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="trojan-backend", console=True)
