import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

BASE_PERSONA = os.getenv("DEFAULT_PERSONA", "You are a helpful assistant.")

def build_system_prompt(use_thinking: bool = False, use_search: bool = False) -> str:
    prompt = BASE_PERSONA
    if use_thinking:
        prompt += "\n--- Thinking Directive: Outline reasoning in italics before answering. ---"
    if use_search:
        prompt += "\n--- Web Search Directive: Summarize search results and cite sources. ---"
    return prompt

def prepare_model_messages(
    channel_history: List[Dict],
    query: str,
    search_results: List[Dict],
    *, 
    file_data: Optional[str] = None,
    use_thinking: bool = False
) -> List[Dict]:
    
    use_search_in_prompt = bool(search_results)
    system_prompt = build_system_prompt(use_thinking, use_search_in_prompt)
    
    messages = [{"role": "system", "content": system_prompt}]
    
    if channel_history:
        lines = [f"{m.get('username') or 'User'}: {m.get('content')}" for m in channel_history]
        messages.append({"role": "system", "content": "Recent memory:\n" + "\n".join(lines)})

    if search_results:
        res_lines = [f"- {s.get('title')} ({s.get('link')}): {s.get('snippet')}" for s in search_results]
        messages.append({"role": "system", "content": "Web search context:\n" + "\n".join(res_lines)})
    
    user_message = {"role": "user", "content": query}
    if file_data:
        user_message["images"] = [file_data]
        
    messages.append(user_message)
    return messages