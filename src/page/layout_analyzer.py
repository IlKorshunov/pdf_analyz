# pylint: disable=no-member
from typing import List, Tuple, Optional, Iterable, Dict, Any, Protocol
import fitz
import layoutparser as lp   
from pdf2image import convert_from_path
from PIL import Image
from layoutparser.elements import Layout, TextBlock, Rectangle  
from config.model_config import DEFAULT_DPI
from config.model_config import get_model_configs

class BoxProtocol(Protocol):
    @property
    def coordinates(self) -> Tuple[float, float, float, float]: ...
    score: float


class LayoutAnalyzer:
    """Единый класс для анализа layout'а PDF документов с resolved режимом."""
    
    def __init__(self, model_name: str = "prima", extra_config: Optional[List[str]] = None, weights_dir: str = "weights"):
        self.model_name = model_name
        self.extra_config = extra_config or []
        self.weights_dir = weights_dir
        self._model: Optional["lp.Detectron2LayoutModel"] = None

    def _get_model(self) -> "lp.Detectron2LayoutModel":
        """Ленивая инициализация модели."""
        if self._model is None:
            model_configs = get_model_configs(self.weights_dir)
            
            if self.model_name not in model_configs:
                raise ValueError(f"Unknown model name: {self.model_name}. Available: {list(model_configs.keys())}")
            cfg = model_configs[self.model_name]
            self._model = lp.models.Detectron2LayoutModel(
                config_path=cfg["config_path"],
                label_map=cfg["label_map"],
                extra_config=self.extra_config,
                model_path=cfg.get("weights_path")
            )
        return self._model

    
    def _box_area(self, b: BoxProtocol) -> float:
        x1, y1, x2, y2 = b.coordinates
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    def _contains(self, outer: BoxProtocol, inner: BoxProtocol, tol: int = 0) -> bool:
        ox1, oy1, ox2, oy2 = outer.coordinates
        ix1, iy1, ix2, iy2 = inner.coordinates
        return (ix1 >= ox1 - tol and iy1 >= oy1 - tol and ix2 <= ox2 + tol and iy2 <= oy2 + tol)

    def _iou(self, el1: BoxProtocol, el2: BoxProtocol) -> float:
        x11, y11, x12, y12 = el1.coordinates
        x21, y21, x22, y22 = el2.coordinates

        xi1, yi1 = max(x11, x21), max(y11, y21)
        xi2, yi2 = min(x12, x22), min(y12, y22)

        inter_w = max(0.0, xi2 - xi1)
        inter_h = max(0.0, yi2 - yi1)
        inter_area = inter_w * inter_h

        area1 = self._box_area(el1)
        area2 = self._box_area(el2)
        union_area = area1 + area2 - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def _containment_ratio(self, inner: BoxProtocol, outer: BoxProtocol) -> float:
        """Доля площади inner, покрытая пересечением с outer."""
        ix1, iy1, ix2, iy2 = inner.coordinates
        ox1, oy1, ox2, oy2 = outer.coordinates

        xi1, yi1 = max(ix1, ox1), max(iy1, oy1)
        xi2, yi2 = min(ix2, ox2), min(iy2, oy2)
        inter_area = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)

        inner_area = self._box_area(inner)
        return inter_area / inner_area if inner_area > 0 else 0.0

    def _sorted_by_score_then_area(self, boxes: Iterable[BoxProtocol]) -> List[BoxProtocol]:
        """Сортировка боксов по убыванию score и площади."""
        return sorted(boxes, key=lambda b: (-getattr(b, "score", 0.0), -self._box_area(b)))

    def _suppress_with_rules(self, selected: "Layout", candidate: BoxProtocol, 
                           *, const_thresh: float, iou_thresh: float, tol: int) -> bool:
        """Проверяет, нужно ли отбраковать кандидата из-за конфликтов."""
        for sel in selected:
            if (self._contains(sel, candidate, tol=tol) or self._containment_ratio(candidate, sel) >= const_thresh or self._iou(candidate, sel) >= iou_thresh): return True
        return False

    def _remove_superseded(self, selected: "Layout", keeper: BoxProtocol, 
                          *, const_thresh: float, iou_thresh: float, tol: int) -> "Layout":
        """Удаляет боксы, вытесненные новым keeper'ом."""
        remain = [sel for sel in selected if not self._conflict(keeper, sel, const_thresh=const_thresh, iou_thresh=iou_thresh, tol=tol)]
        return Layout(remain)

    
    def _render_pdf_pages(self, pdf_path: str, dpi: int = DEFAULT_DPI) -> List[Image.Image]:
        """Конвертирует все страницы PDF в список PIL.Image."""
        return convert_from_path(pdf_path, dpi=dpi, fmt="png")

    def _detect_on_image(self, page_img: Image.Image) -> "lp.Layout":
        """Детекция макета на одной странице-изображении."""
        model = self._get_model()
        return model.detect(page_img)

    def _filter_layout_by_score(self, layout: "Layout", score_threshold: float) -> "Layout":
        """Фильтрация боксов по минимальному значению score."""
        return Layout([b for b in layout if getattr(b, "score", 0.0) >= score_threshold])

    def _visualize_layout(self, image: Image.Image, layout: "Layout", box_width: int = 3) -> Image.Image:
        """Рисует прямоугольники боксов поверх изображения."""
        try:
            return lp.draw_box(image, layout, box_width=box_width)
        except AttributeError:
            return lp.visualization.draw_box(image, layout, box_width=box_width)

    
    def _hierarchical_filter(self, layout: "Layout", min_score: float = 0.2, 
                           const_tresh: float = 0.9, iou_thresh: float = 0.4, tol: int = 0) -> "Layout":
        """Иерархическая фильтрация перекрывающихся боксов."""
        candidates = [b for b in layout if getattr(b, "score", 0.0) >= min_score]
        candidates = self._sorted_by_score_then_area(candidates)

        selected = Layout()
        for box in candidates:
            if self._suppress_with_rules(selected, box, const_thresh=const_tresh, iou_thresh=iou_thresh, tol=tol):
                continue
            selected = self._remove_superseded(selected, box, const_thresh=const_tresh, iou_thresh=iou_thresh, tol=tol)
            selected.append(box)
        return selected

    
    def _rect_intersects(self, r1: Rectangle, r2: Rectangle) -> bool:
        """Проверяет пересечение двух прямоугольников."""
        xi1 = max(r1.x_1, r2.x_1)
        yi1 = max(r1.y_1, r2.y_1)
        xi2 = min(r1.x_2, r2.x_2)
        yi2 = min(r1.y_2, r2.y_2)
        return (xi2 - xi1) > 0 and (yi2 - yi1) > 0

    def _subtract_overlap(self, src: Rectangle, other: Rectangle) -> Optional[Rectangle]:
        """Вычитает перекрытие из исходного прямоугольника."""
        if not self._rect_intersects(src, other):
            return src
        if src.y_1 < other.y_1 < src.y_2:
            new_rect = Rectangle(src.x_1, src.y_1, src.x_2, other.y_1)
        else:
            new_rect = Rectangle(src.x_1, other.y_2, src.x_2, src.y_2)
        if (new_rect.x_2 - new_rect.x_1) <= 0 or (new_rect.y_2 - new_rect.y_1) <= 0:
            return None
        return new_rect

    def _resolve_overlaps(self, layout: "Layout") -> "Layout":
        """Разрешает перекрытия между блоками."""
        ordered = sorted(layout, key=lambda b: b.area)
        resolved: List[TextBlock] = []
        for blk in ordered:
            rect = blk.block
            for accepted in resolved:
                if self._rect_intersects(rect, accepted.block):
                    new_rect = self._subtract_overlap(rect, accepted.block)
                    if new_rect is None:
                        rect = None
                        break
                    rect = new_rect
            if rect is None:
                continue
            resolved.append(TextBlock(rect, type=blk.type, score=getattr(blk, "score", 0.0)))
        return Layout(resolved)

    def _rect_to_image_xy(self, rect: fitz.Rect, page_height_pt: float, scale: float) -> Tuple[float, float, float, float]:
        """Преобразование координат из PDF в изображение.
        это костыльно!!!
        """
        x1 = rect.x0 * scale
        y1 = (page_height_pt - rect.y1) * scale
        x2 = rect.x1 * scale
        y2 = (page_height_pt - rect.y0) * scale
        return x1, y1, x2, y2

    def _attach_text(self, blocks: List[Dict[str, Any]], page: "fitz.Page", scale: float) -> None:
        """Присоединяет текст к блокам layout'а."""
        page_h_pt = page.rect.height
        page_h_px = page_h_pt * scale

        def to_px_flipped(rect_pt: fitz.Rect) -> Rectangle:
            x1, y1, x2, y2 = self._rect_to_image_xy(rect_pt, page_h_pt, scale)
            return Rectangle(x1, page_h_px - y2, x2, page_h_px - y1)

        for blk in page.get_text("dict").get("blocks", []):
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    txt = (sp.get("text") or "").strip()
                    if not txt:
                        continue
                    span_rect_px = to_px_flipped(fitz.Rect(sp["bbox"]))
                    for target in blocks:
                        if self._rect_intersects(span_rect_px, Rectangle(*target["bbox_px"])):
                            target["text"] += txt + " "
                            break

    
    def analyze_page_hierarchical(self, pdf_path: str, page_number: int = 0, 
                                min_score: float = 0.2, const_tresh: float = 0.8, 
                                iou_thresh: float = 0.9, tol: int = 5) -> Tuple[Image.Image, "Layout"]:
        """Анализ одной страницы с иерархической фильтрацией перекрытий."""
        image = self._render_pdf_pages(pdf_path)[page_number]
        raw_layout = self._detect_on_image(image)
        filtered = self._hierarchical_filter(raw_layout, min_score=min_score, 
                                           const_tresh=const_tresh, iou_thresh=iou_thresh, tol=tol)
        vis = self._visualize_layout(image, filtered, box_width=3)
        return vis, filtered

    def analyze_page_with_resolved_text(self, pdf_path: str, page_number: int = 0, 
                                      min_score: float = 0.05, const_tresh: float = 0.8, 
                                      iou_thresh: float = 0.9, tol: int = 2) -> List[Dict[str, Any]]:
        """Анализ страницы с resolved текстом."""
        _, raw_layout = self.analyze_page_hierarchical(
            pdf_path, page_number=page_number, min_score=min_score, 
            const_tresh=const_tresh, iou_thresh=iou_thresh, tol=tol
        )
        resolved_layout = self._resolve_overlaps(raw_layout)

        blocks: List[Dict[str, Any]] = []
        for lb in resolved_layout:
            x1, y1, x2, y2 = lb.block.coordinates
            blocks.append({"text": "", "bbox_px": [x1, y1, x2, y2], "type": lb.type})

        doc = fitz.open(pdf_path)
        page = doc[page_number]
        scale = DEFAULT_DPI / 72.0
        self._attach_text(blocks, page, scale=scale)
        doc.close()
        return blocks

    def analyze_page_with_resolved_layout(self, pdf_path: str, page_number: int = 0, 
                                        min_score: float = 0.05, const_tresh: float = 0.8, 
                                        iou_thresh: float = 0.9, tol: int = 2) -> Tuple[List[Dict[str, Any]], Image.Image]:
        """Анализ страницы с resolved layout'ом и визуализацией."""
        blocks = self.analyze_page_with_resolved_text(
            pdf_path, page_number, min_score=min_score, 
            const_tresh=const_tresh, iou_thresh=iou_thresh, tol=tol
        )
        image = self._render_pdf_pages(pdf_path)[page_number]
        layout = Layout([TextBlock(Rectangle(*b["bbox_px"]), type=b["type"], text=b["text"]) for b in blocks])
        vis = self._visualize_layout(image, layout)
        return blocks, vis

    def analyze_pdf_simple(self, pdf_path: str, page_number: int = 0, 
                         score_threshold: float = 0.5) -> Tuple[Image.Image, "Layout"]:
        """Простой анализ одной страницы без иерархической фильтрации."""
        image = self._render_pdf_pages(pdf_path)[page_number]
        layout = self._detect_on_image(image)
        filtered = self._filter_layout_by_score(layout, score_threshold)
        vis = self._visualize_layout(image, filtered, box_width=3)
        return vis, filtered

    def save_annotated_pdf(self, vis_pages: List[Image.Image], output_path: str) -> None:
        """Сохраняет набор размеченных страниц как единый PDF."""
        if not vis_pages:
            raise ValueError("Empty list of pages")
        vis_pages[0].save(output_path, "PDF", resolution=100.0, save_all=True, append_images=vis_pages[1:])
