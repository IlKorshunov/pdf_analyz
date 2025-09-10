import io
import os
import fitz
import re
import string
import unicodedata
from typing import Tuple, Dict, Any, List, Optional, Iterable, Set
from PIL import Image
from config.model_config import _URL_RE, TOC_WORDS_RE, Appendix_WORDS_RE

BBox = Tuple[float, float, float, float]


def _normalize_toc_line(text: str) -> str:
    text = re.sub(r"[.]{2,}", " ", text)  
    text = re.sub(r'(?<=\d)\s*\.\s*(?=\d)', '.', text) 
    text = re.sub(r'(?<=\d)\s*\.(?=\s)', '.', text)        
    return re.sub(r"\s+", " ", text).strip()

class TextExtractor:
    """Извлечение и структурирование текста."""
    
    def __init__(self, page: "fitz.Page"):
        self.page = page
        self._text_dict: Optional[Dict[str, Any]] = None
        self._clear_text_blocks: Optional[List[Dict[str, Any]]] = None
        self._structured_blocks: Optional[List[Dict[str, Any]]] = None

    def get_text_dict(self, flags: int = fitz.TEXTFLAGS_SEARCH, minimal: bool = True) -> Dict[str, Any]:
        """Получить текст страницы в виде словаря.
        Пропускает пустые строки и строки, содержащие только пробелы.
        Пропускает номер страницы.
        Args:
            flags: Флаги для извлечения текста
            minimal: Если True, возвращает только основные метаданные
        """
        self._text_dict = self.page.get_text("dict", flags=flags)
        if minimal: return self._get_minimal_text_dict(self._text_dict)
        return self._text_dict


    def _get_minimal_text_dict(self, raw_dict: Dict) -> Dict:
        """Отфильтровать лишние метаданные."""
        minimal_blocks = []

        for block in raw_dict.get('blocks', []):
            minimal_block = {
                'type': block.get('type'),
                'bbox': block.get('bbox'),
                'lines': []
            }

            for line in block.get('lines', []):
                minimal_line = {
                    'bbox': line.get('bbox'),
                    'spans': []
                }
                for span in line.get('spans', []):
                    text = span.get('text', "")
                    if text.strip() == "":
                        continue
                    minimal_span = {
                        'text': text,
                        'font': span.get('font'),
                        'size': span.get('size'),
                        'color': span.get('color'),
                        'bbox': span.get('bbox')
                    }
                    minimal_line['spans'].append(minimal_span)

                if not minimal_line['spans']:
                    continue

                first_text = minimal_line['spans'][0]['text'].strip()
                last_text = minimal_line['spans'][-1]['text'].strip()
                if re.fullmatch(r"\d+", first_text) or re.fullmatch(r"\d+", last_text):
                    continue

                minimal_block['lines'].append(minimal_line)

            if not minimal_block['lines']:
                continue
            minimal_blocks.append(minimal_block)

        return {'blocks': minimal_blocks}


    def get_clear_text_blocks(self, table_bboxes: List[fitz.Rect]) -> List[Dict[str, Any]]:
        """Получить текстовые блоки, не пересекающиеся с таблицами."""
        if self._clear_text_blocks is None:
            text_dict = self.get_text_dict()
            self._clear_text_blocks = [
                b for b in text_dict.get("blocks", [])
                if "lines" in b and not any(fitz.Rect(b["bbox"]).intersects(tb) for tb in table_bboxes)
            ]
        return self._clear_text_blocks

    @staticmethod
    def need_space_between(prev_text: str, next_text: str) -> bool:
        """Определить, нужен ли пробел между текстами."""
        if not prev_text or not next_text:
            return False
        if prev_text[-1].isspace() or next_text[0].isspace():
            return False

        if prev_text[-1] in string.punctuation:
            return False
        if next_text[0] in string.punctuation:
            return False

        return True

    def _build_block_struct(self, b: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
        """Структурировать один текстовый блок: слить спаны в текст,
        корректно расставить пробелы и вернуть span-диапазоны."""
        block_bbox = list(b.get("bbox", []))   
        parts: list[str] = []
        spans_out: list[Dict[str, Any]] = []
        total_len = 0   

        for l in b.get("lines", []):
            line_bbox = list(l.get("bbox", []))

            for s in l.get("spans", []):
                raw = (s.get("text") or "").strip()
                if not raw:
                    continue

                need_space = False
                if parts:
                    prev_text = parts[-1]
                    need_space = self.need_space_between(prev_text, raw)   

                if need_space:
                    parts.append(" ")
                    total_len += 1   

                start_char = total_len
                parts.append(raw)
                total_len += len(raw)
                end_char = total_len

                spans_out.append({
                    "id": f"block_{idx}_span_{len(spans_out)}",
                    "text": raw,
                    "start_char": start_char,
                    "end_char": end_char,
                    "bbox": list(s.get("bbox", line_bbox)),
                    "font": s.get("font") or "",
                    "line_bbox": line_bbox,
                })

        if not spans_out:
            return None

        block_text = "".join(parts)
        return {
            "id": f"block_{idx}",
            "text": block_text,
            "bbox": block_bbox,
            "spans": spans_out,
        }


    def get_structured_blocks(self, table_bboxes: List[fitz.Rect]) -> List[Dict[str, Any]]:
        """Получить структурированные текстовые блоки."""
        if self._structured_blocks is None:
            clear_blocks = self.get_clear_text_blocks(table_bboxes)
            out: List[Dict[str, Any]] = []
            for i, b in enumerate(clear_blocks):
                built = self._build_block_struct(b, i)
                if built: out.append(built)
            self._structured_blocks = out
        return self._structured_blocks


class TableExtractor:
    """Извлечение таблиц."""
    
    def __init__(self, page: "fitz.Page"):
        self.page = page
        self._tables_data: Optional[List[List[List[str]]]] = None
        self._tables_bboxes: Optional[List[fitz.Rect]] = None

    def extract_tables(self) -> Tuple[List[List[List[str]]], List[fitz.Rect]]:
        """Найти и извлечь таблицы со страницы.
        Возвращает список строк ячеек каждой таблицы и их bbox.
        """
        if self._tables_data is None or self._tables_bboxes is None:
            found = self.page.find_tables()
            self._tables_data = [t.extract() for t in found]
            self._tables_bboxes = [fitz.Rect(t.bbox) for t in found]
        return self._tables_data, self._tables_bboxes


class LinkExtractor:
    """Извлечение ссылок."""
    def __init__(self, page: "fitz.Page"):
        self.page = page
        self._links: Optional[List[Dict[str, Any]]] = None

    @staticmethod
    def _clean_text(txt: str) -> str:
        """Очистить текст от управляющих символов."""
        return "".join(ch for ch in txt if unicodedata.category(ch)[0] != "C").strip()

    def _find_full_line_text_intersecting(self, text_dict: Dict[str, Any], bbox_link: BBox) -> Optional[str]:
        """Найти полный текст строки, пересекающейся с bbox ссылки."""
        rect_link = fitz.Rect(bbox_link)
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_bbox = fitz.Rect(line["bbox"])
                if line_bbox.intersects(rect_link):
                    return " ".join(
                        self._clean_text(span.get("text", "")).strip()
                        for span in line.get("spans", [])
                        if span.get("text")
                    )
        return None

    def _iter_link_annotations(self, text_dict: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """Итерировать по аннотациям ссылок на странице."""
        for lnk in self.page.get_links():
            uri = lnk.get("uri")
            if not uri:
                continue
            from_bbox = list(lnk["from"])
            full_text = self._find_full_line_text_intersecting(text_dict, from_bbox)
            yield {"text": full_text, "uri": uri, "bbox": from_bbox}

    def _iter_inline_urls(self, text_dict: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """Итерировать по встроенным URL в тексте."""
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                full_line_text = " ".join(s.get("text", "").strip() for s in line.get("spans", []) if s.get("text"))
                for span in line["spans"]:
                    span_text = span.get("text", "").strip()
                    if not span_text:
                        continue
                    m = _URL_RE.search(span_text)
                    if not m:
                        continue
                    bbox = list(fitz.Rect(span.get("bbox", line["bbox"])))
                    yield {"text": full_line_text, "uri": m.group(0), "bbox": bbox}

    def extract_links(self, text_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Извлечь все ссылки со страницы."""
        if self._links is None:
            out: List[Dict[str, Any]] = []
            out.extend(self._iter_link_annotations(text_dict))
            out.extend(self._iter_inline_urls(text_dict))
            self._links = out
        return self._links



class ImageExtractor:
    """Извлечение изображений."""
    
    CAPTION_MAX_DY_PT = 100
    
    def __init__(self, page: "fitz.Page"):
        self.page = page
        self._images: Optional[List[Dict[str, Any]]] = None
        self._captions: Optional[List[Dict[str, Any]]] = None

    def _iter_page_images(self) -> Iterable[Tuple[tuple, fitz.Rect]]:
        """Итерировать по изображениям на странице."""
        for img_info in self.page.get_images(full=True):
            bbox = fitz.Rect(self.page.get_image_bbox(img_info))
            if not bbox.is_empty:
                yield img_info, bbox

    def _get_image_bbox_maybe(self, img_info: tuple) -> Optional[List[float]]:
        """получить bbox изображения."""
        return list(fitz.Rect(self.page.get_image_bbox(img_info)))

    def _extract_image_bytes(self, doc: fitz.Document, xref: int) -> Optional[Tuple[bytes, str]]:
        """Извлечь байты изображения из документа."""
        info = doc.extract_image(xref)
        return info["image"], info.get("ext", "png")

    def _save_image_bytes(self, img_bytes: bytes, ext: str, out_dir: str, img_id: str) -> Optional[Tuple[str, int, int]]:
        """Сохранить байты изображения в файл."""
        im = Image.open(io.BytesIO(img_bytes))
        fname = f"{img_id}.{ext}"
        fpath = os.path.join(out_dir, fname)
        im.save(fpath)
        return fpath, im.width, im.height

    def _stable_image_id(self, xref: int, seen: Dict[int, int]) -> str:
        """Создать стабильный ID для изображения."""
        seen[xref] = seen.get(xref, 0) + 1
        suffix = "" if seen[xref] == 1 else f"_{seen[xref]}"
        return f"img_p{self.page.number}_{xref}{suffix}"

    def extract_images(self, out_dir: str = "images") -> List[Dict[str, Any]]:
        """Извлечь все изображения со страницы."""
        if self._images is None:
            os.makedirs(out_dir, exist_ok=True)
            results: List[Dict[str, Any]] = []
            seen: Dict[int, int] = {}
            doc = self.page.parent

            for img_info in self.page.get_images(full=True):
                xref = img_info[0]
                img_id = self._stable_image_id(xref, seen)
                bbox_list = self._get_image_bbox_maybe(img_info)

                data = self._extract_image_bytes(doc, xref)
                if not data:
                    continue
                img_bytes, ext = data

                saved = self._save_image_bytes(img_bytes, ext, out_dir, img_id)
                if not saved:
                    continue
                fpath, width, height = saved

                results.append({
                    "id": img_id,
                    "xref": xref,
                    "bbox": bbox_list,
                    "path": fpath,
                    "width": width,
                    "height": height,
                    "ext": ext,
                })
            self._images = results
        return self._images

    def _page_text_blocks_raw(self) -> List[Tuple[BBox, str]]:
        """Быстро получить список текстовых блоков страницы как (bbox, text)."""
        raw = self.page.get_text("blocks")
        out: List[Tuple[BBox, str]] = []
        for tb in raw:
            bbox = tuple(tb[:4])
            txt = (tb[4] or "").strip()
            out.append((bbox, txt))
        return out

    def _is_caption_for_image(self, text_bbox: fitz.Rect, img_bbox: fitz.Rect) -> bool:
        """Проверить, является ли текстовый блок подписью к изображению."""
        is_below = text_bbox.y0 > img_bbox.y1
        close_vertically = (text_bbox.y0 - img_bbox.y1) < self.CAPTION_MAX_DY_PT
        return is_below and close_vertically

    def _find_first_caption_below(self, img_bbox: fitz.Rect, all_text_blocks: List[Tuple[BBox, str]]) -> Optional[Tuple[BBox, str]]:
        """Найти первый текстовый блок, который выглядит подписью к изображению."""
        for bbox, text in all_text_blocks:
            if text and self._is_caption_for_image(fitz.Rect(bbox), img_bbox):
                return bbox, text
        return None

    def extract_captions(self) -> List[Dict[str, Any]]:
        """Найти подписи к изображениям."""
        if self._captions is None:
            captions = []
            all_text_blocks = self._page_text_blocks_raw()
            idx = 0
            for _, img_bbox in self._iter_page_images():
                found = self._find_first_caption_below(img_bbox, all_text_blocks)
                if not found:
                    continue
                caption_bbox, caption_text = found
                captions.append({
                    "id": f"cap_p{self.page.number}_{idx}",
                    "caption_text": caption_text,
                    "caption_bbox": list(caption_bbox),
                    "image_bbox": list(img_bbox),
                })
                idx += 1
            self._captions = captions
        return self._captions




class TitleExtractor:
    """Извлечение заголовков из оглавления."""
    def __init__(self, page: "fitz.Page"):
        self.page = page
        self.titles: List[str] = []
        self.titles_spans = []

    def _page_text_dict(self, flags: int = fitz.TEXTFLAGS_SEARCH) -> Dict[str, Any]:
        return self.page.get_text("dict", flags=flags)

    def is_toc_page(self) -> bool:
        txt = self.page.get_text("text") or ""
        if not txt:
            return False
        found = {m.group(1).lower() for m in TOC_WORDS_RE.finditer(txt)}
        return ("содержание" in found) and ("введение" in found)

    def collect_toc_candidates_on_page(self) -> None:
        """
        получить список огравлений
        """
        pages = [self.page]
        doc = self.page.parent
        nxt_idx = self.page.number + 1
        nxt = doc[nxt_idx]
        if Appendix_WORDS_RE.search(nxt.get_text("text") or ""):
            pages.append(nxt)

        def parse_page_lines(page) -> list[str]:
            lines: list[str] = []
            d = page.get_text("dict", flags=fitz.TEXTFLAGS_SEARCH)
            for block in d.get("blocks", []) or []:
                for line in block.get("lines", []) or []:
                    parts: list[str] = []
                    for s in line.get("spans", []) or []:
                        seg = (s.get("text") or "").strip()
                        if not seg:
                            continue
                        if parts and self.need_space_between(parts[-1], seg):
                            parts.append(" ")
                        parts.append(seg)
                    raw = "".join(parts)
                    if not raw or raw.strip().isdigit():
                        continue
                    lines.append(raw)
            return lines

        out: list[str] = []
        for p in pages:
            out.extend(parse_page_lines(p))

        merged: list[str] = []
        rx_num_only = re.compile(r"^\d+(?:\.\d+)*$")
        for s in out:
            if merged and rx_num_only.fullmatch(merged[-1]):
                merged[-1] = merged[-1] + " " + s
            else:
                merged.append(s)

        seen: set[str] = set()
        result: list[str] = []
        for s in merged:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                result.append(s)
        self.titles = result
        return 

