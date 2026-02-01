import os
import yaml
from pathlib import Path
from typing import Tuple, Dict, Any
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def load_config() -> dict:
    """Load configuration from config.yaml with env var substitution."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        # Read file content
        content = f.read()
        
    # Expand environment variables using os.path.expandvars
    # This handles ${VAR} syntax
    expanded_content = os.path.expandvars(content)
    
    return yaml.safe_load(expanded_content)


@dataclass
class TokenUsage:
    """Token usage statistics from an API call."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }


@dataclass
class CompletionResult:
    """Result from a completion call including response and token usage."""
    content: str
    usage: TokenUsage
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "usage": self.usage.to_dict()
        }


class OpenAIClient:
    """OpenAI API client wrapper"""
    
    def __init__(self, config: dict = None):
        if config is None:
            config = load_config()
        
        self.config = config["openai"]
        self.client = OpenAI(api_key=self.config["api_key"])
        self.model = self.config.get("model", "gpt-4")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 4096)
    
    def chat(self, messages: list[dict], **kwargs) -> str:
        """Send a chat completion request"""
        response = self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return response.choices[0].message.content
    
    def chat_with_usage(self, messages: list[dict], **kwargs) -> CompletionResult:
        """Send a chat completion request and return response with token usage."""
        response = self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        
        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens
        )
        
        return CompletionResult(
            content=response.choices[0].message.content,
            usage=usage
        )
    
    def complete(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """Simple completion with optional system prompt"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)
    
    def complete_with_usage(self, prompt: str, system_prompt: str = None, **kwargs) -> CompletionResult:
        """Simple completion with optional system prompt, returns response with token usage."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat_with_usage(messages, **kwargs)


# Convenience function to get a client instance
def get_client() -> OpenAIClient:
    """Get an OpenAI client instance"""
    return OpenAIClient()


if __name__ == "__main__":
    # Quick test
    client = get_client()
    response = client.complete("Say hello in one word.")
    print(f"Response: {response}")

