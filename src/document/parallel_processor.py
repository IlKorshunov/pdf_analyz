import os
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from PIL import Image
from document.document import Document
from page.page import Page
import fitz

class ParallelProcessor:
    """Класс для параллельной обработки PDF документов."""
    
    def __init__(self, processes: Optional[int] = None):
        self.processes = processes

    def _get_worker_count(self, task_count: int) -> int:
        """Определить оптимальное количество воркеров."""
        max_procs = os.cpu_count()
        if self.processes is None: return min(task_count, max_procs)
        else: return max(1, min(self.processes, max_procs, task_count))

    def _worker_analyze_document(self, pdf_path: str, resolved: bool, images_dir: str = "images") -> Tuple[str, Any]:
        """Воркер для анализа одного документа."""
        try:
            with Document(pdf_path) as doc:
                if resolved:
                    result = doc.analyze_document(images_dir=images_dir, resolved=True)
                else:
                    result = doc.analyze_document(images_dir=images_dir, resolved=False)
            return pdf_path, result
        except Exception as exc:
            return pdf_path, {"__error__": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}

    def analyze_documents_parallel(self, pdf_paths: List[str], images_dir: str = "images", 
                                 *, resolved: bool = False) -> Dict[str, Any]:
        """Параллельный анализ нескольких документов."""
        if not pdf_paths:
            return {}

        workers = self._get_worker_count(len(pdf_paths))
        results: Dict[str, Any] = {}
        
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._worker_analyze_document, path, resolved, images_dir): path 
                for path in pdf_paths
            }
            
            for future in as_completed(futures):
                path = futures[future]
                try:
                    _path, res = future.result()
                    results[_path] = res
                except Exception as exc:
                    results[path] = {"__error__": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}

        return results

    def _worker_analyze_page(self, pdf_path: str, page_index: int, images_dir: str, resolved: bool) -> Tuple[int, Any]:
        """Воркер для анализа одной страницы."""
        try:
            doc = fitz.open(pdf_path)
            try:
                page = doc[page_index]
                page_obj = Page(pdf_path, page)
                
                if resolved:
                    vis_images = []
                    result = page_obj.analyze_page(doc, images_dir=images_dir, resolved=True, vis_images=vis_images)
                    vis_img = vis_images[0] if vis_images else None
                    return page_index, result, vis_img
                else:
                    result = page_obj.analyze_page(doc, images_dir=images_dir, resolved=False)
                    return page_index, result
            finally:
                doc.close()
        except Exception as exc:
            logging.error("Page analysis failed for %s [page %d]: %s", pdf_path, page_index, exc)
            error_result = {"__error__": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(), "page_number": page_index}
            if resolved:
                return page_index, error_result, None
            else:
                return page_index, error_result

    def analyze_document_parallel_pages(self, pdf_path: str, images_dir: str = "images", 
                                      *, resolved: bool = False, include_errors: bool = False) -> List[Any]:
        """Параллельный анализ страниц одного документа."""
        if not pdf_path:
            return []

        try:
            doc = fitz.open(pdf_path)
            num_pages = len(doc)
            doc.close()
        except Exception:
            logging.error("Failed to open PDF: %s", pdf_path)
            return []

        workers = self._get_worker_count(num_pages)
        by_index: Dict[int, Any] = {}
        vis_images: List[Image.Image] = []
        
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._worker_analyze_page, pdf_path, i, images_dir, resolved): i 
                for i in range(num_pages)
            }
            
            for future in as_completed(futures):
                i = futures[future]
                try:
                    if resolved:
                        result_tuple = future.result()
                        if len(result_tuple) == 3:
                            idx, res, vis_img = result_tuple
                            if vis_img is not None:
                                try:
                                    img = vis_img if vis_img.mode == "RGB" else vis_img.convert("RGB")
                                    vis_images.append(img)
                                except Exception:
                                    pass
                        else:
                            idx, res = result_tuple[0], result_tuple[1]
                    else:
                        idx, res = future.result()
                    
                    by_index[idx] = res
                except Exception as exc:
                    logging.error("Future failed for page %d: %s", i, exc)
                    by_index[i] = {"__error__": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(), "page_number": i}

        out: List[Any] = []
        for i in range(num_pages):
            res = by_index.get(i)
            if res is None:
                continue
            if not include_errors and isinstance(res, dict) and res.get("__error__"):
                continue
            out.append(res)
        
        if resolved and vis_images:
            os.makedirs(images_dir, exist_ok=True)
            pdf_out = os.path.join(images_dir, "resolved_annotated.pdf")
            try:
                first, rest = vis_images[0], vis_images[1:]
                first.save(pdf_out, "PDF", resolution=100.0, save_all=True, append_images=rest)
                for r in out:
                    if isinstance(r, dict):
                        r["annotated_pdf_path"] = pdf_out
            except Exception as exc:
                logging.error("Failed to create PDF: %s", exc)
        
        return out
