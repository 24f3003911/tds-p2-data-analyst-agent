import os
import traceback
import logging
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List

from .data_loader import DataLoader
from .llm_orchestrator import LLMOrchestrator
from .utils.code_executor import CodeExecutor
from .utils.validation import sanitize_filename

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("analyst_agent")

# Soft safeguard (not enforced, just logged)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

app = FastAPI(title="Data Analyst Agent")

# Initialize components
loader = DataLoader()
executor = CodeExecutor()
orchestrator = LLMOrchestrator(loader, executor, debug=True)


@app.post("/analyze")
async def analyze(files: List[UploadFile] = File(...)):
    """
    Endpoint for analyzing uploaded files.
    - question.txt is mandatory and contains the main question.
    - Other files are optional and passed to the LLM without filtering.
    """

    try:
        uploaded_files = []
        question_text = None

        for file in files:
            contents = await file.read()

          
            if len(contents) > MAX_FILE_SIZE:
                logger.warning(f"File {file.filename} is very large ({len(contents)} bytes). May affect processing.")

            filename = sanitize_filename(file.filename or "untitled")
            file_data = {"filename": filename, "content": contents}

            if filename.lower() == "question.txt":
                question_text = contents.decode("utf-8", errors="ignore").strip()
                logger.info(f"Detected question.txt with {len(question_text)} chars")
            else:
                uploaded_files.append(file_data)

        if not question_text:
            logger.warning("Request missing question.txt")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "question.txt is required but missing"}
            )
        #Calling orchestrator
        orchestrator_result = orchestrator.handle_request(uploaded_files, question_text)
        return JSONResponse(content=orchestrator_result)

    except Exception as e:
        logger.error("Error in /analyze: %s", str(e))
        logger.debug(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/")
async def root():
    return {"status": "running", "message": "Data Analyst Agent API is up"}
