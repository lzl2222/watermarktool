import os
import doubao_parser
import video_processor

def run_integration_test():
    test_url = "https://www.doubao.com/video-sharing?share_id=49700931634797570&source_type=mobile&video_id=v0369cg10004d98dbmaljht7f1umkktg&share_scene=video_viewer"
    
    print("=== 1. 开始解析链接 ===")
    info = doubao_parser.get_video_info(test_url)
    print("解析成功！")
    print(f"作者: {info['nickname']}")
    print(f"分辨率: {info['width']}x{info['height']}")
    print(f"CDN视频链接: {info['video_url'][:80]}...")
    
    print("\n=== 2. 开始下载视频 ===")
    temp_original = "temp_test_original.mp4"
    if os.path.exists(temp_original):
        os.remove(temp_original)
        
    def progress_cb(percent):
        print(f"下载进度: {percent}%", end="\r")
        
    video_processor.download_video(info["video_url"], temp_original, progress_callback=progress_cb)
    print("\n下载完成！文件大小:", os.path.getsize(temp_original))
    
    print("\n=== 3. 开始本地去水印 ===")
    final_output = "doubao_test_no_watermark.mp4"
    if os.path.exists(final_output):
        os.remove(final_output)
        
    processed_path = video_processor.remove_watermark(
        temp_original,
        final_output,
        info["width"],
        info["height"]
    )
    print("去水印完成！")
    print("输出文件:", processed_path)
    print("输出大小:", os.path.getsize(final_output))
    
    # 清理临时文件
    if os.path.exists(temp_original):
        os.remove(temp_original)
        
    # 验证输出文件有效性
    if os.path.exists(final_output) and os.path.getsize(final_output) > 0:
        print("\n=== 集成测试通过！ ===")
        # 清理测试输出
        os.remove(final_output)
    else:
        print("\n=== 集成测试失败！ ===")
        exit(1)

if __name__ == "__main__":
    run_integration_test()
