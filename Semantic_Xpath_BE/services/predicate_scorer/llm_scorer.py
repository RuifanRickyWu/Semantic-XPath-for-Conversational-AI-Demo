"""LLM-based predicate scorer using OpenAI."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from clients.openai_client import OpenAIClient

from .base import BatchScoringResult, PredicateScorer, ScoringResult


class LLMPredicateScorer(PredicateScorer):
    """Score node descriptions against predicates using an LLM."""

    def __init__(self, client=None, traces_path=None):
        self._client = client or OpenAIClient()
        self._traces_path = traces_path

    def score_batch(self, nodes, predicate):
        if not nodes:
            return BatchScoringResult(predicate=predicate, results=[])

        descriptions = [
            n.get("description", "") or n.get("name", "") or str(n.get("type", "?"))
            for n in nodes
        ]

        prompt = self._build_prompt(descriptions, predicate)
        messages = [
            {"role": "system", "content": "Score how well each description matches the predicate. Reply with a JSON array of numbers 0.0-1.0."},
            {"role": "user", "content": prompt},
        ]

        if hasattr(self._client, "chat_with_usage"):
            result = self._client.chat_with_usage(messages)
            content = result.content
            token_usage = getattr(result, "usage", None)
            token_usage_dict = token_usage.to_dict() if hasattr(token_usage, "to_dict") else {}
        else:
            content = self._client.chat(messages)
            token_usage_dict = {}

        scores = self._parse_scores(content, len(nodes))

        results = []
        for i, node in enumerate(nodes):
            score = scores[i] if i < len(scores) else 0.5
            score = max(0.0, min(1.0, float(score)))
            results.append(
                ScoringResult(
                    node_id=str(node.get("id", i)),
                    node_type=str(node.get("type", "?")),
                    node_description=str(node.get("description", "")),
                    predicate=predicate,
                    score=score,
                )
            )

        return BatchScoringResult(
            predicate=predicate,
            results=results,
            token_usage=token_usage_dict if token_usage_dict else None,
        )

    def _build_prompt(self, descriptions, predicate):
        lines = ["Predicate: " + predicate, ""]
        for i, d in enumerate(descriptions):
            lines.append(str(i + 1) + ". " + (d[:500] if d else ""))
        lines.append("")
        lines.append("Return a JSON array of scores 0.0-1.0, e.g. [0.8, 0.2, 0.9]")
        return "\n".join(lines)

    def _parse_scores(self, content, expected_len):
        content = (content or "").strip()
        m = re.search(r"\[[\d.,\s]+\]", content)
        if m:
            try:
                scores = json.loads(m.group())
                return [float(s) for s in scores[:expected_len]]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        return [0.5] * expected_len
