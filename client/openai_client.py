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
        config = yaml.safe_load(f)
        
    key = config.get("openai", {}).get("api_key")
    
    # Manually substitute API key if it contains the placeholder
    if key and "${OPENAI_API_KEY}" in key:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Try to find .env file explicitly if not found
            env_path = Path(__file__).parent.parent / ".env"
            load_dotenv(dotenv_path=env_path)
            api_key = os.getenv("OPENAI_API_KEY")
            
        if api_key:
            config["openai"]["api_key"] = api_key
        else:
            print("Warning: OPENAI_API_KEY not found in environment or .env file")
            
    return config


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
    
    # Models that use max_completion_tokens instead of max_tokens
    NEW_API_MODELS = ["gpt-5", "o1", "o3"]
    
    # Models that don't support custom temperature (only default=1)
    NO_TEMPERATURE_MODELS = ["gpt-5-mini", "gpt-5-nano", "o1-mini", "o1-preview", "o3-mini"]
    
    def __init__(self, config: dict = None):
        if config is None:
            config = load_config()
        
        self.config = config["openai"]
        self.client = OpenAI(api_key=self.config["api_key"])
        self.model = self.config.get("model", "gpt-4")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 4096)
    
    def _uses_new_api(self, model: str) -> bool:
        """Check if model uses the new API with max_completion_tokens."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.NEW_API_MODELS)
    
    def _supports_temperature(self, model: str) -> bool:
        """Check if model supports custom temperature setting."""
        model_lower = model.lower()
        return not any(model_lower.startswith(prefix) for prefix in self.NO_TEMPERATURE_MODELS)
    
    def _build_completion_kwargs(self, model: str, temperature: float, max_tokens: int) -> dict:
        """Build kwargs for completion API, handling model-specific parameters."""
        kwargs = {"model": model}
        
        # Only add temperature if the model supports it
        if self._supports_temperature(model):
            kwargs["temperature"] = temperature
        
        # Use appropriate token limit parameter based on model
        if self._uses_new_api(model):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
        
        return kwargs
    
    def chat(self, messages: list[dict], **kwargs) -> str:
        """Send a chat completion request"""
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        completion_kwargs = self._build_completion_kwargs(model, temperature, max_tokens)
        completion_kwargs["messages"] = messages
        
        response = self.client.chat.completions.create(**completion_kwargs)
        return response.choices[0].message.content
    
    def chat_with_usage(self, messages: list[dict], **kwargs) -> CompletionResult:
        """Send a chat completion request and return response with token usage."""
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        completion_kwargs = self._build_completion_kwargs(model, temperature, max_tokens)
        completion_kwargs["messages"] = messages
        
        response = self.client.chat.completions.create(**completion_kwargs)
        
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

