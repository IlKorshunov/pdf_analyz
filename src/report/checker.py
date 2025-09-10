import re
import fitz
from typing import Tuple, List, Dict, Any
from config.model_config import LETTER_PATTERN, NUMBER_PATTERN, SIMPLE_PATTERN, _E_RESOURCE_RE, _NUMBERED_PARAGRAPH_RE
from page.extractors import TitleExtractor

class Checker:
    def has_page_number(self, page: fitz.Page) -> Tuple[bool, int]:
        """Проверить наличие номера страницы."""
        page_texts = page.get_text("blocks")
        if not page_texts:
            return False, None

        for i in [0, -1]:
            text = page_texts[i][4].strip()
            if text.isdigit():
                return True, i
        return False, None

    def check_document_pages(self, pdf_path: str) -> bool:
        """Проверить номера страниц во всем документе."""
        doc = fitz.open(pdf_path)
        pages_with_numbers = 0
        count = 0
        flag = False
        all_pages = len(doc)
        for page in doc:
            if TitleExtractor(page).is_toc_page():
                flag = True
                all_pages -= page.number
            has_number, _ = self.has_page_number(page)
            if has_number:
                pages_with_numbers += 1
            if flag:
                count += 1

        doc.close()
        return count == all_pages

    def check_captions_under_images_page(self, page_json: Dict[str, Any]) -> Tuple[bool, int, int]:
        """Проверить подписи к изображениям на странице."""
        captions_count = len(page_json.get("image_captions", []))
        images_count = len(page_json.get("images", []))
        is_valid = captions_count == images_count
        return is_valid, captions_count, images_count

    def check_captions_under_images_doc(self, doc_json: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
        """Проверить подписи к изображениям во всем документе."""
        all_pages_ok = True
        results = []
        
        for page in doc_json:
            page_num = page.get("page_number")
            ok, cap_count, img_count = self.check_captions_under_images_page(page)
            results.append({
                "page_number": page_num,
                "ok": ok,
                "captions": cap_count,
                "images": img_count,
                "missing_captions": max(0, img_count - cap_count)
            })
            all_pages_ok &= ok
        
        return all_pages_ok, results

    def check_correctness_appendix(self, page_json: Dict[str, Any]) -> bool:
        """Проверить корректность приложения на странице."""
        text_blocks = page_json.get("text_blocks", [])
        all_text = " ".join([block.get("text", "") for block in text_blocks]).lower()

        letter_appendixes = LETTER_PATTERN.findall(all_text)
        number_appendixes = NUMBER_PATTERN.findall(all_text)
        simple_appendixes = SIMPLE_PATTERN.findall(all_text)

        if len(simple_appendixes) == 1 and len(letter_appendixes) == 0 and len(number_appendixes) == 0:
            return True   
        elif len(letter_appendixes) > 0 and len(number_appendixes) == 0:
            return True   
        else:
            return False

    def check_appendix(self, page_json: Dict[str, Any]) -> int:
        """Проверить приложение на странице."""
        text_blocks = page_json.get("text_blocks", [])
        all_text = " ".join([block.get("text", "") for block in text_blocks]).lower()
        
        if SIMPLE_PATTERN.search(all_text):
            if self.check_correctness_appendix(page_json):
                return 1  
            else:
                return -1 
        else:
            return 0  

    def check_document_appendices(self, doc_pages: List[Dict[str, Any]]) -> bool:
        """Проверить приложения во всем документе."""
        has_valid = False
        has_any_appendix = False

        for page_json in doc_pages:
            result = self.check_appendix(page_json)
            if result == -1:
                return False  
            elif result == 1:
                has_valid = True
            elif result == 0:
                text_blocks = page_json.get("text_blocks", [])
                all_text = " ".join([block.get("text", "") for block in text_blocks]).lower()
                if SIMPLE_PATTERN.search(all_text):
                    has_any_appendix = True

        if not has_any_appendix:
            return True
            
        return has_valid

    def check_links(self, page_json: Dict[str, Any]) -> bool:
        """Проверить наличие 'электронный ресурс' рядом со ссылками."""
        links = page_json.get("links") or []
        if not links:
            return True

        for link in links:
            line_text = (link.get("text") or "").strip()
            if not _E_RESOURCE_RE.search(line_text):
                return False
        return True

    def check_numbered_paragraph_spacing_page(self, page_json: Dict[str, Any], *, min_gap_pt: float = 8.0) -> Tuple[bool, List[Dict[str, Any]]]:
        """Проверить отступы нумерованных параграфов на странице."""
        blocks = page_json.get("text_blocks") or []
        problems: List[Dict[str, Any]] = []
        if not blocks:
            return True, problems

        for i, b in enumerate(blocks):
            text = (b.get("text") or "").strip()
            if not text:
                continue
            if _NUMBERED_PARAGRAPH_RE.match(text):
                j = i - 1
                while j >= 0 and not (blocks[j].get("text") or "").strip():
                    j -= 1
                if j >= 0:
                    try:
                        prev_bbox = blocks[j].get("bbox") or [0, 0, 0, 0]
                        cur_bbox = b.get("bbox") or [0, 0, 0, 0]
                        gap = float(cur_bbox[1]) - float(prev_bbox[3])
                    except Exception:
                        gap = min_gap_pt  
                    if gap < min_gap_pt:
                        problems.append({
                            "block_id": b.get("id"),
                            "gap_pt": gap,
                            "required_pt": min_gap_pt,
                            "prev_block_id": blocks[j].get("id"),
                            "text": text[:80]
                        })
        return len(problems) == 0, problems

    def check_numbered_paragraph_spacing_doc(self, doc_json: List[Dict[str, Any]], *, min_gap_pt: float = 8.0) -> Tuple[bool, List[Dict[str, Any]]]:
        """Проверить отступы нумерованных параграфов во всем документе."""
        all_ok = True
        details: List[Dict[str, Any]] = []
        for page in doc_json:
            ok, probs = self.check_numbered_paragraph_spacing_page(page, min_gap_pt=min_gap_pt)
            all_ok &= ok
            if not ok:
                details.append({
                    "page_number": page.get("page_number"),
                    "problems": probs,
                })
        return all_ok, details

    def check_numbered_paragraph_spacing_page_px(self, page_json: Dict[str, Any], *, min_gap_px: float = 10.0, dpi: int = 300) -> Tuple[bool, List[Dict[str, Any]]]:
        """Проверить отступы нумерованных параграфов в пикселях."""
        min_gap_pt = (min_gap_px * 72.0) / float(dpi)
        return self.check_numbered_paragraph_spacing_page(page_json, min_gap_pt=min_gap_pt)

    def check_font(self) -> bool:
        pass

    def check_links_doc(self, doc_json: List[Dict[str, Any]]) -> tuple[bool, List[Dict[str, Any]]]:
        """Проверить ссылки во всём документе."""
        results = []
        all_ok = True
        
        for page in doc_json:
            page_num = page.get("page_number", 0)
            links = page.get("links", [])
            
            if not links:
                results.append({
                    "page_number": page_num,
                    "ok": True,
                    "links_count": 0,
                    "problematic_links": []
                })
                continue
            
            problematic_links = []
            for link in links:
                pass 
                # нужна сама логика проверки
                
            page_ok = len(problematic_links) == 0
            if not page_ok:
                all_ok = False
            
            results.append({
                "page_number": page_num,
                "ok": page_ok,
                "links_count": len(links),
                "problematic_links": problematic_links
            })
        
        return all_ok, results

    def check_document(self, pdf_path: str, doc_json: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Комплексная проверка документа."""
        page_numbers_ok = self.check_document_pages(pdf_path)
        appendices_ok = self.check_document_appendices(doc_json)
        captions_ok, captions_results = self.check_captions_under_images_doc(doc_json)
        links_ok, links_results = self.check_links_doc(doc_json)
        # fonts_ok = self.check_font()
        all_ok = page_numbers_ok and appendices_ok and captions_ok and links_ok

        return {
            "all_ok": all_ok,
            "page_numbers_ok": page_numbers_ok,
            "appendices_ok": appendices_ok,
            "captions_ok": captions_ok,
            "captions_results": captions_results,
            "links_ok": True,
            "links_results": links_results,
        }
