import os
from typing import Dict, Any, List, Optional
from .utils.llm_clients import LLMClient
from .llm_parser import parse_llm_response
import time
import concurrent.futures

GENERIC_SYSTEM_PROMPT = """
You are a highly capable data analyst agent.

You will receive:
- A primary question (question.txt or provided text)
- Optional additional files (data, SQL DB dumps, Parquet files, etc.)

Your objectives:
1. Read and interpret the question carefully.
2. If the question contains one or more URLs:
   - Determine the best way to retrieve and parse its content:
     - Use requests + BeautifulSoup for static HTML
     - Use httpx for APIs
     - Use playwright or selenium for dynamic JS-heavy pages
   - Handle pagination, nested links, and subpages if needed.
   - Avoid hardcoding to a specific site — make it domain-agnostic.
3. Handle any type of data source in the files:
   - CSV, JSON, Parquet, SQL database connections, Excel, etc.
4. Break down the task into subtasks:
   - If a subtask requires code, write fully runnable Python 3.11 code.
   - Only output code blocks when code is required.
5. If you cannot perform a subtask yourself, you may "call" another specialist LLM.
6. After running code and processing results, compose the final user-facing answer.
IMPORTANT: 
You need to understand that as the question is received by an api, the same api you are interacting with, 
there are certain limitations to the kind of data that this api can process. So do not respond with extra explanations or inferences.
There are two modes of answer: the final answer OR code for execution
When returning the final answer, mention "final answer: " before the actual answer. 
do not add any other input or conclusion before or after. just simple json object- {"final answer": *THE ACTUAL ANSWER IN THE CORRECT FORMAT*}
when returning code for execution, return in json format with two properties - the code and the analysis. 
"code" is associated with the code blocks you want me to run and 
"analysis": should contain text describing progress made so far with respect to solving the problem:
{
"code":*the code*,
"analysis": *your analysis and progress so far*
}
Please do not send extra explanations. Do the analysis on your own and just return the requested data, except when sending back code,
you can describe your progress and analysis next to "analysis" in the Json object. 
Also try to answer within 30-40 seconds

"""


