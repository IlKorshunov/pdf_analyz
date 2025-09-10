import sys
import argparse

sys.path.append('../src')

from document import Document, ParallelProcessor
from page import Page
from page.extractors import TextExtractor, TableExtractor, LinkExtractor, ImageExtractor, TitleExtractor
from report import Checker, Reporter
import fitz


def analyze_document_pipeline(pdf_path: str, output_json_path: str = "analysis_results.json", 
                    images_dir: str = "images", resolved: bool = False, verbose: bool = False, 
                    weights_dir: str = "weights"):
    """Анализ PDF документа с проверками качества."""
    
    with Document(pdf_path) as doc:
        results = doc.analyze_document(images_dir=images_dir, resolved=resolved, verbose=verbose, weights_dir=weights_dir)
        doc.analyze_and_save_json(output_json_path, images_dir=images_dir, resolved=resolved, verbose=verbose, weights_dir=weights_dir)
    
    checker = Checker()
    reporter = Reporter()
    
    check_results = checker.check_document(pdf_path, results)
    
    report_path = "quality_report.txt"
    reporter.save_report(pdf_path, results, report_path)
    
    return results, check_results


def main():
    """Главная функция для командной строки."""
    
    parser = argparse.ArgumentParser(description='Анализ PDF документов')
    parser.add_argument('pdf_path', help='Путь к PDF файлу')
    parser.add_argument('--output', '-o', default='analysis_results.json', 
                       help='Путь для сохранения JSON результатов')
    parser.add_argument('--images', '-i', default='images', 
                       help='Папка для сохранения изображений')
    parser.add_argument('--resolved', action='store_true', 
                       help='Использовать resolved режим анализа')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Подробный вывод')
    parser.add_argument('--weights', '-w', default='weights', 
                       help='Папка с весами моделей')
    
    args = parser.parse_args()

    try:
        _, check_results = analyze_document_pipeline(
            pdf_path=args.pdf_path,
            output_json_path=args.output,
            images_dir=args.images,
            resolved=args.resolved,
            verbose=args.verbose,
            weights_dir=args.weights
        )
        
        if check_results['all_ok']:
            print("Все проверки пройдены успешно!")
            sys.exit(0)
        else:
            print("Найдены проблемы в документе!")
            sys.exit(1)
            
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()