import os
import subprocess
import requests
import imageio_ffmpeg

def download_video(url, output_path, progress_callback=None):
    """
    下载视频文件，并通过回调函数报告进度
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"无法下载视频，HTTP状态码: {response.status_code}")
        
    total_size = int(response.headers.get('content-length', 0))
    downloaded_size = 0
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)
                downloaded_size += len(chunk)
                if progress_callback and total_size > 0:
                    percent = int((downloaded_size / total_size) * 100)
                    progress_callback(percent)
                    
    if progress_callback:
        progress_callback(100)

def remove_watermark(input_path, output_path, width, height):
    """
    使用 FFmpeg delogo 滤镜对视频中的左上角和右下角水印进行模糊处理，并保留原音轨
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # 动态计算水印模糊区域坐标 (基于主流的 280x50 水印大小，四周外边距分别为左右 40，上下 30)
    w = width if (width and width > 0) else 720
    h = height if (height and height > 0) else 1280
    
    tl_x, tl_y = 40, 30
    tl_w, tl_h = 280, 50
    
    br_w, br_h = 280, 50
    br_x = max(0, w - br_w - 40)
    br_y = max(0, h - br_h - 30)
    
    filter_str = f"delogo=x={tl_x}:y={tl_y}:w={tl_w}:h={tl_h},delogo=x={br_x}:y={br_y}:w={br_w}:h={br_h}"
    
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", input_path,
        "-vf", filter_str,
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        output_path
    ]
    
    # 执行 FFmpeg 命令
    process = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    
    if process.returncode != 0:
        error_msg = process.stderr.decode('utf-8', errors='ignore')
        raise RuntimeError(f"FFmpeg 转换失败:\n{error_msg}")
        
    return output_path
