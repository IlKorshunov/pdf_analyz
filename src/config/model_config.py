import re
import os

_URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)")
TOC_WORDS_RE = re.compile(r"\b(содержание|введение)\b", re.IGNORECASE)
Appendix_WORDS_RE = re.compile(r"\b(приложение)\b", re.IGNORECASE)
LETTER_PATTERN = re.compile(r'приложение\s*[а-яёa-z]', re.IGNORECASE)
NUMBER_PATTERN = re.compile(r'приложение\s*\d+', re.IGNORECASE)
SIMPLE_PATTERN = re.compile(r'приложение', re.IGNORECASE)
_NUMBERED_PARAGRAPH_RE = re.compile(r"^\s*\d+\.\d+(?:\.\d+)*\s+")
_E_RESOURCE_RE = re.compile(r"электрон\w*\.?\s*ресурс\w*", re.IGNORECASE)

DEFAULT_DPI = 300

def get_model_configs(weights_dir: str = "weights") -> dict:
    """Получить конфигурации моделей с относительными путями к весам."""
    weights_path = os.path.abspath(weights_dir)
    
    return {
        "publaynet": {
            "config_path": "lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config",
            "weights_path": os.path.join(weights_path, "large.pth"),
            "label_map": {0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
        },
        "prima": {
            "config_path": "lp://PrimaLayout/mask_rcnn_R_50_FPN_3x/config",
            "weights_path": os.path.join(weights_path, "prima_weights.pth"),
            "label_map": {
                1: "TextRegion", 2: "ImageRegion", 3: "TableRegion",
                4: "MathsRegion", 5: "SeparatorRegion", 6: "OtherRegion"
            }
        },
        "hjdataset": {
            "config_path": "lp://HJDataset/mask_rcnn_R_50_FPN_3x/config",
            "weights_path": os.path.join(weights_path, "hj_weights.pth"),
            "label_map": {
                1: "Page Frame", 2: "Row", 3: "Title Region",
                4: "Text Region", 5: "Title", 6: "Subtitle", 7: "Other"
            },
        },
    }

MODEL_CONFIGS = get_model_configs()

