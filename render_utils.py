from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover
    raise ImportError("render_utils.py requires PyMuPDF. Install with: pip install pymupdf") from exc

RGB = Tuple[float, float, float]
RectLike = Union[fitz.Rect, Sequence[float], Tuple[float, float, float, float]]


@dataclass(frozen=True)
class Stamp:
    page: int
    kind: str  # "x" or "text"
    rect: Tuple[float, float, float, float]
    text: str = ""
    color: RGB = (0.0, 0.0, 0.0)
    font_size: float = 10.0
    align: str = "left"
    line_width: float = 1.5
    padding: float = 2.5


def _to_rect(value: RectLike) -> fitz.Rect:
    if isinstance(value, fitz.Rect):
        return value
    if len(value) != 4:
        raise ValueError(f"Rect must have 4 values, got {value!r}")
    x0, y0, x1, y1 = value
    return fitz.Rect(float(x0), float(y0), float(x1), float(y1))


def _normalize_color(color: Optional[Sequence[float]]) -> RGB:
    if color is None:
        return (0.0, 0.0, 0.0)
    if len(color) != 3:
        raise ValueError(f"Color must be RGB, got {color!r}")
    return (float(color[0]), float(color[1]), float(color[2]))


def open_pdf(path: Union[str, Path]) -> fitz.Document:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return fitz.open(pdf_path)


def draw_x_mark(
    page: fitz.Page,
    rect: RectLike,
    *,
    color: RGB = (0.0, 0.0, 0.0),
    line_width: float = 1.6,
    padding: float = 2.5,
) -> None:
    r = _to_rect(rect)
    c = _normalize_color(color)
    x0 = r.x0 + padding
    y0 = r.y0 + padding
    x1 = r.x1 - padding
    y1 = r.y1 - padding

    page.draw_line((x0, y0), (x1, y1), color=c, width=line_width)
    page.draw_line((x0, y1), (x1, y0), color=c, width=line_width)


def draw_text(
    page: fitz.Page,
    rect: RectLike,
    text: str,
    *,
    color: RGB = (0.0, 0.0, 0.0),
    font_size: float = 10.0,
    align: str = "left",
    font_name: str = "helv",
) -> None:
    r = _to_rect(rect)
    c = _normalize_color(color)
    align_map = {"left": 0, "center": 1, "right": 2}
    if align not in align_map:
        raise ValueError(f"Unsupported alignment: {align}")
    page.insert_textbox(
        r,
        text,
        fontname=font_name,
        fontsize=font_size,
        color=c,
        align=align_map[align],
    )


def stamp_pdf(
    template_pdf: Union[str, Path],
    output_pdf: Union[str, Path],
    stamps: Iterable[Stamp],
    *,
    flatten: bool = True,
    garbage: int = 4,
    deflate: bool = True,
) -> Path:
    template_path = Path(template_pdf)
    output_path = Path(output_pdf)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = open_pdf(template_path)
    try:
        for stamp in stamps:
            if stamp.page < 0 or stamp.page >= doc.page_count:
                raise IndexError(
                    f"Stamp page {stamp.page} is outside document page range 0-{doc.page_count - 1}"
                )
            page = doc[stamp.page]
            if stamp.kind.lower() == "x":
                draw_x_mark(
                    page,
                    stamp.rect,
                    color=stamp.color,
                    line_width=stamp.line_width,
                    padding=stamp.padding,
                )
            elif stamp.kind.lower() == "text":
                draw_text(
                    page,
                    stamp.rect,
                    stamp.text,
                    color=stamp.color,
                    font_size=stamp.font_size,
                    align=stamp.align,
                )
            else:
                raise ValueError(f"Unsupported stamp kind: {stamp.kind!r}")

        save_kwargs = dict(garbage=garbage, deflate=deflate)
        if flatten:
            save_kwargs.update(clean=True)
        doc.save(output_path, **save_kwargs)
        return output_path
    finally:
        doc.close()


def merge_pdfs(
    pdf_paths: Iterable[Union[str, Path]],
    output_pdf: Union[str, Path],
) -> Path:
    output_path = Path(output_pdf)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    merged = fitz.open()
    try:
        for path in pdf_paths:
            source = open_pdf(path)
            try:
                merged.insert_pdf(source)
            finally:
                source.close()
        merged.save(output_path, garbage=4, deflate=True)
        return output_path
    finally:
        merged.close()


def render_stamps_from_dicts(
    template_pdf: Union[str, Path],
    output_pdf: Union[str, Path],
    stamp_dicts: Iterable[dict],
    *,
    flatten: bool = True,
) -> Path:
    stamps: List[Stamp] = []
    for item in stamp_dicts:
        stamps.append(
            Stamp(
                page=int(item["page"]),
                kind=str(item["kind"]),
                rect=tuple(float(v) for v in item["rect"]),
                text=str(item.get("text", "")),
                color=_normalize_color(item.get("color")),
                font_size=float(item.get("font_size", 10.0)),
                align=str(item.get("align", "left")),
                line_width=float(item.get("line_width", 1.5)),
                padding=float(item.get("padding", 2.5)),
            )
        )
    return stamp_pdf(template_pdf, output_pdf, stamps, flatten=flatten)


__all__ = [
    "Stamp",
    "open_pdf",
    "draw_x_mark",
    "draw_text",
    "stamp_pdf",
    "merge_pdfs",
    "render_stamps_from_dicts",
]
