# PDF Document Analysis System

Система для комплексного анализа PDF документов с извлечением контента, проверкой качества и генерацией отчетов. Поддерживает извлечение текста, таблиц, ссылок, изображений, заголовков и автоматическую проверку структуры документов.

## Основные возможности

### Извлечение контента
- **Текст**: структурированное извлечение с сохранением форматирования
- **Таблицы**: автоматическое обнаружение и извлечение табличных данных
- **Ссылки**: извлечение URL и проверка их валидности
- **Изображения**: сохранение изображений с высоким качеством
- **Заголовки**: автоматическое определение структуры заголовков и оглавления

### Анализ структуры
- **Оглавление**: автоматическое обнаружение страниц с содержанием
- **Нумерация**: проверка корректности нумерации страниц
- **Приложения**: валидация структуры приложений
- **Layout анализ**: использование ML моделей для анализа структуры документа

### Проверка качества
- **Валидация ссылок**: проверка доступности внешних ссылок
- **Подписи к изображениям**: проверка наличия описаний изображений
- **Структурная целостность**: валидация оглавления и приложений
- **Детальные отчеты**: генерация отчетов о найденных проблемах

## Быстрый старт

### Установка

1. **Клонируйте репозиторий:**
```bash
git clone <repository-url>
cd pdf_analyz
```

2. **Создайте виртуальное окружение:**
```bash
python -m venv venv310
source venv310/bin/activate 
```

3. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

4. **[Скачайте веса моделей](https://layout-parser.readthedocs.io/en/latest/notes/modelzoo.html)** (поместите в папку `weights/`): 
  - `large.pth` - для модели PubLayNet
   - `prima_weights.pth` - для модели PrimaLayout
   - `hj_weights.pth` - для модели HJDataset

### Использование

#### Командная строка

```bash
# Базовый анализ документа
python notebooks/main.py data/your_document.pdf

# С сохранением результатов в JSON
python notebooks/main.py data/your_document.pdf --output results.json

# С извлечением изображений
python notebooks/main.py data/your_document.pdf --images extracted_images

# С resolved режимом (ML анализ структуры)
python notebooks/main.py data/your_document.pdf --resolved --verbose

# С указанием папки с весами моделей
python notebooks/main.py data/your_document.pdf --weights path/to/weights
```

#### Jupyter Notebook

```python
import sys
sys.path.append('../src')

from main import analyze_document_pipeline

# Анализ документа
results, check_results = analyze_document_pipeline(
    "data/your_document.pdf",
    output_json_path="results.json",
    images_dir="extracted_images",
    resolved=True,
    verbose=True
)

print(f"Проверки пройдены: {check_results['all_ok']}")
print(f"Проанализировано страниц: {len(results)}")
```


## Конфигурация

### Модели машинного обучения

Система поддерживает три модели для анализа структуры документов:

- **PubLayNet**: для научных статей и документов
- **PrimaLayout**: универсальная модель для различных типов документов  
- **HJDataset**: специализированная модель для китайских документов

Конфигурация моделей находится в `src/config/model_config.py`:

```python
def get_model_configs(weights_dir: str = "weights") -> dict:
    return {
        "publaynet": {
            "config_path": "lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config",
            "weights_path": os.path.join(weights_path, "large.pth"),
            "label_map": {0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
        },
        # ... другие модели
    }
```

### Регулярные выражения

В `model_config.py` определены регулярные выражения для:
- Поиска URL в тексте
- Обнаружения оглавления
- Поиска приложений
- Валидации структуры документов

## Формат выходных данных

### JSON результаты

```json
{
  "pages": [
    {
      "page_number": 0,
      "text": {
        "blocks": [...],
        "structured_blocks": [...]
      },
      "tables": [...],
      "links": [...],
      "images": [...],
      "titles": [...]
    }
  ],
  "document_info": {
    "total_pages": 54,
    "toc_pages": [5],
    "has_appendices": true
  }
}
```
