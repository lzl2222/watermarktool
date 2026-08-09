# -*- coding: utf-8 -*-
"""保存下载文件：Android 用 MediaStore 存入相册（小米可见）；桌面回退本地 downloads 目录"""
import os
import shutil

IS_ANDROID = False
try:
    import android  # python-for-android 提供
    IS_ANDROID = True
except Exception:
    pass


def _desktop_dir():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    os.makedirs(d, exist_ok=True)
    return d


def save_media(src_path, display_name, mime="image/jpeg", subdir="去水印"):
    """
    把 src_path 保存到相册/下载目录，返回最终路径或 content:// uri。
    - Android: MediaStore（Pictures/去水印），相册直接可见
    - 桌面:    本地 downloads/ 目录（便于 Windows 上开发调试）
    """
    if IS_ANDROID:
        return _save_android(src_path, display_name, mime, subdir)
    dst = os.path.join(_desktop_dir(), display_name)
    shutil.copy2(src_path, dst)
    return dst


def _save_android(src_path, display_name, mime, subdir):
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    MediaStore = autoclass("android.provider.MediaStore")
    ContentValues = autoclass("android.content.ContentValues")
    ctx = resolver = None
    ctx = PythonActivity.mActivity
    resolver = ctx.getContentResolver()

    is_image = mime.startswith("image/")
    collection = (MediaStore.Images.Media.EXTERNAL_CONTENT_URI
                  if is_image else MediaStore.Video.Media.EXTERNAL_CONTENT_URI)

    def build_values(pending):
        v = ContentValues()
        v.put("DISPLAY_NAME", display_name)
        v.put("MIME_TYPE", mime)
        try:
            v.put("RELATIVE_PATH", "Pictures/" + subdir)  # API 29+
        except Exception:
            pass
        if pending:
            try:
                v.put("IS_PENDING", 1)
            except Exception:
                pass
        return v

    uri = None
    try:
        uri = resolver.insert(collection, build_values(True))
    except Exception:
        uri = resolver.insert(collection, build_values(False))
    if uri is None:
        raise RuntimeError("保存到相册失败")

    out = resolver.openOutputStream(uri)
    try:
        with open(src_path, "rb") as f:
            shutil.copyfileobj(f, out)
    finally:
        out.close()
    # 清除 pending 标记，让文件立即可见
    try:
        v = ContentValues()
        v.put("IS_PENDING", 0)
        resolver.update(uri, v, None, None)
    except Exception:
        pass
    return str(uri)
