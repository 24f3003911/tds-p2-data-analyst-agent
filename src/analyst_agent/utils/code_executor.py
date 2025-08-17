import subprocess
import tempfile
import os
import shutil
import uuid
import re
import sys
import logging
from pathlib import Path
from ..configs.settings import CODE_EXEC_TIMEOUT, SANDBOX_IMAGE

# Logger
logger = logging.getLogger(__name__)

# Keep track of running containers for sequential execution
_active_container = None
_work_dir = None


def _extract_imports(code: str):
    """
    Extract top-level imported package names from the Python code.
    Returns a set of package names.
    """
    packages = set()
    import_pattern = r"^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)"
    for line in code.splitlines():
        match = re.match(import_pattern, line)
        if match:
            pkg = match.group(1).split('.')[0]
            if pkg not in sys.stdlib_module_names:
                packages.add(pkg)
    logger.debug(f"[CodeExecutor] Extracted imports: {packages}")
    return packages


def _cleanup_container():
    """Stops and removes the active container, deletes work dir."""
    global _active_container, _work_dir
    if _active_container:
        logger.info(f"[CodeExecutor] Stopping container {_active_container}")
        subprocess.run(["docker", "stop", _active_container], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["docker", "rm", _active_container], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _active_container = None
    if _work_dir and os.path.exists(_work_dir):
        logger.info(f"[CodeExecutor] Removing work directory {_work_dir}")
        shutil.rmtree(_work_dir, ignore_errors=True)
        _work_dir = None


def run_code(code: str, uploaded_files: dict, keep_container_open: bool = False) -> dict:
    """
    Executes provided Python code in an isolated Docker container.
    """
    global _active_container, _work_dir

    try:
        # If no active container yet, create work dir and container
        if _active_container is None:
            _work_dir = Path(tempfile.mkdtemp(prefix="sandbox_"))
            logger.info(f"[CodeExecutor] Created temp workspace: {_work_dir}")

            for fname, fpath in uploaded_files.items():
                shutil.copy(fpath, _work_dir / fname)
                logger.debug(f"[CodeExecutor] Copied file {fname} -> {_work_dir / fname}")

            _active_container = f"sandbox_{uuid.uuid4().hex[:8]}"
            logger.info(f"[CodeExecutor] Starting new container: {_active_container}")

            subprocess.run(
                [
                    "docker", "run", "-dit",
                    "--name", _active_container,
                    "-v", f"{_work_dir}:/workspace",
                    "-w", "/workspace",
                    "--network", "bridge",
                    SANDBOX_IMAGE,
                    "bash"
                ],
                check=True
            )

        #  Step 1: Save the code to the shared workspace
        code_file = _work_dir / "script.py"

        # 🔽 Fix: if code is a list, join it into a single string
        if isinstance(code, list):
            code = "\n\n".join(code)

        code_file.write_text(code, encoding="utf-8")
        logger.debug(f"[CodeExecutor] Saved code to {code_file}")

        # Step 2: Install missing packages
        packages_to_install = _extract_imports(code)
        if packages_to_install:
            logger.info(f"[CodeExecutor] Installing missing packages: {packages_to_install}")
            install_cmd = [
                "docker", "exec", _active_container,
                "pip", "install", "--no-cache-dir", *packages_to_install
            ]
            subprocess.run(
                install_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60
            )

        # Step 3: Execute the code inside the persistent container
        cmd = ["docker", "exec", _active_container, "python", "script.py"]
        logger.info(f"[CodeExecutor] Executing script in container {_active_container}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CODE_EXEC_TIMEOUT
        )

        # Step 4: Cleanup if not persistent
        if not keep_container_open:
            logger.info("[CodeExecutor] Cleaning up after execution")
            _cleanup_container()

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }

    except subprocess.TimeoutExpired:
        logger.error("[CodeExecutor] Execution timed out")
        if not keep_container_open:
            _cleanup_container()
        return {"success": False, "stdout": "", "stderr": "Execution timed out."}

    except Exception as e:
        logger.exception(f"[CodeExecutor] Error during execution: {e}")
        if not keep_container_open:
            _cleanup_container()
        return {"success": False, "stdout": "", "stderr": str(e)}


# 👇 Wrapper Class for compatibility
class CodeExecutor:
    def run(self, code: str, uploaded_files: dict, keep_container_open: bool = False) -> dict:
        return run_code(code, uploaded_files, keep_container_open)

    def cleanup(self):
        _cleanup_container()
