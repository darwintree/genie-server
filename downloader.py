import requests
from pydub import AudioSegment
import io
import os

def download_and_convert_m4a_to_ogg(url: str, output_filename: str):
    try:
        print(f"正在从 {url} 下载文件...")
        # 1. 发送请求获取音频数据
        response = requests.get(url, stream=True)
        response.raise_for_status()  # 检查请求是否成功

        # 将下载的内容读入内存二进制流
        m4a_data = io.BytesIO(response.content)

        print(f"正在转换格式为 OGG...")
        # 2. 使用 pydub 读取 M4A (ffmpeg 会在后台处理)
        audio = AudioSegment.from_file(m4a_data, format="m4a")

        # 3. 导出为 OGG
        # 可以通过 bitrate 参数指定比特率，例如 "192k"
        audio.export(output_filename, format="ogg")

        print(f"转换完成！文件已保存为: {output_filename}")

    except Exception as e:
        print(f"发生错误: {e}")
        raise
