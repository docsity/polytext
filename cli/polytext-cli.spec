# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    # Elenco degli script di entry point
    ['__main__.py'],
    
    # Percorsi aggiuntivi dove cercare i moduli (equivalente a --paths)
    pathex=['/app'],
    
    # Eseguibili binari da includere (equivalente a --add-binary)
    binaries=[
        ('/usr/bin/ffmpeg', 'ffmpeg'),
        ('/usr/bin/ffprobe', 'ffmpeg')
    ],
    
    # File di dati da includere (equivalente a --add-data)
    # Usiamo la funzione helper di PyInstaller per trovare automaticamente i dati di 'magika'.
    # Questo è più robusto rispetto a un percorso hard-coded.
    datas=collect_data_files('magika', include_py_files=True),
    
    # Import nascosti che PyInstaller non rileva automaticamente (equivalente a --hidden-import)
    hiddenimports=['audioop'],
    
    # Hooks aggiuntivi da eseguire
    hookspath=[],
    
    # Hooks da escludere
    hooksconfig={},
    
    # Opzioni di runtime
    runtime_hooks=[],
    
    # Moduli da escludere
    excludes=[],
    
    # Nome dell'eseguibile (equivalente a --name)
    name='polytext-temp',
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='polytext-temp',
    debug=False, # Imposta a True per un debug dettagliato come con --debug=all
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # L'opzione --onefile è gestita qui
    onefile=True,
)