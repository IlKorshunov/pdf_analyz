import os
import json
import fitz
from typing import List, Dict, Any, Optional
from PIL import Image
from page.page import Page


class Document:
    """Класс для работы с PDF документом."""
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._doc: Optional[fitz.Document] = None

    def analyze_document(self, images_dir: str = "images", *, resolved: bool = False, verbose: bool = False, weights_dir: str = "weights") -> List[Dict[str, Any]]:
        """Анализ всего документа с выбором режима через флаг resolved."""
        if self._doc is None:
            self._doc = fitz.open(self.pdf_path)

        if resolved:
            os.makedirs(images_dir, exist_ok=True)
        
        results: List[Dict[str, Any]] = []
        vis_images: List[Image.Image] = [] if resolved and verbose else []
        
        for page in self._doc:
            try:
                res = Page(self.pdf_path, page).analyze_page(self._doc, images_dir=images_dir, resolved=resolved, vis_images=vis_images if resolved and verbose else None, weights_dir=weights_dir)
                results.append(res)
            except Exception:
                continue

        if resolved and verbose and vis_images:
            pdf_out = os.path.join(images_dir, "resolved_annotated.pdf")
            try:
                first, rest = vis_images[0], vis_images[1:]
                first.save(pdf_out, "PDF", resolution=100.0, save_all=True, append_images=rest)
                for r in results: r["annotated_pdf_path"] = pdf_out
            except Exception:
                pass
        
        return results

    def analyze_and_save_json(self, output_path: str, images_dir: str = "images", *, resolved: bool = False, verbose: bool = False, weights_dir: str = "weights"):
        """Анализ документа и сохранение в JSON с выбором режима через флаг resolved."""
        results = self.analyze_document(images_dir=images_dir, resolved=resolved, verbose=verbose, weights_dir=weights_dir)
        
        if not resolved:
            for page_result in results:
                if "images" in page_result:
                    del page_result["images"]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)

    def __enter__(self):
        """Вход в контекстный менеджер."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера."""
        self.close()

    def close(self):
        """Закрыть документ."""
        if self._doc:
            self._doc.close()
            self._doc = None
