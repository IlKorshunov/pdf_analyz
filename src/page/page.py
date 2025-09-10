import fitz
from typing import Tuple, Dict, Any, List, Optional
from page.extractors import TextExtractor, TableExtractor, LinkExtractor, ImageExtractor, TitleExtractor
from page.layout_analyzer import LayoutAnalyzer
import os

class Page:
    def __init__(self, pdf_path: str, page: "fitz.Page"):
        self.pdf_path = pdf_path
        self.page = page
        self._text_extractor = TextExtractor(page)
        self._table_extractor = TableExtractor(page)
        self._link_extractor = LinkExtractor(page)
        self._image_extractor = ImageExtractor(page)
        self._title_extractor = TitleExtractor(page)
        self._layout_analyzer = None

    def text_dict(self) -> Dict[str, Any]:
        """Получить текст страницы в виде словаря."""
        return self._text_extractor.get_text_dict()

    def tables(self) -> Tuple[List[List[List[str]]], List[fitz.Rect]]:
        """Получить таблицы и их bbox."""
        return self._table_extractor.extract_tables()

    def text_blocks(self) -> List[Dict[str, Any]]:
        """Получить структурированные текстовые блоки."""
        _, table_bboxes = self.tables()
        return self._text_extractor.get_structured_blocks(table_bboxes)

    def links(self) -> List[Dict[str, Any]]:
        """Получить все ссылки со страницы."""
        text_dict = self.text_dict()
        return self._link_extractor.extract_links(text_dict)

    def images(self, out_dir: str = "images") -> List[Dict[str, Any]]:
        """Получить все изображения со страницы."""
        return self._image_extractor.extract_images(out_dir)

    def captions(self) -> List[Dict[str, Any]]:
        """Получить подписи к изображениям."""
        return self._image_extractor.extract_captions()

    def titles(self) -> List[Dict[str, Any]]:
        """Извлечь заголовки со страницы (если это оглавление)."""
        return self._title_extractor.extract_titles()

    def is_toc_page(self) -> bool:
        """Проверить, является ли страница оглавлением."""
        return self._title_extractor.is_toc_page()

    @classmethod
    def get_all_titles(cls, pdf_path: str) -> List[Dict[str, Any]]:
        """Получить все заголовки из документа."""
        return TitleExtractor.get_all_titles(pdf_path)

    def as_dict(self, images_dir: str = "images") -> Dict[str, Any]:
        """Получить все данные страницы в виде словаря."""
        tables_data, _ = self.tables()
        return {
            "page_number": self.page.number,
            "text_blocks": self.text_blocks(),
            "tables": tables_data,
            "links": self.links(),
            "image_captions": self.captions(),
            "images": self.images(out_dir=images_dir),
        }

    def analyze_page(self, doc: fitz.Document, images_dir: str = "images", *, resolved: bool = False, vis_images: Optional[List] = None, weights_dir: str = "weights") -> Dict[str, Any]:
        """Анализ страницы с выбором режима через флаг resolved."""
        tables_data, _ = self.tables()
        result = {
            "page_number": self.page.number,
            "tables": tables_data,
            "image_captions": self.captions(),
            "images": self.images(images_dir),
            "links": self.links(),
        }
        
        if resolved:
            if self._layout_analyzer is None:
                self._layout_analyzer = LayoutAnalyzer(weights_dir=weights_dir)
            blocks, vis_img = self._layout_analyzer.analyze_page_with_resolved_layout(
                self.pdf_path, page_number=self.page.number
            )
            os.makedirs(images_dir, exist_ok=True)
            
            if vis_images is not None and vis_img is not None:
                try:
                    img = vis_img if vis_img.mode == "RGB" else vis_img.convert("RGB")
                    vis_images.append(img)
                except Exception:
                    pass

            result.update({
                "resolved_blocks": blocks,
                "annotated_image_path": "",
            })
        else:
            result["text_blocks"] = self.text_blocks()
        
        return result

    def clear_cache(self) -> None:
        self._text_extractor._text_dict = None
        self._text_extractor._clear_text_blocks = None
        self._text_extractor._structured_blocks = None
        self._table_extractor._tables_data = None
        self._table_extractor._tables_bboxes = None
        self._link_extractor._links = None
        self._image_extractor._images = None
        self._image_extractor._captions = None