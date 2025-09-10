"""Утилиты для работы с PDF."""
import os
from typing import Tuple

import fitz


def rect_to_image_xy(rect: fitz.Rect, page_height_pt: float, 
                    scale: float) -> Tuple[float, float, float, float]:
    """
    Преобразование координат прямоугольника из PDF в изображение.
    
    Args:
        rect: Прямоугольник в координатах PDF.
        page_height_pt: Высота страницы в точках.
        scale: Масштаб преобразования.
        
    Returns:
        Кортеж координат (x1, y1, x2, y2) в координатах изображения.
    """
    x1 = rect.x0 * scale
    y1 = (page_height_pt - rect.y1) * scale
    x2 = rect.x1 * scale
    y2 = (page_height_pt - rect.y0) * scale
    return x1, y1, x2, y2


def save_pdf_page(src_dir: str, page_start: int, page_end: int,
                 out_dir: str, out_name: str) -> str:
    """
    Сохранить диапазон страниц из PDF в новый файл.
    
    Args:
        src_dir: Путь к исходному PDF файлу.
        page_start: Начальная страница (1-based).
        page_end: Конечная страница (1-based).
        out_dir: Директория для сохранения.
        out_name: Имя выходного файла.
        
    Returns:
        Путь к сохранённому файлу.
    """
    os.makedirs(out_dir, exist_ok=True)

    doc = fitz.open(src_dir)
    if page_start < 1 or page_end > len(doc) or page_start > page_end:
        raise ValueError("error in page_start or end")

    out_pdf = fitz.open()
    out_pdf.insert_pdf(doc, from_page=page_start, to_page=page_end)

    if not out_name.lower().endswith(".pdf"):
        out_name += ".pdf"
    out_path = os.path.join(out_dir, out_name)
    out_pdf.save(out_path)

    out_pdf.close()
    doc.close()

    return out_path