# Data Analyst Agent

A fully LLM-centric data analysis agent that uses a feedback-loop orchestration system to analyze data and answer questions.

## 🎯 Purpose

This agent system:

- Accepts user tasks via API with optional data files (CSV, JSON, Parquet, SQLite, etc.)
- Passes full context to a Language Model (LLM) for interpretation and analysis
- The LLM generates code, reflects on execution results, and provides final answers
- Supports delegation to specialized LLMs for specific tasks (visualization, scraping, analysis)
- Uses a feedback loop architecture where the application only orchestrates, while the LLM handles all logic

## 🧠 Architecture

The system uses a **feedback-loop based orchestration**:

1. **LLM Response Types**:
   - **Code blocks**: Python code to execute for analysis
   - **Final answers**: Complete responses to user questions  
   - **Delegation**: Instructions to call specialist LLMs

2. **Feedback Loop**:
   - LLM generates response
   - System executes code or handles delegation
   - Results feed back to LLM for analysis
   - Process continues until final answer is provided

3. **Key Components**:
   - **FastAPI endpoint** for user requests
   - **LLM orchestrator** managing the feedback loop
   - **Code executor** for sandboxed Python execution
   - **Data loader** for file processing
   - **Response parser** for structured LLM output
   - **Caching system** for performance optimization

## 📁 Project Structure

```
data-analyst-agent/
├── src/
│   └── analyst_agent/
│       ├── main.py                 # FastAPI endpoint
│       ├── llm_orchestrator.py     # Core feedback loop logic
│       ├── llm_parser.py           # LLM response parser
│       ├── data_loader.py          # File loading and processing
│       ├── utils/
│       │   ├── llm_clients.py      # Multi-LLM support (HF + OpenAI)
│       │   ├── code_executor.py    # Sandboxed code execution
│       │   ├── validation.py       # Output validation
│       │   └── cache.py            # Disk-based caching
│       └── configs/
│           └── settings.py         # Configuration management
├── tests/
│   └── test_app.py                 # Comprehensive test suite
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container setup
└── README.md                       # This file
```

## 🚀 Installation & Setup

### Local Development

1. **Clone and setup**:
```bash
git clone <repository-url>
cd data-analyst-agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Environment configuration**:
```bash
# Optional: Configure models and settings
export HF_MODEL_NAME="gpt2"  # Default HuggingFace model
export OPENAI_API_KEY="your-key-here"  # Optional OpenAI support
export DEBUG="True"  # Enable debug mode
```

4. **Run the application**:
```bash
python -m uvicorn src.analyst_agent.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment

1. **Build and run**:
```bash
docker build -t data-analyst-agent .
docker run -p 8000:8000 -e OPENAI_API_KEY="your-key" data-analyst-agent
```

2. **With environment file**:
```bash
docker run -p 8000:8000 --env-file .env data-analyst-agent
```

## 📖 Usage Examples

### Basic API Usage

**Upload files and ask questions**:

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "question=Analyze the sales data and identify trends" \
  -F "files=@sales_data.csv" \
  -F "files=@customer_info.json"
```

**Programmatic JSON API**:

```bash
curl -X POST "http://localhost:8000/analyze_simple" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the average age in this dataset?",
    "files": [
      {
        "name": "data.csv", 
        "content": "bmFtZSxhZ2UKSm9obiwzMApKYW5lLDI1"
      }
    ]
  }'
```

### Python Client Example

```python
import requests
import base64

# Prepare file
with open("data.csv", "rb") as f:
    file_content = base64.b64encode(f.read()).decode()

# Make request
response = requests.post("http://localhost:8000/analyze_simple", json={
    "question": "Analyze this data and create visualizations",
    "files": [{"name": "data.csv", "content": file_content}]
})

result = response.json()
print(f"Success: {result['success']}")
print(f"Answer: {result['response']}")
```

### Supported File Types

- **CSV** (`.csv`) - Tabular data
- **JSON** (`.json`) - Structured data  
- **Excel** (`.xlsx`) - Spreadsheets
- **Parquet** (`.parquet`) - Columnar data
- **SQLite** (`.sqlite`) - Database files
- **Text** (`.txt`) - Plain text data

## 🔧 Configuration

### Environment Variables

```bash
# LLM Configuration
HF_MODEL_NAME="gpt2"                    # HuggingFace model
OPENAI_API_KEY=""                       # OpenAI API key (optional)
OPENAI_MODEL_NAME="gpt-3.5-turbo"      # OpenAI model
DEFAULT_MODEL="hf"                      # "hf" or "openai"

# System Limits
MAX_FEEDBACK_ROUNDS=10                  # Max analysis rounds
CODE_EXEC_TIMEOUT=30                    # Code execution timeout (seconds)
MAX_FILE_SIZE=50                        # Max file size (MB)

# Caching
CACHE_DIR="/tmp/analyst_cache"          # Cache directory
CACHE_EXPIRE=3600                       # Cache expiry (seconds)

# API Settings
API_HOST="0.0.0.0"                     # Server host
API_PORT=8000                          # Server port
DEBUG="False"                          # Debug mode
```

### Specialist Models

Configure specialist models for specific tasks:

```python
SPECIALIST_MODELS = {
    "visualization": "gpt2",      # Data visualization
    "scraping": "gpt2",          # Web scraping  
    "analysis": "gpt2",          # Statistical analysis
}
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_app.py::TestDataLoader -v
pytest tests/test_app.py::TestLLMParser -v
pytest tests/test_app.py::TestCodeExecutor -v

# Run with coverage
pytest tests/ --cov=src/analyst_agent --cov-report=html
```

## 🔍 API Documentation

Once running, access interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Main Endpoints

- **POST /analyze**: Main analysis endpoint with file upload
- **POST /analyze_simple**: JSON-based analysis endpoint
- **GET /health**: Health check and system status
- **GET /models**: List available LLM models
- **GET /**: API information and available endpoints

## 🎭 Design Philosophy

### LLM-Only Logic
- The application provides **zero domain knowledge**
- All analysis logic comes from the LLM
- System only handles orchestration and execution

### Feedback-Driven Architecture  
- LLM sees all context including previous results
- Can iteratively refine analysis based on execution feedback
- Self-correcting when code fails or results are incomplete

### Tool Delegation
- LLM can delegate to specialist models
- Supports different models for visualization, scraping, analysis
- Extensible for new specialist capabilities

## 🚨 Security Considerations

- **Sandboxed Execution**: Code runs in isolated temporary directories
- **File Validation**: Size and type restrictions on uploads
- **Timeout Protection**: Execution timeouts prevent runaway processes
- **Input Sanitization**: Filename and content validation

## 📝 Development Notes

### Adding New File Types

1. Add extension to `ALLOWED_EXTENSIONS` in `settings.py`
2. Implement parser in `data_loader.py` `_analyze_*` method
3. Add validation logic if needed

### Adding New LLM Providers

1. Create client class in `llm_clients.py`
2. Add configuration in `settings.py`
3. Update orchestrator routing logic

### Extending Specialist Models

1. Add model configuration in `SPECIALIST_MODELS`
2. Update delegation handling in `llm_orchestrator.py`
3. Add model-specific prompting if needed

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ -v`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with FastAPI for high-performance async API
- Uses HuggingFace Transformers for local LLM support
- Leverages diskcache for efficient result caching
- Pandas ecosystem for data processing capabilities