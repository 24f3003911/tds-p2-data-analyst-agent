"""
Updated settings for Data Analyst Agent - Hugging Face LLM First, OpenAI removed.
"""
import os
from pathlib import Path
from dotenv import load_dotenv  # NEW

# =====================
# Load .env automatically
# =====================
BASE_DIR = Path(__file__).resolve().parent.parent  # adjust if needed
dotenv_path = BASE_DIR / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)
    print(f"[INFO] Loaded environment variables from {dotenv_path}")
else:
    print("[WARNING] .env file not found, using system environment variables")



# =====================
# Basic API configuration
# =====================
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"


# =====================
# File handling
# =====================
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "50")) * 1024 * 1024  # Default 50MB
ALLOWED_EXTENSIONS = ['.csv', '.json', '.txt', '.xlsx', '.parquet', '.sqlite']

# API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# Models (fast, cost-aware defaults)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/llama-3.3-nemotron-70b-instruct")

# SLA / reliability
LLM_PER_PROVIDER_TIMEOUT_SEC = int(os.getenv("LLM_PER_PROVIDER_TIMEOUT_SEC", "30"))
LLM_TOTAL_BUDGET_SEC = int(os.getenv("LLM_TOTAL_BUDGET_SEC", "240"))  # keep < 5 minutes app-wide
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_BACKOFF_BASE_SEC = float(os.getenv("LLM_BACKOFF_BASE_SEC", "1.0"))


# =====================
# System limits
# =====================
MAX_FEEDBACK_ROUNDS = int(os.getenv("MAX_FEEDBACK_ROUNDS", "3"))
SANDBOX_IMAGE = os.getenv("MCP_PYTHON_IMAGE", "python:3.11-slim")
CODE_EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", "60"))  # seconds

# =====================
# Caching
# =====================
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/analyst_cache")
CACHE_EXPIRE = int(os.getenv("CACHE_EXPIRE", "3600"))  # seconds

# =====================
# Docker Execution
# =====================
DOCKER_ENABLED = os.getenv("DOCKER_ENABLED", "true").lower() == "true"



# =====================
# Allowed tools for LLM-generated code
# =====================
ALLOWED_LLM_TOOLS = [
    "pandas", "numpy", "matplotlib", "seaborn", "requests", "beautifulsoup4",
    "scikit-learn", "json", "csv", "sqlite3", "plotly", "PIL", "base64",
    "urllib", "re", "datetime", "os", "sys", "io", "scipy"
]

# =====================
# Prompt Templates
# =====================

INITIAL_SYSTEM_PROMPT = """You are an expert data analyst assistant.

Available files: {file_list}
User question: {question}

IMPORTANT: You must respond with ONE of these formats:
1. Python code in triple backticks: ```python
# your code here
```
2. Final answer starting with 'Final Answer:': Final Answer: [your answer]
3. Call specialist llms for tasks undoable by you: call_llm: {{"model": "scraping", "prompt": "your request"}}  

The user's question may require web scraping, data processing, visualization or any task related to data analysis. 
You should write Python code where required and return it as mentioned before and answer the user's questions.
"""

ERROR_PROMPT_TEMPLATE = """The code had an error: {error}

Please provide either: 1) Python code to execute, 2) A final answer starting with 'Final Answer:', or 3) A delegation instruction using 'call_llm: {{...}}'."""

DELEGATION_PROMPT_TEMPLATE = """You are a {model_type} specialist. 

Context: {context}
Task: {request}

Provide executable Python code or clear instructions."""

# Task classification patterns
TASK_PATTERNS = {
    'scraping': ['scrape', 'scraping', 'wikipedia', 'url', 'web', 'extract from', 'fetch from'],
    'visualization': ['plot', 'chart', 'graph', 'visualization', 'scatter', 'regression', 'draw'],
    'analysis': ['analyze', 'analysis', 'correlation', 'statistics', 'data', 'calculate', 'compute'],
    'ml': ['machine learning', 'predict', 'model', 'classification', 'clustering', 'regression'],
    'cleaning': ['clean', 'preprocessing', 'missing values', 'duplicates', 'outliers']
}