#!/usr/bin/env python3
"""
Debug script to identify import issues in the Data Analyst Agent.
"""

import sys
import traceback
from pathlib import Path

print("🔍 Data Analyst Agent - Import Debugging")
print(f"Python version: {sys.version}")
print(f"Working directory: {Path.cwd()}")
print(f"Python path: {sys.path[:3]}...")  # First 3 entries
print()

# Test 1: Basic Python imports
print("1️⃣ Testing basic Python imports...")
basic_imports = ['os', 'json', 'typing', 'pathlib']
for module in basic_imports:
    try:
        __import__(module)
        print(f"   ✓ {module}")
    except ImportError as e:
        print(f"   ✗ {module}: {e}")

print()

# Test 2: FastAPI and web framework imports
print("2️⃣ Testing web framework imports...")
web_imports = ['fastapi', 'uvicorn', 'pydantic', 'starlette']
for module in web_imports:
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f"   ✓ {module} {version}")
    except ImportError as e:
        print(f"   ✗ {module}: {e}")

print()

# Test 3: Data science imports
print("3️⃣ Testing data science imports...")
ds_imports = ['pandas', 'numpy', 'matplotlib']
for module in ds_imports:
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f"   ✓ {module} {version}")
    except ImportError as e:
        print(f"   ✗ {module}: {e}")

print()

# Test 4: Heavy ML imports
print("4️⃣ Testing ML/AI imports...")
ml_imports = ['torch', 'transformers', 'sklearn']
for module in ml_imports:
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f"   ✓ {module} {version}")
    except ImportError as e:
        print(f"   ✗ {module}: {e}")

print()

# Test 5: Docker and system imports
print("5️⃣ Testing system imports...")
sys_imports = ['docker', 'requests', 'diskcache']
for module in sys_imports:
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f"   ✓ {module} {version}")
    except ImportError as e:
        print(f"   ✗ {module}: {e}")

print()

# Test 6: Project imports
print("6️⃣ Testing project imports...")
project_imports = [
    'src.analyst_agent.configs.settings',
    'src.analyst_agent.data_loader',
    'src.analyst_agent.llm_parser',
    'src.analyst_agent.utils.cache',
    'src.analyst_agent.utils.validation'
]

for module in project_imports:
    try:
        __import__(module)
        print(f"   ✓ {module}")
    except ImportError as e:
        print(f"   ✗ {module}: {e}")
        print(f"      Full error: {traceback.format_exc()}")
    except Exception as e:
        print(f"   ⚠ {module}: {e}")

print()

# Test 7: Create minimal FastAPI app
print("7️⃣ Testing minimal FastAPI app creation...")
try:
    from fastapi import FastAPI
    
    app = FastAPI(title="Test App")
    
    @app.get("/")
    def root():
        return {"message": "Test successful"}
    
    print("   ✓ Minimal FastAPI app created successfully")
    
except Exception as e:
    print(f"   ✗ Failed to create FastAPI app: {e}")
    print(f"      Full error: {traceback.format_exc()}")

print()

# Test 8: Check if project structure is correct
print("8️⃣ Checking project structure...")
required_files = [
    'src/analyst_agent/__init__.py',
    'src/analyst_agent/main.py', 
    'src/analyst_agent/configs/__init__.py',
    'src/analyst_agent/configs/settings.py',
    'src/analyst_agent/utils/__init__.py'
]

for file_path in required_files:
    path = Path(file_path)
    if path.exists():
        print(f"   ✓ {file_path}")
    else:
        print(f"   ✗ Missing: {file_path}")

print()
print("🎯 Debugging complete! Check for ✗ marks above to identify issues.")