class LLMOrchestrator:
    def __init__(self, loader, executor, debug: bool = True):
        self.loader = loader
        self.executor = executor
        self.debug = debug
        self.llm_client = LLMClient(debug=debug)
        self.max_iterations = 9  # Prevent infinite loops
        self.global_budget_sec = 300  # 5 min per API

    def _call_with_timeout(self, fn, prompt, timeout=60):
        """Run fn(prompt) with timeout enforcement."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn, prompt)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                if self.debug:
                    print(f"[LLMOrchestrator] {fn.__name__} timed out after {timeout}s")
                return None
    

    def feedback_loop(self, first_prompt: str, file_map: Dict[str, str]) -> Dict[str, Any]:
        """
        Main feedback loop that tries Gemini -> Claude -> OpenAI in sequence
        """
        apis = ['nvidia','gemini','openai']
        
        for api in apis:
            if self.debug:
                print(f"\n[LLMOrchestrator] Trying {api.upper()} API...")
            
            result = self._run_api_loop(api, first_prompt, file_map)
            if result["success"]:
                return result
            
            if self.debug:
                print(f"[LLMOrchestrator] {api.upper()} failed, trying next API...")
        
        # All APIs failed
        return {
            "success": False,
            "error": "All APIs (Gemini, Nvidia, OpenAI) failed to provide a response",
            "final_answer": None
        }

    def _run_api_loop(self, api_name: str, initial_prompt: str, file_map: Dict[str, str]) -> Dict[str, Any]:
        """
        Run the feedback loop for a specific API
        """
        history: List[str] = []
        current_prompt = initial_prompt
        iteration = 0
        deadline = time.time() + self.global_budget_sec
        
        while iteration < self.max_iterations:
            if time.time() >= deadline:
                return {"success": False, "error": f"Global deadline exceeded for {api_name}", "final_answer": None}

            iteration += 1
            if self.debug:
                print(f"\n[LLMOrchestrator] {api_name.upper()} - Iteration {iteration}")
                print(f"[LLMOrchestrator] Prompt preview: {current_prompt[:200]}...")
            
            if api_name == "openai":
                llm_output = self._call_with_timeout(self.llm_client.call_openai, current_prompt, timeout=60)
            elif api_name == "nvidia":
                llm_output = self._call_with_timeout(self.llm_client.call_nvidia, current_prompt, timeout=60)
            elif api_name == "gemini":
                llm_output = self._call_with_timeout(self.llm_client.call_gemini, current_prompt, timeout=60)
            else:
                return {"success": False, "error": f"Unknown API: {api_name}"}
            
            if not llm_output:
                if self.debug:
                    print(f"[LLMOrchestrator] {api_name.upper()} returned None, switching API...")
                return {"success": False, "error": f"{api_name} API returned None"}
            
            if self.debug:
                print(f"[LLMOrchestrator] {api_name.upper()} raw output: {llm_output[:200]}...")
            
            # Parse LLM output
            parsed = parse_llm_response(llm_output)
            
            if self.debug:
                print(f"[LLMOrchestrator] Parsed type: {parsed['type']}")
            
            # Handle different response types
            if parsed["type"] == "final_answer":
                return {
                    "success": True,
                    "final_answer": parsed["content"],
                    "api_used": api_name,
                    "iterations": iteration,
                    "parsed": parsed,
                    "raw_output": llm_output
                }
            
            elif parsed["type"] == "code" and parsed["code_blocks"]:
                if self.debug:
                    print(f"[LLMOrchestrator] Executing {len(parsed['code_blocks'])} code blocks...")
                
                # Execute the code
                exec_results = self.executor.run(parsed["code_blocks"], file_map)
                history.append(
                    f"Iteration {iteration}\n"
                    f"Model output:\n{llm_output}\n\n"
                    f"Execution Results:\n{exec_results}\n"
                )
                # Prepare feedback prompt for next iteration
                feedback_prompt = self._build_feedback_prompt(
                    initial_prompt, 
                    history
                )
                current_prompt = feedback_prompt
                
                if self.debug:
                    print(f"[LLMOrchestrator] Code execution completed, continuing loop...")
            
            else:
                # Unhandled response type, treat as continuation
                if self.debug:
                    print(f"[LLMOrchestrator] Unhandled response type: {parsed['type']}")
                
                # Build continuation prompt
                current_prompt = f"{initial_prompt}\n\nPrevious response:\n{llm_output}\n\nPlease provide the final answer or executable code."
        
        return {
            "success": False,
            "error": f"Maximum iterations ({self.max_iterations}) reached for {api_name}",
            "final_answer": None
        }

    def _build_feedback_prompt(self, original_prompt: str, history: List[str]) -> str:
        """
        Build a feedback prompt after code execution
        """
        feedback = f"""
Original Question:
{original_prompt}

Here is the full history of attempts so far:
{"\n\n---\n\n".join(history)}

Now, based on this history, please either:
1. Provide the **final answer** in JSON format: {{ "final answer": ... }}
2. OR, if more work is needed, provide only the next incremental code block in the format: {{"code": <code to be executed>, 
"analysis": <brief description of further analysis made by you>}}

But try to construct efficient code at once. 
And if the received input is satisfactory, try to analyze and give the final answer at the earliest according to the format mentioned previously.
"""
        return feedback

    def run_analysis(self, file_map: Dict[str, str], question_text: str) -> Dict[str, Any]:
        """
        Build prompt for LLM, call it, parse response, and possibly execute code.
        """
        # Build the full prompt
        prompt_str = (
            f"{GENERIC_SYSTEM_PROMPT}\n\n"
            f"Question: {question_text}\n\n"
            f"Files available for context:\n{list(file_map.keys())}"
        )

        if self.debug:
            print("\n[LLMOrchestrator] Starting analysis...")
            print(f"[LLMOrchestrator] Prompt preview: {prompt_str[:500]}...")
        
        result = self.feedback_loop(prompt_str, file_map)
        return result
    
    def handle_request(self, uploaded_files: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
        """
        Main entry point: loads files, sends prompt to LLM, parses and returns results.
        """
        if self.debug:
            print(f"\n[LLMOrchestrator] Received question: {question}")
            print(f"[LLMOrchestrator] Uploaded file count: {len(uploaded_files)}")

        file_map = self.loader.load_files(uploaded_files)
        if self.debug:
            print(f"[LLMOrchestrator] Loaded files: {list(file_map.keys())}")

        return self.run_analysis(file_map, question)