# -*- mode: python ; coding: utf-8 -*-

# PyInstaller's package hooks collect the runtime files needed by numpy,
# pandas, Pillow, python-docx and pywebview. Avoid collect_all(): it also
# bundled tests, notebooks, plotting stacks and optional data backends.

a = Analysis(
    ['main_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('index.html',            '.'),
        ('styles.css',            '.'),
        ('backend.py',            '.'),
        ('bi_server.py',          '.'),
        ('pbix_analysis.py',      '.'),
        ('tmdl_analysis.py',      '.'),
        ('doc_export.py',         '.'),
        ('render_graphics.py',    '.'),
        ('logging_setup.py',      '.'),
        ('connector_matching.py', '.'),
        ('graph_utils.py',        '.'),
        ('connector_catalog.py',  '.'),
        ('image',                 'image'),
        ('assets',                'assets'),
        ('src',                   'src'),
    ],
    hiddenimports=[
        # Imports below are lazy at runtime or selected dynamically by pywebview.
        'pbixray',
        'docx',
        'docx.oxml',
        'docx.oxml.ns',
        'docx.shared',
        'docx.enum.text',
        'docx.enum.table',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'clr',
        'System',
        'System.Windows.Forms',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Optional stacks not used by BI Flow Mapper.
        'IPython',
        'jupyter',
        'matplotlib',
        'notebook',
        'openpyxl',
        'pandas.tests',
        'pyarrow',
        'pytest',
        'scipy',
        'tkinter',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BI Flow Mapper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX saves disk space but adds decompression and antivirus work on launch.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    # No cert available yet -- unsigned .exe triggers Windows SmartScreen.
    # Free-signing path researched (SignPath Foundation, OSS-eligible under
    # our MIT license) but requires a manual application by the project
    # owner; not yet submitted. See docs/CODE_SIGNING.md before changing
    # this. Windows Authenticode signing is applied post-build (signtool /
    # SignPath action on the .exe artifact), not via this PyInstaller field.
    codesign_identity=None,
    entitlements_file=None,
    icon=['image/icon.ico'],
)
