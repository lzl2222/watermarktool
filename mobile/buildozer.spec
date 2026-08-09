[app]
title = 去水印
package.name = watermarktool
package.domain = org.watermark
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,otf,md,txt
version = 0.1.0

requirements = python3,kivy==2.3.0,requests,pycryptodome,ffpyplayer

orientation = portrait
fullscreen = 0

# 小米手机 = arm64-v8a
android.archs = arm64-v8a
android.api = 34
android.minapi = 24
android.allow_backup = False
android.accept_sdk_license = True
android.entrypoint = main.py
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO
android.private_storage = True

[buildozer]
log_level = 2
warn_on_root = 1
