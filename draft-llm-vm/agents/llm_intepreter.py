from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.openai_client import make_request
from util.data_parser import (
    parse_json_response,
    get_related_entities,
    get_entity_details,
    get_entities_json,
    load_manifest,
)


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    prompt_path = PROMPTS_DIR / f"{name}.txt"
    with open(prompt_path, "r") as f:
        return f.read()


def resolve_pointer(user_request: str) -> dict:
    """
    Use LLM to determine which POI(s) or restaurant(s) are related to the user request.
    
    Args:
        user_request: Natural language request from user
        
    Returns:
        dict with matched entity IDs, related entities, and reasoning
    """
    manifest = load_manifest()
    entities_json = get_entities_json()
    
    system_prompt = load_prompt("pointer_resolve_system")
    user_prompt_template = load_prompt("pointer_resolve_user")
    
    user_prompt = user_prompt_template.format(
        user_request=user_request,
        manifest=manifest,
        entities=entities_json
    )

    response = make_request(user_prompt, system_prompt)
    
    # Parse the JSON response using data_parser utility
    default_error = {
        "matched_ids": [],
        "reasoning": "Failed to parse LLM response",
        "confidence": "low"
    }
    
    result, error = parse_json_response(response, default=default_error)
    
    if error:
        result["error"] = error
    
    # Enrich result with related entity details
    related_entities = get_related_entities(result)
    result["related_entities"] = related_entities
    
    result["raw_response"] = response
    result["user_request"] = user_request
    
    return result
