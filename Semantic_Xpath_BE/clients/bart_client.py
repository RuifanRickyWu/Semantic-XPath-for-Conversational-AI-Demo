import logging
import threading

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from typing import Union

logger = logging.getLogger(__name__)


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


_client_instance: BartNLIClient = None
_client_lock = threading.Lock()


def get_bart_client(force_new: bool = False) -> BartNLIClient:
    """Get or create the process-wide BART NLI client (thread-safe singleton)."""
    global _client_instance
    if _client_instance is not None and not force_new:
        return _client_instance
    with _client_lock:
        if _client_instance is None or force_new:
            _client_instance = BartNLIClient()
    return _client_instance



