import logging
import os
import threading
from pathlib import Path

import torch
import yaml
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from typing import Optional, Union

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class BartNLIClient:
    """BART Large MNLI client for entailment scoring.
    
    Uses facebook/bart-large-mnli model for zero-shot classification
    via natural language inference (NLI).
    """
    
    def __init__(self, model_name: str = "facebook/bart-large-mnli", device: str = None):
        """Initialize the BART NLI client.
        
        Args:
            model_name: HuggingFace model name. Defaults to facebook/bart-large-mnli.
            device: Device to run the model on. Auto-detected if None.
        """
        self.model_name = model_name
        
        # Auto-detect device
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device
        
        logger.info("Loading BART NLI model %s on %s …", model_name, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        logger.info("BART NLI model loaded successfully.")
    
    def get_entailment_score(
        self, 
        node_info: str, 
        predicate: str,
        hypothesis_template: str = "This node {predicate}."
    ) -> float:
        """Calculate entailment score for a node given a predicate.
        
        Args:
            node_info: Information about the node (used as NLI premise).
            predicate: The predicate to check (used to construct hypothesis).
            hypothesis_template: Template for constructing hypothesis. 
                                 Use {predicate} as placeholder.
        
        Returns:
            Entailment score (probability) between 0 and 1.
        """
        # Construct hypothesis from predicate
        hypothesis = hypothesis_template.format(predicate=predicate)
        
        # Tokenize premise and hypothesis
        inputs = self.tokenizer(
            node_info, 
            hypothesis, 
            return_tensors="pt",
            truncation=True,
            max_length=1024
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Run inference
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
        
        # BART MNLI outputs: [contradiction, neutral, entailment]
        # Index 0: contradiction, Index 1: neutral, Index 2: entailment
        # We take entailment vs contradiction probability
        entail_contradiction_logits = logits[:, [0, 2]]
        probs = torch.softmax(entail_contradiction_logits, dim=1)
        
        # Return probability of entailment (index 1 after selecting [0,2])
        entailment_score = probs[0, 1].item()
        
        return entailment_score
    
    def get_detailed_scores(
        self, 
        node_info: str, 
        predicate: str,
        hypothesis_template: str = "This node {predicate}."
    ) -> dict:
        """Get detailed NLI scores including contradiction, neutral, and entailment.
        
        Args:
            node_info: Information about the node (used as NLI premise).
            predicate: The predicate to check (used to construct hypothesis).
            hypothesis_template: Template for constructing hypothesis.
        
        Returns:
            Dictionary with contradiction, neutral, and entailment probabilities.
        """
        hypothesis = hypothesis_template.format(predicate=predicate)
        
        inputs = self.tokenizer(
            node_info, 
            hypothesis, 
            return_tensors="pt",
            truncation=True,
            max_length=1024
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
        
        probs = torch.softmax(logits, dim=1)[0]
        
        return {
            "contradiction": probs[0].item(),
            "neutral": probs[1].item(),
            "entailment": probs[2].item()
        }
    
    def batch_entailment_scores(
        self,
        node_infos: list[str],
        predicate: str,
        hypothesis_template: str = "This node {predicate}."
    ) -> list[float]:
        """Calculate entailment scores for multiple nodes against a single predicate.
        
        Args:
            node_infos: List of node information strings.
            predicate: The predicate to check against all nodes.
            hypothesis_template: Template for constructing hypothesis.
        
        Returns:
            List of entailment scores corresponding to each node.
        """
        hypothesis = hypothesis_template.format(predicate=predicate)
        
        # Create pairs of (node_info, hypothesis) for batch processing
        premises = node_infos
        hypotheses = [hypothesis] * len(node_infos)
        
        inputs = self.tokenizer(
            premises,
            hypotheses,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=1024
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
        
        entail_contradiction_logits = logits[:, [0, 2]]
        probs = torch.softmax(entail_contradiction_logits, dim=1)
        entailment_scores = probs[:, 1].tolist()
        
        return entailment_scores


class ModalBartNLIClient:
    """Remote BART client backed by a deployed Modal function."""

    def __init__(
        self,
        app_name: str,
        function_name: str,
        environment_name: Optional[str] = None,
    ) -> None:
        self.app_name = app_name
        self.function_name = function_name
        self.environment_name = environment_name
        self._function = None
        self._init_function_handle()

    def _init_function_handle(self) -> None:
        try:
            import modal
        except ImportError as exc:
            raise RuntimeError(
                "Modal backend selected but 'modal' package is not installed. "
                "Install it via `pip install modal`."
            ) from exc

        if hasattr(modal.Function, "from_name"):
            kwargs = {}
            if self.environment_name:
                kwargs["environment_name"] = self.environment_name
            self._function = modal.Function.from_name(
                self.app_name,
                self.function_name,
                **kwargs,
            )
            logger.info(
                "Modal BART handle ready via from_name(app=%s, function=%s, environment=%s)",
                self.app_name,
                self.function_name,
                self.environment_name or "default",
            )
            return

        # Backward compatibility with older SDKs.
        self._function = modal.Function.lookup(self.app_name, self.function_name)
        logger.info(
            "Modal BART handle ready via lookup(app=%s, function=%s)",
            self.app_name,
            self.function_name,
        )

    def get_entailment_score(
        self,
        node_info: str,
        predicate: str,
        hypothesis_template: str = "This node {predicate}.",
    ) -> float:
        scores = self.batch_entailment_scores(
            [node_info],
            predicate,
            hypothesis_template=hypothesis_template,
        )
        return float(scores[0]) if scores else 0.5

    def get_detailed_scores(
        self,
        node_info: str,
        predicate: str,
        hypothesis_template: str = "This node {predicate}.",
    ) -> dict:
        hypothesis = hypothesis_template.format(predicate=predicate)
        logger.info(
            "Calling Modal BART detailed scoring (app=%s, function=%s)",
            self.app_name,
            self.function_name,
        )
        try:
            payload = self._function.remote(
                [node_info],
                [hypothesis],
                include_neutral=True,
            )
        except Exception:
            logger.exception("Modal BART detailed scoring failed")
            raise
        if not payload:
            return {"contradiction": 0.0, "neutral": 0.0, "entailment": 0.0}
        return payload[0]

    def batch_entailment_scores(
        self,
        node_infos: list[str],
        predicate: str,
        hypothesis_template: str = "This node {predicate}.",
    ) -> list[float]:
        if not node_infos:
            return []
        hypothesis = hypothesis_template.format(predicate=predicate)
        hypotheses = [hypothesis] * len(node_infos)
        logger.info(
            "Calling Modal BART batch scoring (count=%d, app=%s, function=%s)",
            len(node_infos),
            self.app_name,
            self.function_name,
        )
        try:
            payload = self._function.remote(
                node_infos,
                hypotheses,
                include_neutral=False,
            )
        except Exception:
            logger.exception("Modal BART batch scoring failed")
            raise
        logger.info("Modal BART batch scoring returned %d rows", len(payload))
        return [float(x.get("entailment", 0.5)) for x in payload]


_client_instance: Union[BartNLIClient, ModalBartNLIClient, None] = None
_client_lock = threading.Lock()


def _build_local_client(entailment_config: dict) -> BartNLIClient:
    local_cfg = entailment_config.get("local", {})
    model_name = local_cfg.get("model_name", "facebook/bart-large-mnli")
    device = local_cfg.get("device")
    return BartNLIClient(model_name=model_name, device=device)


def _build_modal_client(entailment_config: dict) -> ModalBartNLIClient:
    modal_cfg = entailment_config.get("modal", {})
    app_name = modal_cfg.get("app_name", "semantic-xpath-bart")
    function_name = modal_cfg.get("function_name", "score_entailment_batch")
    environment_name = modal_cfg.get("environment_name")
    if isinstance(environment_name, str):
        environment_name = environment_name.strip() or None
    if environment_name is None:
        environment_name = os.getenv("MODAL_ENVIRONMENT_NAME")
    return ModalBartNLIClient(
        app_name=app_name,
        function_name=function_name,
        environment_name=environment_name,
    )


def get_bart_client(force_new: bool = False) -> Union[BartNLIClient, ModalBartNLIClient]:
    """Get or create the process-wide BART NLI client (thread-safe singleton)."""
    global _client_instance
    if _client_instance is not None and not force_new:
        return _client_instance
    with _client_lock:
        if _client_instance is None or force_new:
            config = load_config()
            entailment_cfg = config.get("entailment", {})
            backend = str(entailment_cfg.get("backend", "modal")).strip().lower()
            logger.info("Initializing BART client backend=%s", backend)
            if backend == "local":
                _client_instance = _build_local_client(entailment_cfg)
            else:
                _client_instance = _build_modal_client(entailment_cfg)
    return _client_instance



