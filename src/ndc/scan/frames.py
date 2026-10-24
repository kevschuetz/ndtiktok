"""Frame sampling + one contact sheet per account (D-17, D-21).

The contact sheet is what the in-session executor looks at to judge face/faceless, format,
visible speaker and on-screen citations. Frames are labelled with their video id.
"""

from pathlib import Path

from PIL import Image, ImageDraw


def sample_frames(path: str | Path, n: int = 2) -> list[Image.Image]:
    """n frames evenly spaced through the video (PyAV seek, first frame after each point)."""
    import av  # analyze extra; imported lazily

    out: list[Image.Image] = []
    with av.open(str(path)) as container:
        if not container.streams.video:
            return out
        stream = container.streams.video[0]
        duration = None
        if stream.duration and stream.time_base:
            duration = float(stream.duration * stream.time_base)
        elif container.duration:
            duration = container.duration / 1_000_000
        if not duration:
            for frame in container.decode(video=0):
                out.append(frame.to_image())
                if len(out) >= n:
                    break
            return out
        for i in range(n):
            target = duration * (i + 1) / (n + 1)
            container.seek(int(target / stream.time_base), stream=stream, any_frame=False)
            for frame in container.decode(video=0):
                if frame.time is None or frame.time >= target - 0.5:
                    out.append(frame.to_image())
                    break
    return out


def compose_contact_sheet(
    frames: list[tuple[str, Image.Image]], out_path: str | Path, width: int = 1024, cols: int = 3
) -> Path | None:
    """Grid of labelled frames, saved as JPEG. Returns None when there are no frames."""
    if not frames:
        return None
    cols = max(1, min(cols, len(frames)))
    rows = -(-len(frames) // cols)
    cell_w = width // cols
    thumbs = []
    for label, img in frames:
        img = img.convert("RGB")
        h = max(1, round(img.height * cell_w / img.width))
        thumbs.append((label, img.resize((cell_w, h))))
    label_h = 18
    cell_h = max(t.height for _, t in thumbs) + label_h
    sheet = Image.new("RGB", (cell_w * cols, cell_h * rows), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (label, thumb) in enumerate(thumbs):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        draw.text((x + 4, y + 2), label[:60], fill="black")
        sheet.paste(thumb, (x, y + label_h))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, "JPEG", quality=85)
    return out_path
