"""サムネイル生成（FFmpegフレーム切り出し + Pillowテキスト合成）"""

import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont


def extract_frame(video_path: str) -> str:
    """動画の中間地点からフレームを1枚切り出す。

    Returns:
        切り出した画像の一時ファイルパス（JPEG）
    """
    # 開始10秒のフレームを切り出し
    seek_sec = 10.0

    output = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    output_path = output.name
    output.close()

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(seek_sec),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpegフレーム切り出しエラー:\n{result.stderr}")

    return output_path


def add_text_to_image(
    image_path: str,
    text: str,
    font_file: str,
    font_size: int = 80,
    font_color: str = "red",
    stroke_color: str = "black",
    stroke_width: int = 8,
) -> str:
    """画像にテキストを合成する。

    テキストは画像中央に配置。赤文字に黒縁取り。サイズは画像幅の70%に自動調整。

    Returns:
        テキスト合成済み画像の一時ファイルパス（JPEG）
    """
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # 画像幅の95%に収まるようフォントサイズを自動計算
    target_width = img.width * 0.95
    font_size = 500  # 大きめから開始して縮小
    while font_size > 10:
        font = ImageFont.truetype(font_file, font_size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        text_width = bbox[2] - bbox[0]
        if text_width <= target_width:
            break
        font_size -= 5

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # 画像中央に配置
    x = (img.width - text_width) / 2
    y = (img.height - text_height) / 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill=font_color,
        stroke_fill=stroke_color,
        stroke_width=stroke_width,
    )

    output = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    output_path = output.name
    output.close()

    img.save(output_path, "JPEG", quality=95)
    return output_path


def generate_thumbnail(
    video_path: str,
    text: str,
    font_file: str,
    font_size: int = 200,
    font_color: str = "red",
    stroke_color: str = "black",
    stroke_width: int = 8,
) -> str:
    """動画からサムネイルを生成する（フレーム切り出し + テキスト合成）。

    Returns:
        サムネイル画像の一時ファイルパス（JPEG）
    """
    frame_path = extract_frame(video_path)
    thumbnail_path = add_text_to_image(
        frame_path,
        text,
        font_file=font_file,
        font_size=font_size,
        font_color=font_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
    )

    # 中間フレームを削除
    import os
    os.unlink(frame_path)

    return thumbnail_path


def _get_duration(video_path: str) -> float:
    """動画の長さ（秒）を取得する"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe エラー:\n{result.stderr}")
    return float(result.stdout.strip())
