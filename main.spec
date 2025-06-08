# main.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],  # ⬅️ UPDATED main script name
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),                 
        ('playwright-browsers', 'playwright-browsers'),  # Chromium binaries
    ],
    hiddenimports=['playwright'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='facebook_automation',  # Final EXE name
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # set to False to hide the terminal
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='facebook_automation'
)
