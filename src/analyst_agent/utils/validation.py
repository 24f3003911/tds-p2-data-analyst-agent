"""
Validation utilities for the Data Analyst Agent.
"""
import re
from typing import List, Dict, Any


def is_valid_output(output: str) -> bool:
    """Check if code execution output is valid (no errors)."""
    if not output or not output.strip():
        return False

    error_indicators = [
        "traceback (most recent call last):",
        "error:",
        "exception:",
        "syntaxerror:",
        "nameerror:",
        "valueerror:",
        "typeerror:",
        "importerror:",
        "filenotfounderror:",
        "keyerror:",
        "indexerror:",
        "attributeerror:"
    ]

    output_lower = output.strip().lower()
    lines = output_lower.splitlines()

    # Reject if error is in first few lines (likely a failure)
    for idx, line in enumerate(lines):
        if any(err in line for err in error_indicators) and idx < 5:
            return False

    return True


def extract_python_code(text: str) -> List[str]:
    """Extract Python code blocks from text."""
    python_pattern = r"```python\s*(.*?)```"
    generic_pattern = r"```\s*(.*?)```"

    code_blocks = re.findall(python_pattern, text, re.DOTALL)
    if not code_blocks:
        code_blocks = re.findall(generic_pattern, text, re.DOTALL)

    return [code.strip() for code in code_blocks if code.strip()]


def validate_file_upload(filename: str, content_length: int, allowed_extensions: List[str], max_size: int) -> Dict[str, Any]:
    result = {'valid': True, 'errors': [], 'warnings': []}

    if not filename:
        result['valid'] = False
        result['errors'].append("Filename is required")
        return result

    file_ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
    if file_ext not in [ext.lower() for ext in allowed_extensions]:
        result['valid'] = False
        result['errors'].append(f"File extension '{file_ext}' not allowed. Allowed: {allowed_extensions}")

    if content_length > max_size:
        result['valid'] = False
        result['errors'].append(f"File size {content_length} bytes exceeds maximum {max_size} bytes")

    if content_length > max_size * 0.8:
        result['warnings'].append(f"File is large ({content_length} bytes), processing may be slow")

    return result


def sanitize_filename(filename: str) -> str:
    filename = filename.split('/')[-1].split('\\')[-1]
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    filename = filename.strip(' .')
    return filename if filename else "untitled"


def validate_llm_response(response: str) -> Dict[str, Any]:
    result = {
        'valid': True,
        'has_code': False,
        'has_final_answer': False,
        'has_delegation': False,
        'errors': [],
        'code_blocks_count': 0
    }

    if not response or not response.strip():
        result['valid'] = False
        result['errors'].append("Empty response")
        return result

    if '```' in response:
        result['has_code'] = True
        result['code_blocks_count'] = response.count('```') // 2

    if 'final answer:' in response.lower():
        result['has_final_answer'] = True

    if 'call_llm:' in response.lower():
        result['has_delegation'] = True

    if not (result['has_code'] or result['has_final_answer'] or result['has_delegation']):
        result['warnings'] = result.get('warnings', [])
        result['warnings'].append("Response doesn't contain clear action")

    return result
