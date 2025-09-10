import os
import sys
import unittest
import fitz
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from config.model_config import _URL_RE
from page.extractors import LinkExtractor, TextExtractor


class TestLinkExtractor(unittest.TestCase):
    def _pairs_from_last_page(self, pdf_path: str):
        doc = fitz.open(pdf_path)
        last_page = doc[-1]
        text_dict = TextExtractor(last_page).get_text_dict()
        link_extractor = LinkExtractor(last_page)
        links = list(link_extractor._iter_link_annotations(text_dict))
        doc.close()
        return [(link["text"], link["uri"]) for link in links]

    def test_iter_link_annotations(self):
        pdf_path = os.path.join(os.path.dirname(__file__), "testData", "dataLinks", "threeLinks.pdf")

        got = self._pairs_from_last_page(pdf_path)
        expected = [
            ("1. Гугл диск с тестовыми видео ссылка",
             "https://drive.google.com/drive/folders/1-dUerY7t05JpnePiT8vUHHyaY9mOI15o?usp=sharing"),
            ("2. Ссылка на github с решением ссылка",
             "https://github.com/YurySalyatov/CV_Detection.git"),
            ("3. Датасет огня и дыма ссылка",
             "https://www.kaggle.com/datasets/sayedgamal99/smoke-fire-detection-yolo/data"),
            ("4. Датасет мусора ссылка",
             "https://www.kaggle.com/datasets/cubeai/trash-detection-for-yolov8/data"),
            ("5. Датасет телефонов ссылка",
             "https://www.kaggle.com/datasets/sergeysalytov/phone-detection-yolo-from-roboflow"),
            ("6. Датасет масок, балаклав, ножей, бит ссылка",
             "https://www.kaggle.com/datasets/sergeysalytov/yolo-knife-mask-stick"),
            ("7. Датасет курьеров ссылка",
             "https://www.kaggle.com/datasets/sergeysalytov/courier-dataset-for-yolo"),
            ("8. Ссылка на github с реализацией сервиса ссылка",
             "https://github.com/YurySalyatov/fastApiYOLOService/tree/master"),
        ]

        self.assertEqual(len(expected), len(got), f"Число ссылок не совпадает: expected {len(expected)}, got {len(got)}")
        for i, (exp, real) in enumerate(zip(expected, got), 1):
            self.assertEqual(exp, real, f"Пара #{i} не совпала.\nexpected={exp}\n   got={real}")

    def test_extract_links_method(self):
        doc = fitz.open()
        page = doc.new_page()
        extractor = LinkExtractor(page)
        text_extractor = TextExtractor(page)
        text_dict = text_extractor.get_text_dict()
        links = extractor.extract_links(text_dict)
        self.assertEqual(links, [])

    def test_empty_page(self):
        doc = fitz.open()
        page = doc.new_page()
        extractor = LinkExtractor(page)
        text_dict = TextExtractor(page).get_text_dict()
        links = extractor.extract_links(text_dict)
        self.assertEqual(links, [])

    def test_url_patterns(self):
        text_dict_single = {
            "blocks": [{
                "lines": [{
                    "bbox": [0, 0, 200, 20],
                    "spans": [
                        {"text": "см. https://example.com/docs", "bbox": [0, 0, 200, 20]},
                    ],
                }],
            }],
        }

        text_dict_two = {
            "blocks": [{
                "lines": [{
                    "bbox": [0, 0, 400, 20],
                    "spans": [
                        {"text": "зеркала:", "bbox": [0, 0, 60, 20]},
                        {"text": " http://a.tld", "bbox": [60, 0, 160, 20]},
                        {"text": " и ", "bbox": [160, 0, 200, 20]},
                        {"text": "https://b.tld/path", "bbox": [200, 0, 400, 20]},
                    ],
                }],
            }],
        }

        le = LinkExtractor(page=None)  
        got_single = [(it["text"], it["uri"]) for it in le._iter_inline_urls(text_dict_single)]
        got_two  = [(it["text"], it["uri"]) for it in le._iter_inline_urls(text_dict_two)]

        expected_single = [("см. https://example.com/docs", "https://example.com/docs")]
        expected_two = [
            ("зеркала: http://a.tld и https://b.tld/path", "http://a.tld"),
            ("зеркала: http://a.tld и https://b.tld/path", "https://b.tld/path"),
        ]

        with self.subTest(case="single"):
            self.assertEqual(expected_single, got_single)
        with self.subTest(case="two"):
            self.assertEqual(expected_two, got_two)

    def test_iter_inline_urls(self):
        text_dict = {
            "blocks": [{
                "lines": [{
                    "bbox": [0, 0, 200, 20],
                    "spans": [
                        {"text": "Visit https://example.com for more info", "bbox": [0, 0, 200, 20]},
                    ],
                }],
            }],
        }
        
        le = LinkExtractor(page=None)
        urls = list(le._iter_inline_urls(text_dict))
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0]["uri"], "https://example.com")


if __name__ == "__main__":
    unittest.main()