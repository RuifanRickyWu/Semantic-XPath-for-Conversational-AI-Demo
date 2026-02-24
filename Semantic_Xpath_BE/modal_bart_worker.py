"""Modal GPU worker for BART MNLI entailment scoring.

Deploy with:
  modal deploy modal_bart_worker.py
"""

import modal


APP_NAME = "semantic-xpath-bart"
MODEL_NAME = "facebook/bart-large-mnli"

app = modal.App(APP_NAME)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.3.1",
        "transformers>=4.46.2",
    )
)


_tokenizer = None
_model = None
_torch = None


def _load_once():
    global _tokenizer, _model, _torch
    if _model is not None and _tokenizer is not None and _torch is not None:
        return _tokenizer, _model, _torch

    import torch  # Imported lazily inside Modal container.
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    _torch = torch
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    _model.to("cuda")
    _model.eval()
    return _tokenizer, _model, _torch


@app.function(
    image=image,
    gpu="A10G",
    timeout=600,
    scaledown_window=300,
)
def score_entailment_batch(
    premises: list[str],
    hypotheses: list[str],
    include_neutral: bool = False,
) -> list[dict]:
    """Score premise-hypothesis pairs.

    Returns one dict per pair with:
      - contradiction
      - entailment
      - neutral (when include_neutral=True)
    """
    if len(premises) != len(hypotheses):
        raise ValueError("premises and hypotheses must have the same length")
    if not premises:
        return []

    tokenizer, model, torch = _load_once()

    inputs = tokenizer(
        premises,
        hypotheses,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=1024,
    )
    inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits

    probs = torch.softmax(logits, dim=1)
    rows: list[dict] = []
    for p in probs:
        row = {
            "contradiction": float(p[0].item()),
            "entailment": float(p[2].item()),
        }
        if include_neutral:
            row["neutral"] = float(p[1].item())
        rows.append(row)
    return rows
