"""
LLM client with API fallback mechanism.
Supports Gemini -> Claude -> OpenAI fallback workflow.
"""
import os
import logging
import json
import time
from typing import Optional, Dict, Any, Tuple, Callable
from ..configs.settings import (
    # API keys
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    NVIDIA_API_KEY,
    # Models (override with env if needed)
    GEMINI_MODEL,
    OPENAI_MODEL,
    NVIDIA_MODEL,
    # Timeouts / retries
    LLM_PER_PROVIDER_TIMEOUT_SEC,
    LLM_MAX_RETRIES,
    LLM_BACKOFF_BASE_SEC,
)

from .cache import get_cache
from openai import OpenAI
from google import genai

logger = logging.getLogger(__name__)


def _sleep_backoff(attempt: int, base: float) -> None:
    # exponential backoff with jitter
    delay = base * (2 ** (attempt - 1))
    delay = min(delay, 8.0)  # cap per hop
    time.sleep(delay * (0.75 + 0.5 * os.urandom(1)[0] / 255.0))


class _Breaker:
    """Tiny circuit breaker per provider."""
    def __init__(self, threshold: int = 3, cooldown_sec: int = 120):
        self.failures = 0
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self.block_until = 0.0

    def record_success(self):
        self.failures = 0
        self.block_until = 0.0

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.block_until = time.time() + self.cooldown_sec

    def is_open(self) -> bool:
        return time.time() < self.block_until


