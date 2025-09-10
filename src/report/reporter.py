import os
from typing import List, Dict, Any
from .checker import Checker


class Reporter:
    """Класс для генерации отчетов о проверке PDF документов."""
    
    def __init__(self):
        self.checker = Checker()

    def get_report(self, pdf_path: str, doc_json: List[Dict[str, Any]]) -> str:
        """Сгенерировать текстовый отчет о проверке документа."""
        report_data = self.checker.check_document(pdf_path, doc_json)
        report_lines = []

        if report_data["all_ok"]:
            return "Все проверки пройдены."

        if not report_data["page_numbers_ok"]:
            missing_numbers = []
            for i, page in enumerate(doc_json):
                has_number, _ = self.checker.has_page_number_from_json(page)
                if not has_number:
                    missing_numbers.append(page.get("page_number", i+1))
            report_lines.append(f"Номера страниц отсутствуют на страницах: {missing_numbers}")

        if not report_data["appendices_ok"]:
            bad_appendix_pages = []
            for i, page in enumerate(doc_json):
                result = self.checker.check_appendix(page)
                if result == -1:
                    bad_appendix_pages.append(page.get("page_number", i+1))

            if bad_appendix_pages:
                report_lines.append(f"Некорректные приложения на страницах: {bad_appendix_pages}")
            else:
                report_lines.append("Приложения отсутствуют или не пронумерованы корректно.")

        if not report_data["captions_ok"]:
            missing_captions_pages = [
                f"{p['page_number']} (отсутствуют подписи к {p['missing_captions']} изображению/ям)"
                for p in report_data["captions_results"] 
                if not p["ok"]
            ]
            report_lines.append(f"Проблемы с подписями к изображениям на страницах: {missing_captions_pages}")

        if not report_data["links_ok"]:
            problematic_pages = [str(p["page_number"]) for p in report_data["links_results"] if not p["ok"] and p["links_count"] > 0]
            if problematic_pages:
                report_lines.append(f"Некорректные ссылки на страницах: {', '.join(problematic_pages)}")
            else:
                report_lines.append("Обнаружены проблемы со ссылками.")

        return os.linesep.join(report_lines)

    def get_detailed_report(self, pdf_path: str, doc_json: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Получить подробный отчет в виде словаря."""
        return self.checker.check_document(pdf_path, doc_json)

    # def get_spacing_report(self, doc_json: List[Dict[str, Any]], min_gap_pt: float = 8.0) -> Dict[str, Any]:
    #     """Получить отчет о проблемах с отступами нумерованных параграфов."""
    #     all_ok, details = self.checker.check_numbered_paragraph_spacing_doc(doc_json, min_gap_pt=min_gap_pt)
        
    #     return {
    #         "all_ok": all_ok,
    #         "problems_count": len(details),
    #         "pages_with_problems": [d["page_number"] for d in details],
    #         "details": details
    #     }

    def save_report(self, pdf_path: str, doc_json: List[Dict[str, Any]], output_path: str):
        """Сохранить отчет в файл."""
        report = self.get_report(pdf_path, doc_json)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

