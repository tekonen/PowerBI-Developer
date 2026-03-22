"""Video/recording frame extractor.

Uses OpenCV to extract key frames from screen recordings via scene change
detection, then sends frames to Claude vision for dashboard layout interpretation.
"""

from __future__ import annotations

from pathlib import Path

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


def extract_key_frames(
    video_path: Path,
    *,
    max_frames: int = 10,
    min_scene_change: float = 30.0,
) -> list[bytes]:
    """Extract key frames from a video using scene change detection.

    Uses histogram comparison between consecutive frames to detect significant
    visual changes (scene transitions).

    Args:
        video_path: Path to the video file.
        max_frames: Maximum number of frames to extract.
        min_scene_change: Minimum histogram difference to trigger a scene change (0-100).

    Returns:
        List of frame images as PNG bytes.
    """
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    logger.info(f"Video: {total_frames} frames, {fps:.1f} fps, {total_frames / fps:.1f}s")

    frames: list[bytes] = []
    prev_hist = None

    # Sample every N frames based on video length
    sample_interval = max(1, total_frames // (max_frames * 10))

    frame_idx = 0
    while cap.isOpened() and len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_interval == 0:
            # Convert to grayscale and compute histogram
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            cv2.normalize(hist, hist)

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                if diff > min_scene_change:
                    png_bytes = _frame_to_png(frame)
                    frames.append(png_bytes)
                    timestamp = frame_idx / fps
                    logger.info(f"Key frame at {timestamp:.1f}s (diff={diff:.1f})")
            else:
                # Always capture first frame
                frames.append(_frame_to_png(frame))

            prev_hist = hist

        frame_idx += 1

    cap.release()

    # If we got too few frames, fall back to uniform sampling
    if len(frames) < 3 and total_frames > 0:
        logger.info("Few scene changes detected, falling back to uniform sampling")
        frames = _uniform_sample(video_path, max_frames)

    logger.info(f"Extracted {len(frames)} key frames")
    return frames


def _frame_to_png(frame) -> bytes:
    """Convert an OpenCV frame to PNG bytes."""
    import cv2

    success, buf = cv2.imencode(".png", frame)
    if not success:
        raise RuntimeError("Failed to encode frame as PNG")
    return buf.tobytes()


def _uniform_sample(video_path: Path, num_frames: int) -> list[bytes]:
    """Uniformly sample frames from a video."""
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = max(1, total // num_frames)

    frames = []
    for i in range(0, total, interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            frames.append(_frame_to_png(frame))
        if len(frames) >= num_frames:
            break

    cap.release()
    return frames
