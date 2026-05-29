# mt5_signals.spec
# Arquivo de configuração do PyInstaller
# Execute com: pyinstaller mt5_signals.spec

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('templates', 'templates'),
]

hiddenimports = [
    # Flask
    'flask',
    'flask_cors',
    'jinja2',
    'jinja2.ext',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.debug',
    'click',
    # MetaTrader5 + numpy (MT5 depende do numpy internamente)
    'MetaTrader5',
    'numpy',
    'numpy._core',
    'numpy._core.multiarray',
    'numpy._core._multiarray_umath',
    'numpy._core._multiarray_tests',
    'numpy._core.numeric',
    'numpy._core._dtype',
    'numpy._core._methods',
    'numpy.core',
    'numpy.core.multiarray',
    'numpy.core._multiarray_umath',
    'numpy.core.numeric',
    # Pandas
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs',
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.timezones',
    'pandas._libs.tslibs.timestamps',
    'pandas._libs.interval',
    'pandas._libs.hashtable',
    'pandas._libs.index',
    'pandas._libs.lib',
    'pandas._libs.missing',
    'pandas._libs.reduction',
    'pandas._libs.tslib',
    'pandas._libs.writers',
    'pandas.io.formats.style',
    # Outros
    'pkg_resources.py2_compat',
    # System tray
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
]

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Apenas o que realmente não é usado
        'matplotlib',
        'scipy',
        'tkinter',
        'PyQt5',
        'wx',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MT5SignalAnalyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX desativado -- evita conflito com dlls do numpy
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # Sem janela preta de terminal
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',
)
