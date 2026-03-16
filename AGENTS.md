# AGENTS.md - Development Guide for AIoT农业智能问答系统

## Project Overview

This is a Django 4.2.17-based agricultural IoT AI question answering system developed by 华中农业大学AIoT实验室. It integrates:
- Django + Django REST Framework backend
- DeepSeek-R1, Spark API for AI问答
- Knowledge graph extraction (LTP)
- Image recognition (diseaseModel)
- Agent system (brain_agent.py)

## Build / Run Commands

### Development Server
```bash
# From Django-dashboard directory
python manage.py runserver 127.0.0.1:8000
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Database Migrations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

### Running Tests
No formal test framework configured. Manual testing via:
- Django admin at `/admin`
- API endpoints via curl/Postman

To run a single test manually:
```bash
# Test DeepSeek API
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from aiModels.qaModel.deepseek_r1_api import get_answer
print(get_answer([{'role': 'user', 'content': '测试'}]))
"

# Test Spark API
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from aiModels.qaModel.spark_api import get_answer
print(get_answer('测试'))
"

# Test Agent session
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from aiModels.agent.brain_agent import creat_session
print(creat_session('http://localhost:4096', '测试会话'))
"
```

### Linting
No linting tools configured. Manual code review required.

## Code Style Guidelines

### General Conventions
- **Language**: Chinese comments preferred (project is Chinese agricultural domain)
- **Encoding**: UTF-8
- **Python Version**: 3.10+

### Imports (Order: stdlib → third-party → local)
```python
# Standard library first
import json
import requests
from typing import Any, Dict, List, Optional

# Third-party
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

# Local application
from aiModels.qaModel.deepseek_r1_api import chat_history
```

### Django Views (REST API Pattern)
```python
@csrf_exempt
@require_POST
def my_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # ... logic
            return JsonResponse({'success': True, 'data': result})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
```

### Type Hints
Use type hints for function signatures:
```python
from typing import Any, Dict, List, Optional

def process_data(items: List[str]) -> Dict[str, Any]:
    ...

def get_answer(messages: List[Dict[str, str]]) -> str:
    ...
```

### Naming Conventions
- **Functions**: `snake_case` (e.g., `get_answer`, `extract_entities`)
- **Classes**: `PascalCase` (e.g., `DiseaseRecognition`, `TimeStampedModel`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MODEL_NAME`, `BASE_URL`)
- **Django views**: suffix with `_view` (e.g., `agent_send_message_view`)
- **Database models**: singular PascalCase (e.g., `Base`, `Device`)

### Error Handling
- Always wrap API calls in try/except
- Return JSON errors with appropriate HTTP status codes (400, 404, 500)
- Log errors with print() for debugging
- Handle specific exceptions before generic ones

### Database Models
- Use abstract base classes for common fields (see `TimeStampedModel`)
- Use `managed = False` for existing tables
- Always specify `db_table` and `db_column` for existing MySQL tables
- Use `db_index=True` for frequently queried fields
```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
```

### API Design
- RESTful endpoints in `aiModels/urls.py`
- Use `@require_POST` for mutation endpoints
- Return `JsonResponse` with `success`/`error` keys
- View functions should be in appropriate modules (not all in views.py)

### Templates
- Located in `aiModels/templates/`
- Use Django template syntax
- Support iframe embedding (see `agent.html`)

### Agent System
- Brain agent entry: `aiModels/agent/brain_agent.py`
- SSE streaming via `StreamingHttpResponse`
- Session management via opencode API
- View functions: `_create_session_view`, `_send_message_view`, `_delete_session_view`

### File Output Directories
- **代码/脚本文件**（.py等）：`./aiModels/agent/temp`
- **结果文件**（ppt、doc、pdf、xls等）：`./aiModels/agent/output`

## Project Structure

```
Django-dashboard/
├── manage.py
├── requirements.txt
├── config/
│   ├── settings.py      # Django settings
│   ├── urls.py          # Root URL config
│   └── ...
├── aiModels/
│   ├── urls.py          # App URLs
│   ├── views.py         # Page render views
│   ├── agent/           # Agent system
│   │   └── brain_agent.py
│   ├── qaModel/        # Q&A + RAG
│   │   ├── deepseek_r1_api.py
│   │   ├── spark_api.py
│   │   └── RAG.py
│   ├── diseaseModel/   # Image recognition
│   ├── graph/          # Knowledge graph
│   └── templates/
├── screen/              # Frontend screens
├── storageSystem/       # Database models
│   └── models.py       # ORM models
└── labDatasets/        # Dataset management
```

## Key Patterns

### Adding New API Endpoint
1. Create view function in appropriate module (not views.py for APIs)
2. Add URL route in `aiModels/urls.py`
3. Use decorators: `@csrf_exempt`, `@require_POST` (if needed)

### Adding New Agent
1. Create module in `aiModels/agent/`
2. Implement agent logic
3. Register in brain_agent routing if needed

### Database Access
- Default DB: MySQL `web_database`
- Remote DB: `pig` database for sensor data
- Use Django models in respective apps

### External API Endpoints
- Ollama: `http://localhost:11435` (DeepSeek-R1)
- opencode: `http://localhost:4096` (Agent sessions)
