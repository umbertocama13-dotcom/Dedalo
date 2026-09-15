# PyInstaller specification of the Dedalo desktop app (Windows).
# Run by build.ps1:  pyinstaller --distpath packaging\windows\dist --workpath packaging\windows\build\pyinstaller dedalo.spec
#
# onedir build (a folder with Dedalo.exe), not onefile: a single exe would extract ~500 MB
# to a temporary folder at every start. The installer copies the folder once.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PACKAGING = Path(SPECPATH).resolve()  # noqa: F821 - SPECPATH is defined by PyInstaller
ROOT = PACKAGING.parents[1]
MODEL = "backend/models/sentence-bert-base-italian-xxl-uncased"

# Resources keep the repository layout: desktop/paths.py finds them the same way in both.
datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "database" / "sqlite" / "schema.sql"), "database/sqlite"),
    (str(ROOT / "database" / "seed_catalog.sql"), "database"),
    (str(ROOT / "database" / "sample_diagnostics.csv"), "database"),
    (str(ROOT / MODEL), MODEL),
]

analysis = Analysis(  # noqa: F821 - PyInstaller spec globals
    [str(ROOT / "backend" / "desktop" / "__main__.py")],
    pathex=[str(ROOT / "backend")],
    datas=datas,
    # uvicorn imports its protocol, loop and lifespan implementations by name at runtime,
    # so static analysis cannot find them.
    hiddenimports=collect_submodules("uvicorn"),
    # Development-only libraries: the desktop app uses ONNX Runtime and SQLite.
    excludes=["torch", "sentence_transformers", "transformers", "pymysql", "tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Dedalo",
    icon=str(PACKAGING / "build" / "dedalo.ico"),
    # No console window: output goes to %LOCALAPPDATA%\Dedalo\logs\dedalo.log.
    console=False,
    # UPX compression often triggers antivirus false positives.
    upx=False,
)

COLLECT(  # noqa: F821
    exe,
    analysis.binaries,
    analysis.datas,
    name="Dedalo",
    upx=False,
)
