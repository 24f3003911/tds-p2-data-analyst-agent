import re
import json
from typing import Dict, Any, List, Optional, Tuple

class LLMParser:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def parse_response(self, response: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "raw_response": response,
            "type": "continuation",
            "content": "",
            "code_blocks": [],
            "final_answer": None,
            "analysis": None,
            "delegation": None,
            "metadata": {
                "requires_followup": False,
            },
        }

        if not response or not response.strip():
            result["metadata"]["requires_followup"] = True
            return result

        text = response.strip()

        # 1. Try parsing as JSON
        cleaned = self._strip_backticks_if_needed(text)
        try:
            parsed = json.loads(cleaned)
            # Handle final answer format
            if isinstance(parsed, dict):
                if "final answer" in parsed:
                    result["type"] = "final_answer"
                    result["final_answer"] = parsed["final answer"]
                    result["content"] = parsed["final answer"]
                    return result
                # Handle code+analysis format
                elif "code" in parsed:
                    result["type"] = "code"
                    code_content = parsed["code"]
                    # 🔽 Normalize into a list of strings
                    if isinstance(code_content, str):
                        result["code_blocks"] = [code_content]
                    elif isinstance(code_content, list):
                        result["code_blocks"] = [str(c) for c in code_content]
                    else:
                        result["code_blocks"] = [str(code_content)]

                    result["analysis"] = parsed.get("analysis", None)
                    result["content"] = "\n\n".join(result["code_blocks"])
                    return result
                
            # fallback: if json but not expected keys, treat as continuation
        except json.JSONDecodeError:
            pass

        # 2. Fallback: try to extract code or answer from text
        # (Use regexes only if you expect non-JSON answers)
        answer_match = re.search(r'\{[^\}]*"final answer"\s*:\s*"([^"]+)"[^\}]*\}', text)
        if answer_match:
            val = answer_match.group(1)
            result["type"] = "final_answer"
            result["final_answer"] = val
            result["content"] = val
            return result

        code_match = re.search(r'\{[^\}]*"code"\s*:\s*"([^"]+)"[^\}]*\}', text, re.DOTALL)
        analysis_match = re.search(r'\{[^\}]*"analysis"\s*:\s*"([^"]+)"[^\}]*\}', text, re.DOTALL)
        if code_match:
            code_val = code_match.group(1)
            analysis_val = analysis_match.group(1) if analysis_match else None
            result["type"] = "code"
            result["code_blocks"] = [code_val]
            result["analysis"] = analysis_val
            result["content"] = code_val
            return result

        # 3. Otherwise, treat as continuation
        result["content"] = text
        result["metadata"]["requires_followup"] = True
        return result

    def _strip_backticks_if_needed(self, text: str) -> str:
        """
        Remove Markdown-style code fences (``` or ```json) from LLM responses.
        """
        if not text:
            return ""

        t = text.strip()

        # Remove starting code fence
        if t.lower().startswith("```json"):
            t = t[7:].lstrip("\n\r ")  # remove "```json" + optional newline
        elif t.startswith("```"):
            t = t[3:].lstrip("\n\r ")  # remove "```" + optional newline

        # Remove trailing code fence
        if t.endswith("```"):
            t = t[:-3].rstrip("\n\r ")

        return t.strip()

def parse_llm_response(text: str) -> Dict[str, Any]:
    parser = LLMParser(verbose=True)
    return parser.parse_response(text)
