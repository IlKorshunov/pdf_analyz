"""Тесты для класса TextExtractor с реальными данными."""
import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
import time
import fitz
from page.extractors import TextExtractor
from typing import List


class TestTextExtractor(unittest.TestCase):    
    @classmethod
    def setUpClass(cls):
        """Настройка класса - загружаем тестовый PDF один раз."""
        test_pdf_path = os.path.join(os.path.dirname(__file__), 'testData', 'dataText', 'copyTwoText.pdf')
        cls.test_pdf_path = test_pdf_path
        cls.doc = fitz.open(test_pdf_path)
        cls.test_page = cls.doc[0]
    
    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'doc'):
            cls.doc.close()
    
    def setUp(self):
        self.extractor = TextExtractor(self.test_page)
    
    def test_get_text_dict(self):
        first_line: str = "ГЛАВА 1. Обзор предметной области"
        second_line: str = "1.1"
        third_line: str = "Задача автопромптинга"
        fourth_line: str = "Автопромптинг – это задача автоматической генерации или оптимизации"
        expected_lines: List[str] = [first_line, second_line, third_line, fourth_line]

        get_lines = []
        text_dict = self.extractor.get_text_dict()
        self.assertIn("blocks", text_dict)
        self.assertIsInstance(text_dict["blocks"], list)
        
        text_blocks = [b for b in text_dict["blocks"] if "lines" in b]
        self.assertGreater(len(text_blocks), 0)
        
        has_text = False
        for block in text_blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        get_lines.append(span.get("text", "").strip())
                        has_text = True
        self.assertTrue(has_text, "Должен быть найден текст в блоках")
        for idx, expected in enumerate(expected_lines):
            self.assertEqual(expected, get_lines[idx], f"Строка {idx+1} не соответствует ожидаемой. expected: {expected}, got: {get_lines[idx]}")

    def test_build_block_struct(self):
        block = self.extractor.get_text_dict()["blocks"][0]
        block_struct = self.extractor._build_block_struct(block, 0)
        self.assertIsNotNone(block_struct)
        self.assertEqual(block_struct["text"], "ГЛАВА 1. Обзор предметной области")
        self.assertEqual(len(block_struct["spans"]), 1)
        self.assertEqual(block_struct["spans"][0]["text"], "ГЛАВА 1. Обзор предметной области")


    def test_need_space_between(self):
        self.assertTrue(TextExtractor.need_space_between("Hello", "world"))
        self.assertTrue(TextExtractor.need_space_between("123", "456"))
        self.assertTrue(TextExtractor.need_space_between("word", "text"))
        
        self.assertFalse(TextExtractor.need_space_between("Hello ", "world"))  
        self.assertFalse(TextExtractor.need_space_between("Hello", " world")) 
        self.assertFalse(TextExtractor.need_space_between("Hello", ".world")) 
        self.assertFalse(TextExtractor.need_space_between("Hello", "!world")) 
        self.assertFalse(TextExtractor.need_space_between("Hello", ",world")) 
        self.assertFalse(TextExtractor.need_space_between("", "world"))       
        self.assertFalse(TextExtractor.need_space_between("Hello", ""))       
        self.assertFalse(TextExtractor.need_space_between("Hello.", "world")) 
        
        self.assertFalse(TextExtractor.need_space_between(" ", "world"))      
        self.assertFalse(TextExtractor.need_space_between("Hello", " "))      
        self.assertTrue(TextExtractor.need_space_between("Hello", "world!"))  
        self.assertFalse(TextExtractor.need_space_between("Hello!", "world")) 


if __name__ == '__main__':
    unittest.main(verbosity=2)
