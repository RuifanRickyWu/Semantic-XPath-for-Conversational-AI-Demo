"""Plan-content semantic XPath query generation service."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from services.query_generation.base_query_generation_service import (
    BasePromptQueryGenerationService,
)


_BASE_DIR = Path(__file__).resolve().parents[2]
_PROMPT_PATH = (
    _BASE_DIR
    / "prompts"
    / "query_generation"
    / "plan_content_query_generator.txt"
)


class PlanContentQueryGenerationService(BasePromptQueryGenerationService):
    """Generates semantic XPath queries over plan-content XML."""

    scope: str = "plan_content"

    def __init__(
        self,
        client,
        prompt_path: Optional[Path] = None,
        max_retries: int = 3,
    ) -> None:
        super().__init__(
            client=client,
            prompt_path=prompt_path or _PROMPT_PATH,
            max_retries=max_retries,
        )