class LLMClient:
    """Multi-API LLM client with fallback mechanism."""
    
    def __init__(self, debug: bool = True):
        self.cache = get_cache()
        self.debug = debug
        
        # Resolve config (env overrides settings)
        self.gemini_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY or "")
        self.openai_key = os.getenv("OPENAI_API_KEY", OPENAI_API_KEY or "")
        self.nvidia_key = os.getenv("NVIDIA_API_KEY", NVIDIA_API_KEY or "")

        self.gemini_model = os.getenv("GEMINI_MODEL", GEMINI_MODEL or "gemini-2.5-flash")
        self.openai_model = os.getenv("OPENAI_MODEL", OPENAI_MODEL or "gpt-5")
        self.nvidia_model = os.getenv("NVIDIA_MODEL", NVIDIA_MODEL or "nvidia/llama-3.3-nemotron-super-49b-v1.5")

        self.per_provider_timeout = int(os.getenv("LLM_PER_PROVIDER_TIMEOUT_SEC", str(LLM_PER_PROVIDER_TIMEOUT_SEC or 30)))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", str(LLM_MAX_RETRIES or 2)))
        self.backoff_base = float(os.getenv("LLM_BACKOFF_BASE_SEC", str(LLM_BACKOFF_BASE_SEC or 1.0)))


        # Initialize API clients
        self._init_clients()

        # Circuit breakers
        self._breakers = {
            "gemini": _Breaker(),
            "openai": _Breaker(),
            "nvidia": _Breaker(),
        }

    
    def _init_clients(self):
        """Initialize all API clients"""
        try:
            # Gemini
            self.gemini_client = genai.Client()
            if self.debug:
                print("[LLMClient] Gemini client initialized")
        except Exception as e:
            if self.debug:
                print(f"[LLMClient] Gemini initialization failed: {e}")
            self.gemini_client = None
        

        # OpenAI
        self.openai_client = None
        if self.openai_key:
            try:
                # set a default timeout; per-call override still possible
                self.openai_client = OpenAI()
                if self.debug:
                    logger.info("[LLMClient] OpenAI ready")
            except Exception as e:
                logger.warning(f"[LLMClient] OpenAI init failed: {e}")

        # NVIDIA (OpenAI-compatible)
        self.nv_client = None
        if self.nvidia_key:
            try:
                self.nv_client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=self.nvidia_key,
                    timeout=self.per_provider_timeout
                )
                if self.debug:
                    logger.info("[LLMClient] NVIDIA (OpenAI-compatible) ready")
            except Exception as e:
                logger.warning(f"[LLMClient] NVIDIA init failed: {e}")


    def call_gemini(self, prompt: str) -> Optional[str]:
        """Call Gemini API"""
        if not self.gemini_client:
            return None
        cache_key = f"llm:gemini:{hash((prompt, self.gemini_model))}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                
                # Gemini SDK does not accept per-call timeout directly; rely on overall budget + retries.
               
                api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
                resp = self.gemini_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )
                
                # Extract plain text
                text = getattr(resp, "text", None)
                if not text and getattr(resp, "candidates", None):
                    parts = [getattr(p, "text", "") or "" for p in resp.candidates[0].content.parts]
                    text = "".join(parts).strip()
                if text:
                    self.cache.set(cache_key, text, expire=900)
                    return text
            except Exception as e:
                logger.warning("[Gemini] attempt %d failed: %s", attempt, e)
                if attempt <= self.max_retries:
                    _sleep_backoff(attempt, self.backoff_base)
        return None


    def call_nvidia(self, prompt: str) -> Optional[str]:
        """
        Call NVIDIA's API for LLM inference using OpenAI-compatible client.
        Efficiently retrieves the full streamed response.
        """
        if not self.nv_client:
            return None
        cache_key = f"llm:nvidia:{hash((prompt, self.nvidia_model))}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                completion = self.nv_client.chat.completions.create(
                    model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
                    messages=[{"role": "system", "content": prompt}],
                    temperature=0.3,
                    top_p=0.95,
                    max_tokens=65536,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stream=True,
                    timeout=self.per_provider_timeout
                )
                # Efficiently collect the whole answer from streaming chunks
                buf = []
                
                for chunk in completion:
                    
                    delta = chunk.choices[0].delta
                    if delta.content and getattr(delta, "content", None):
                        buf.append(delta.content)
                text = "".join(buf).strip()
                if text:
                    self.cache.set(cache_key, text, expire=900)
                    return text
            except Exception as e:
                logger.warning("[NVIDIA] attempt %d failed: %s", attempt, e)
                if attempt <= self.max_retries:
                    _sleep_backoff(attempt, self.backoff_base)
        return None


            
    def call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API"""
        if not self.openai_client:
            return None
        
        cache_key = f"llm:openai:{hash((prompt, self.openai_model))}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-5",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.2,
                    timeout=self.per_provider_timeout  # SDK v1 supports 'timeout' per call
                )
        
                if response  and  response.choices:
                    text = response.choices[0].message.content
                    if text:
                        self.cache.set(cache_key, text, expire=900)
                        return text
            except Exception as e:
                logger.warning("[OpenAI] attempt %d failed: %s", attempt, e)
                if attempt <= self.max_retries:
                    _sleep_backoff(attempt, self.backoff_base)
        return None
    

    

    def chat(self, task_prompt: str, files: Optional[Dict[str, str]] = None) -> str:
        """
        Legacy method for backward compatibility
        """
        file_info = ""
        if files:
            file_info = "\n".join([f"- {name}" for name in files.keys()])

        full_prompt = (
            "You are a senior data analyst AI.\n"
            "Read the user's question carefully (from question.txt). The user may specify the exact output format.\n"
            "You MUST return one of the following STRICT JSON objects (no markdown fences):\n"
            "1) {\"final answer\": <string_or_JSON>}\n"
            "OR\n"
            "2) {\"code\": <python_string>, \"analysis\": <optional short string>}\n\n"
            "Rules:\n"
            "- If you need to scrape or analyze data, return runnable Python in the \"code\" field only.\n"
            "- If the user asked for a plain answer, return ONLY \"final answer\" with the answer.\n"
            "- Do not add any extra keys, explanations, or code fences.\n"
            "- Keep outputs compact.\n\n"
            f"Task:\n{task_prompt}\n\n"
            f"Files provided (names only):\n{file_info}\n"
        )

        deadline = time.time() + self.total_budget
        # Cache lookup (per-provider cache happens inside each call)
        # We also keep a global cache because any provider's correct response is acceptable
        global_cache_key = f"llm:any:{hash((full_prompt, tuple(sorted(files.keys())) if files else ())) }"
        cached = self.cache.get(global_cache_key)
        if cached:
            return cached
        
        # Provider order
        providers: Tuple[Tuple[str, Callable[[str, float], Optional[str]]], ...] = (
            ("gemini", self.call_gemini),
            ("openai", self.call_openai),
            ("nvidia", self.call_nvidia),
        )
        
        for name, fn in providers:
            if self._breakers[name].is_open():
                logger.warning(f"[LLMClient] Skipping {name.upper()} (circuit open)")
                continue

            
            

            logger.info("[LLMClient] Trying %s (time left ~%.1fs)", name.upper())
            try:
                out = fn(full_prompt, deadline)
                if out and self._is_strict_json(out):
                    self._breakers[name].record_success()
                    # Store global cache for this prompt regardless of provider
                    self.cache.set(f"{global_cache_key}", out, expire=1800)
                    return out
                else:
                    self._breakers[name].record_failure()
                    logger.warning("[LLMClient] %s returned empty or non-JSON", name.upper())
            except Exception as e:
                self._breakers[name].record_failure()
                logger.exception("[LLMClient] %s call error: %s", name.upper(), e)

        logger.error("[LLMClient] All providers failed or returned invalid output.")
        return ""


    @staticmethod
    def _is_strict_json(text: str) -> bool:
        if not text or not text.strip():
            return False
        t = text.strip()
        # No markdown fences
        if t.startswith("```") or t.endswith("```"):
            return False
        try:
            obj = json.loads(t)
        except json.JSONDecodeError:
            return False
        if not isinstance(obj, dict):
            return False
        # only allowed keys
        allowed1 = set(["final answer"])
        allowed2 = set(["code", "analysis"])
        keys = set(obj.keys())
        if keys == allowed1:
            # final answer must be string or JSON-serializable
            return True
        if "code" in keys and keys.issubset(allowed2) and isinstance(obj["code"], str):
            return True
        return False



# Global client instance
_llm_client = LLMClient(debug=True)

def llm_chat(prompt: str, files: Optional[Dict[str, str]] = None) -> str:
    """Primary entry point for orchestrator to talk to the LLM."""
    return _llm_client.chat(prompt, files)
