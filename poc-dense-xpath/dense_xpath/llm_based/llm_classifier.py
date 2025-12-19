"""
LLM Classifier - Uses LLM to determine if a node matches a semantic query.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from client import OpenAIClient, get_client


class LLMClassifier:
    """
    Classifies whether a node matches a semantic description query using LLM.
    """
    
    PROMPT_PATH = Path(__file__).parent.parent.parent / "store" / "prompts" / "llm_classifier.txt"
    
    def __init__(self, client: OpenAIClient = None):
        """
        Initialize the classifier.
        
        Args:
            client: Optional OpenAI client. If not provided, one will be created.
        """
        self._client = client
        self._prompt_template = None  # Lazy load
    
    @property
    def client(self) -> OpenAIClient:
        """Lazy load the OpenAI client"""
        if self._client is None:
            self._client = get_client()
        return self._client
    
    @property
    def prompt_template(self) -> str:
        """Lazy load the prompt template from file"""
        if self._prompt_template is None:
            with open(self.PROMPT_PATH, "r") as f:
                self._prompt_template = f.read()
        return self._prompt_template
    
    def _build_prompt(self, node_info: str, query: str) -> str:
        """
        Build the prompt by replacing placeholders.
        
        Args:
            node_info: String representation of the node information
            query: The semantic query to match against
            
        Returns:
            Formatted prompt string
        """
        prompt = self.prompt_template
        prompt = prompt.replace("<NODE_INFO>", node_info)
        prompt = prompt.replace("<QUERY>", query)
        return prompt
    
    def classify(self, node_info: str, query: str) -> bool:
        """
        Determine if a node matches the semantic query.
        
        Args:
            node_info: String representation of the node (should include description)
            query: The semantic query to match against
            
        Returns:
            True if the node matches the query, False otherwise
        """
        prompt = self._build_prompt(node_info, query)
        
        response = self.client.complete(
            prompt,
            temperature=0.0,
            max_tokens=10
        )
        
        result = response.strip().lower()
        return result == "true"
    
    def classify_node(self, node: dict, query: str) -> bool:
        """
        Determine if a node dict matches the semantic query.
        
        Args:
            node: Node dictionary with 'description' and other fields
            query: The semantic query to match against
            
        Returns:
            True if the node matches the query, False otherwise
        """
        node_info = self._node_to_string(node)
        return self.classify(node_info, query)
    
    def _node_to_string(self, node: dict) -> str:
        """
        Convert a node dict to a string representation.
        
        Args:
            node: Node dictionary
            
        Returns:
            String representation of the node
        """
        parts = []
        
        if "type" in node:
            parts.append(f"Type: {node['type']}")
        
        if "id" in node:
            parts.append(f"ID: {node['id']}")
        
        # Handle description - could be at top level or in attrs
        description = node.get("description")
        if description is None and "attrs" in node:
            description = node["attrs"].get("description")
        
        if description:
            parts.append(f"Description: {description}")
        else:
            parts.append("Description: (none)")
        
        return "\n".join(parts)


# Convenience function
def is_node_related(node: dict, query: str, client: OpenAIClient = None) -> bool:
    """
    Check if a node matches a semantic query.
    
    Args:
        node: Node dictionary
        query: Semantic query to match
        client: Optional OpenAI client
        
    Returns:
        True if the node matches the query
    """
    classifier = LLMClassifier(client)
    return classifier.classify_node(node, query)


if __name__ == "__main__":
    # Quick test
    classifier = LLMClassifier()
    
    test_node = {
        "type": "POI",
        "id": "poi_1",
        "description": "A cozy Italian trattoria serving authentic pasta and wood-fired pizza"
    }
    
    test_queries = [
        "italian",
        "japanese",
        "pasta",
        "cheap",
    ]
    
    print("Testing LLM Classifier")
    print("=" * 60)
    print(f"Node: {test_node}")
    print("=" * 60)
    
    for query in test_queries:
        result = classifier.classify_node(test_node, query)
        print(f"Query: '{query}' -> {result}")

