import json
import hashlib
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.llm_intepreter import resolve_pointer, get_entity_details


CACHE_DIR = Path(__file__).parent.parent / "cache"


def ensure_cache_dir():
    CACHE_DIR.mkdir(exist_ok=True)


def get_cache_key(request: str) -> str:
    """Generate a cache key from the request."""
    return hashlib.md5(request.lower().strip().encode()).hexdigest()[:12]


def load_from_cache(request: str) -> dict:
    """Try to load a cached result for this request."""
    ensure_cache_dir()
    cache_key = get_cache_key(request)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)
    return None


def save_to_cache(request: str, result: dict):
    """Save result to cache."""
    ensure_cache_dir()
    cache_key = get_cache_key(request)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    result["cached_at"] = datetime.now().isoformat()
    result["cache_key"] = cache_key
    
    with open(cache_file, "w") as f:
        json.dump(result, f, indent=2)
    
    return cache_file


def process_request(request: str, use_cache: bool = True) -> dict:
    """
    Process a user request to find related POIs/restaurants.
    
    Args:
        request: Natural language request
        use_cache: Whether to use cached results if available
        
    Returns:
        dict with matched entities and details
    """
    # Check cache first
    if use_cache:
        cached = load_from_cache(request)
        if cached:
            cached["from_cache"] = True
            return cached
    
    # Call LLM interpreter
    result = resolve_pointer(request)
    
    # Enrich with entity details
    if result.get("matched_ids"):
        result["entity_details"] = get_entity_details(result["matched_ids"])
    
    result["from_cache"] = False
    
    # Save to cache
    cache_file = save_to_cache(request, result)
    result["cache_file"] = str(cache_file)
    
    return result


def interactive_mode():
    """Run in interactive mode, continuously accepting requests."""
    print("=" * 60)
    print("Toronto Itinerary Pointer Resolver")
    print("=" * 60)
    print("Enter your requests to find related POIs/restaurants.")
    print("Type 'quit' or 'exit' to stop.\n")
    
    while True:
        try:
            request = input("\n> Enter request: ").strip()
            
            if not request:
                continue
            
            if request.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            
            print("\nProcessing...")
            result = process_request(request)
            
            print("\n--- RESULTS ---")
            print(f"From cache: {result.get('from_cache', False)}")
            print(f"Confidence: {result.get('confidence', 'unknown')}")
            print(f"Matched IDs: {result.get('matched_ids', [])}")
            print(f"Reasoning: {result.get('reasoning', 'N/A')}")
            
            if result.get("entity_details"):
                print("\n--- MATCHED ENTITIES ---")
                for eid, details in result["entity_details"].items():
                    print(f"\n[{eid}] {details.get('poi_name', 'Unknown')}")
                    print(f"  Day: {details.get('day', 'N/A')}")
                    print(f"  Time: {details.get('time_block', 'N/A')}")
                    print(f"  Description: {details.get('description', 'N/A')}")
            
            if result.get("error"):
                print(f"\nError: {result['error']}")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    interactive_mode()

