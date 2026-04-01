"""FFmpegによるBGM合成"""

import subprocess
import tempfile
from pathlib import Path


def mix_bgm(video_path: str, bgm_path: str, bgm_volume: float = 0.1) -> str:
    """動画にBGMをループ合成する。

    Args:
        video_path: 入力動画ファイルパス
        bgm_path: BGMファイルパス
        bgm_volume: BGM音量（0.0〜1.0）

    Returns:
        BGM合成済み動画の一時ファイルパス

    Raises:
        RuntimeError: FFmpegの実行に失敗した場合
    """
    suffix = Path(video_path).suffix
    output = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    output_path = output.name
    output.close()

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", bgm_path,
        "-filter_complex",
        f"[1:a]volume={bgm_volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first",
        "-c:v", "copy",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg BGM合成エラー:\n{result.stderr}")

    return output_path
