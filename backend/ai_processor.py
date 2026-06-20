"""
Enterprise AI Reasoning Engine for Document Intelligence
Multi-stage reasoning pipeline with Gemini, Groq, Cohere, and Hugging Face support

PATCHED VERSION — changes from the original are marked with `# PATCH:` comments
so you can diff against your existing file and see exactly what moved.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union

from pydantic import BaseModel, Field, field_validator
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import LRUCache
from dotenv import load_dotenv

# PATCH: override=True — without this, python-dotenv will NOT overwrite a variable
# that is already set in the OS environment. That's why COHERE_MODEL in .env kept
# losing to a stale "command-r" sitting in the shell/host environment.
load_dotenv(override=True)

# ============================================================================
# DOMAIN MODELS
# ============================================================================

class DocumentType(str, Enum):
    """Document types supported by the system"""
    INSPECTION = "inspection"
    THERMAL = "thermal"
    BOTH = "both"

class ReasoningStage(str, Enum):
    """Pipeline stages for reasoning"""
    OBSERVATION_EXTRACTION = "observation_extraction"
    CONFLICT_DETECTION = "conflict_detection"
    ROOT_CAUSE = "root_cause"
    SEVERITY_SCORING = "severity_scoring"
    RECOMMENDATION = "recommendation"
    CONFIDENCE_SCORING = "confidence_scoring"
    REPORT_ASSEMBLY = "report_assembly"

class SeverityLevel(str, Enum):
    """Standardized severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "information"

class ConflictType(str, Enum):
    """Types of conflicts between findings"""
    CONTRADICTION = "contradiction"
    INCONSISTENCY = "inconsistency"
    ANOMALY = "anomaly"
    DISCREPANCY = "discrepancy"
    MISMATCH = "mismatch"

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class Evidence(BaseModel):
    """Evidence supporting an observation"""
    source: DocumentType
    text: str
    page: Optional[int] = None
    confidence: float = Field(0.0, ge=0, le=1.0)

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

class Observation(BaseModel):
    """Extracted observation from documents"""
    id: str = Field(default_factory=lambda: hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:8])
    area: str
    observation: str
    category: str
    severity: SeverityLevel = SeverityLevel.INFO
    severity_score: float = Field(0.0, ge=0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0, le=1.0)
    images: List[str] = Field(default_factory=list)
    related_observations: List[str] = Field(default_factory=list)
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('severity_score')
    @classmethod
    def validate_severity_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

class Conflict(BaseModel):
    """Detected conflict between observations"""
    id: str = Field(default_factory=lambda: hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:8])
    conflict_type: ConflictType
    description: str
    observation_ids: List[str] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    severity: SeverityLevel = SeverityLevel.MEDIUM
    confidence: float = Field(0.5, ge=0, le=1.0)
    resolution_suggestion: Optional[str] = None
    impact_score: float = Field(0.0, ge=0, le=1.0)

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

class RootCauseAnalysis(BaseModel):
    """Root cause analysis with reasoning chain"""
    primary_cause: str
    supporting_evidence: List[str] = Field(default_factory=list)
    reasoning_chain: List[str] = Field(default_factory=list)
    contributing_factors: List[str] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0, le=1.0)
    analysis_date: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

class Recommendation(BaseModel):
    """Structured recommendation"""
    id: str = Field(default_factory=lambda: hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:8])
    action: str
    priority: str  # Immediate, Short-term, Long-term, Preventive
    category: str
    observation_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0, le=1.0)
    estimated_cost: Optional[str] = None
    timeframe: Optional[str] = None

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

class ConfidenceMetrics(BaseModel):
    """Comprehensive confidence metrics"""
    overall_confidence: float = Field(0.0, ge=0, le=1.0)
    evidence_quality: float = Field(0.0, ge=0, le=1.0)
    data_completeness: float = Field(0.0, ge=0, le=1.0)
    reasoning_confidence: float = Field(0.0, ge=0, le=1.0)
    conflict_density: float = Field(0.0, ge=0, le=1.0)
    observation_quality: float = Field(0.0, ge=0, le=1.0)

    @field_validator('overall_confidence', 'evidence_quality', 'data_completeness',
                     'reasoning_confidence', 'conflict_density', 'observation_quality')
    @classmethod
    def validate_metric(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

class ProcessingMetadata(BaseModel):
    """Metadata about the processing pipeline"""
    processing_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    stages_completed: List[ReasoningStage] = Field(default_factory=list)
    token_usage: Dict[str, int] = Field(default_factory=dict)
    model_used: str
    retry_count: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)

class DDRReport(BaseModel):
    """Complete DDR Report from AI Reasoning Engine"""
    # Core sections
    executive_summary: Dict[str, Any] = Field(default_factory=dict)
    property_summary: str = ""
    area_observations: List[Observation] = Field(default_factory=list)

    # Intelligence layers
    conflicts: List[Conflict] = Field(default_factory=list)
    root_cause_analysis: Optional[RootCauseAnalysis] = None
    severity_assessment: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Recommendation] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)

    # Metrics
    confidence_metrics: Optional[ConfidenceMetrics] = None
    processing_metadata: Optional[ProcessingMetadata] = None

# ============================================================================
# PROVIDER ABSTRACTION
# ============================================================================

class LLMProvider(ABC):
    """Abstract interface for LLM providers"""

    @abstractmethod
    async def generate(self,
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       temperature: float = 0.1,
                       max_tokens: int = 4096) -> Tuple[str, Dict[str, Any]]:
        """Generate text from the LLM"""
        pass

    @abstractmethod
    async def generate_structured(self,
                                   prompt: str,
                                   output_schema: Dict[str, Any],
                                   system_prompt: Optional[str] = None,
                                   temperature: float = 0.1) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Generate structured output from the LLM"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name"""
        pass

    @abstractmethod
    def get_context_window(self) -> int:
        """Get the context window size"""
        pass

# ============================================================================
# PROVIDER IMPLEMENTATIONS
# ============================================================================

class HuggingFaceProvider(LLMProvider):
    """Hugging Face API provider with support for Vision-Language models"""

    def __init__(self, api_key: str, model: str = "Qwen/Qwen2.5-VL-72B-Instruct"):
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                base_url="https://router.huggingface.co/v1",
                api_key=api_key,
            )
            self.model = model
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"HuggingFaceProvider initialized with model: {model}")
        except ImportError:
            raise ImportError("OpenAI SDK not installed. Run: pip install openai")

    async def generate(self,
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       temperature: float = 0.1,
                       max_tokens: int = 4096) -> Tuple[str, Dict[str, Any]]:

        start_time = time.time()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=300
            )

            text = response.choices[0].message.content

            metadata = {
                "model": self.model,
                "prompt_tokens": len(prompt.split()),
                "response_tokens": len(text.split()),
                "total_tokens": len(prompt.split()) + len(text.split()),
                "latency_seconds": time.time() - start_time,
                "finish_reason": response.choices[0].finish_reason
            }

            return text, metadata

        except asyncio.TimeoutError:
            self.logger.error(f"HuggingFace request timed out after 300s")
            raise TimeoutError("HuggingFace API request timed out")
        except Exception as e:
            self.logger.error(f"HuggingFace generation failed: {str(e)}")
            raise

    async def generate_structured(self,
                                   prompt: str,
                                   output_schema: Dict[str, Any],
                                   system_prompt: Optional[str] = None,
                                   temperature: float = 0.1) -> Tuple[Dict[str, Any], Dict[str, Any]]:

        schema_prompt = f"""{prompt}

CRITICAL: Return ONLY a valid JSON object with NO markdown fences, NO extra text, and NO explanations.
Expected structure:
{json.dumps(output_schema, indent=2)}

Return the raw JSON object only."""

        text, metadata = await self.generate(
            prompt=schema_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=16384
        )

        try:
            result = self._extract_json(text)
            return result, metadata
        except Exception as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            return {}, metadata

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response, handling multiple objects and extra text"""
        text = text.strip()

        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        brace_count = 0
        start_idx = None
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx is not None:
                    try:
                        return json.loads(text[start_idx:i+1])
                    except json.JSONDecodeError:
                        continue

        bracket_count = 0
        start_idx = None
        for i, char in enumerate(text):
            if char == '[':
                if bracket_count == 0:
                    start_idx = i
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if brace_count == 0 and start_idx is not None:
                    try:
                        return json.loads(text[start_idx:i+1])
                    except json.JSONDecodeError:
                        continue

        objects = []
        for match in re.finditer(r'\{[^{}]*\}', text):
            try:
                obj = json.loads(match.group())
                objects.append(obj)
            except json.JSONDecodeError:
                continue

        if objects:
            return objects[0]

        json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract JSON from: {text[:200]}...")

    def get_model_name(self) -> str:
        return self.model

    def get_context_window(self) -> int:
        return 128_000

class GeminiProvider(LLMProvider):
    """Gemini API provider with structured output support"""

    def __init__(self, api_key: str, model: str = "models/gemini-2.5-flash"):
        try:
            import google.generativeai as genai
            self.genai = genai
            self.genai.configure(api_key=api_key)
            self.model = model
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"GeminiProvider initialized with model: {model}")
        except ImportError:
            raise ImportError("Google Generative AI SDK not installed. Run: pip install google-generativeai")

    async def generate(self,
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       temperature: float = 0.1,
                       max_tokens: int = 4096) -> Tuple[str, Dict[str, Any]]:

        start_time = time.time()

        try:
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            else:
                full_prompt = prompt

            model = self.genai.GenerativeModel(model_name=self.model)

            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )

            text = response.text if response.text else ""

            metadata = {
                "model": self.model,
                "prompt_tokens": len(full_prompt.split()),
                "response_tokens": len(text.split()),
                "total_tokens": len(full_prompt.split()) + len(text.split()),
                "latency_seconds": time.time() - start_time,
                "finish_reason": getattr(response, "finish_reason", "unknown")
            }

            return text, metadata

        except Exception as e:
            self.logger.error(f"Gemini generation failed: {str(e)}")
            raise

    async def generate_structured(self,
                                   prompt: str,
                                   output_schema: Dict[str, Any],
                                   system_prompt: Optional[str] = None,
                                   temperature: float = 0.1) -> Tuple[Dict[str, Any], Dict[str, Any]]:

        schema_prompt = f"""{prompt}

CRITICAL: Return ONLY a valid JSON object with NO markdown fences, NO extra text, and NO explanations.
Expected structure:
{json.dumps(output_schema, indent=2)}

Return the raw JSON object only."""

        text, metadata = await self.generate(
            prompt=schema_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=16384
        )

        try:
            result = self._extract_json(text)
            return result, metadata
        except Exception as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            return {}, metadata

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response, handling various formats"""
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        brace_count = 0
        start_idx = None
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx is not None:
                    try:
                        return json.loads(text[start_idx:i+1])
                    except json.JSONDecodeError:
                        pass

        bracket_count = 0
        start_idx = None
        for i, char in enumerate(text):
            if char == '[':
                if bracket_count == 0:
                    start_idx = i
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0 and start_idx is not None:
                    try:
                        return json.loads(text[start_idx:i+1])
                    except json.JSONDecodeError:
                        pass

        if text.startswith('{'):
            completed = text
            open_count = completed.count('{') - completed.count('}')
            if open_count > 0:
                completed += '}' * open_count
                try:
                    return json.loads(completed)
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"Could not extract JSON from: {text[:200]}...")

    def get_model_name(self) -> str:
        return self.model

    def get_context_window(self) -> int:
        return 1_000_000

class GroqProvider(LLMProvider):
    """Groq API provider for fast inference"""

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        try:
            from groq import AsyncGroq
            self.client = AsyncGroq(api_key=api_key)
            self.model = model
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"GroqProvider initialized with model: {model}")
        except ImportError:
            raise ImportError("Groq SDK not installed. Run: pip install groq")

    async def generate(self,
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       temperature: float = 0.1,
                       max_tokens: int = 4096) -> Tuple[str, Dict[str, Any]]:

        start_time = time.time()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=120
            )

            text = response.choices[0].message.content

            metadata = {
                "model": self.model,
                "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') else len(prompt.split()),
                "response_tokens": response.usage.completion_tokens if hasattr(response, 'usage') else len(text.split()),
                "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') else len(prompt.split()) + len(text.split()),
                "latency_seconds": time.time() - start_time,
                "finish_reason": response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else "unknown"
            }

            return text, metadata

        except Exception as e:
            self.logger.error(f"Groq generation failed: {str(e)}")
            raise

    async def generate_structured(self,
                                   prompt: str,
                                   output_schema: Dict[str, Any],
                                   system_prompt: Optional[str] = None,
                                   temperature: float = 0.1) -> Tuple[Dict[str, Any], Dict[str, Any]]:

        schema_prompt = f"""{prompt}

CRITICAL: Return ONLY a valid JSON object with NO markdown fences, NO extra text, and NO explanations.
Expected structure:
{json.dumps(output_schema, indent=2)}

Return the raw JSON object only."""

        # PATCH: Groq's on-demand TPM limit (12000 for llama-3.3-70b-versatile) is
        # enforced against (prompt tokens + max_tokens requested) — not actual usage.
        # The old value of 16384 alone exceeded the 12000 budget regardless of how
        # small the input prompt was. 4096 leaves headroom for an ~8000-char (≈2000
        # token) prompt plus system prompt/schema overhead. If you see truncated JSON
        # in the logs for large reports, raise this gradually rather than jumping
        # back to 16384.
        text, metadata = await self.generate(
            prompt=schema_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=4096
        )

        try:
            result = self._extract_json(text)
            return result, metadata
        except Exception as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            return {}, metadata

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response"""
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        bracket_match = re.search(r'\[.*\]', text, re.DOTALL)
        if bracket_match:
            try:
                return json.loads(bracket_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract JSON from: {text[:200]}...")

    def get_model_name(self) -> str:
        return self.model

    def get_context_window(self) -> int:
        return 128_000

class CohereProvider(LLMProvider):
    """Cohere API provider"""

    def __init__(self, api_key: str, model: str = "command-a-03-2025"):
        try:
            import cohere
            self.api_key = api_key
            self.model = model
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"CohereProvider initialized with model: {model}")
        except ImportError:
            raise ImportError("Cohere SDK not installed. Run: pip install cohere")

    async def generate(self,
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       temperature: float = 0.1,
                       max_tokens: int = 4096) -> Tuple[str, Dict[str, Any]]:

        start_time = time.time()

        try:
            import cohere
            # Use sync client with to_thread for Cohere
            sync_client = cohere.Client(api_key=self.api_key)

            # Cohere uses a different message format
            if system_prompt:
                full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
            else:
                full_prompt = prompt

            response = await asyncio.to_thread(
                sync_client.chat,
                model=self.model,
                message=full_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                preamble="You are a helpful assistant that provides accurate, structured responses."
            )

            text = response.text if response.text else ""

            metadata = {
                "model": self.model,
                "prompt_tokens": len(full_prompt.split()),
                "response_tokens": len(text.split()),
                "total_tokens": len(full_prompt.split()) + len(text.split()),
                "latency_seconds": time.time() - start_time,
                "finish_reason": "completed" if hasattr(response, 'finish_reason') else "unknown"
            }

            return text, metadata

        except Exception as e:
            self.logger.error(f"Cohere generation failed: {str(e)}")
            raise

    async def generate_structured(self,
                                   prompt: str,
                                   output_schema: Dict[str, Any],
                                   system_prompt: Optional[str] = None,
                                   temperature: float = 0.1) -> Tuple[Dict[str, Any], Dict[str, Any]]:

        schema_prompt = f"""{prompt}

CRITICAL: Return ONLY a valid JSON object with NO markdown fences, NO extra text, and NO explanations.
Expected structure:
{json.dumps(output_schema, indent=2)}

Return the raw JSON object only."""

        # PATCH: Cohere's command-a-03-2025 has a hard max OUTPUT length of 8192
        # tokens. The old value of 16384 was double that ceiling, so Cohere
        # rejected every structured-generation call with a 400 ("too many
        # tokens: max tokens must be less than or equal to 8192"). This is a
        # separate limit from Groq's TPM issue — Cohere's cap is per-call output
        # length, not a combined prompt+output budget, so no input truncation
        # is needed here, just the lower max_tokens.
        text, metadata = await self.generate(
            prompt=schema_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=8192
        )

        try:
            result = self._extract_json(text)
            return result, metadata
        except Exception as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            return {}, metadata

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from response"""
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        bracket_match = re.search(r'\[.*\]', text, re.DOTALL)
        if bracket_match:
            try:
                return json.loads(bracket_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract JSON from: {text[:200]}...")

    def get_model_name(self) -> str:
        return self.model

    def get_context_window(self) -> int:
        return 128_000

# ============================================================================
# PROVIDER MANAGER WITH FALLBACK
# ============================================================================

class ProviderManager:
    """Manages multiple providers with automatic fallback"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.providers = []
        self.primary_provider_name = os.getenv("AI_PROVIDER", "groq").lower()
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all available providers from environment variables"""

        # Gemini
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            model = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
            self.providers.append({
                "name": "gemini",
                "provider": GeminiProvider(api_key=gemini_api_key, model=model),
                "enabled": True
            })
            self.logger.info(f"Gemini provider initialized with model: {model}")

        # Groq
        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key:
            model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            self.providers.append({
                "name": "groq",
                "provider": GroqProvider(api_key=groq_api_key, model=model),
                "enabled": True
            })
            self.logger.info(f"Groq provider initialized with model: {model}")

        # Cohere
        cohere_api_key = os.getenv("COHERE_API_KEY")
        if cohere_api_key:
            # PATCH: default now matches the .env value (command-a-03-2025).
            # With load_dotenv(override=True) above, this should never silently
            # fall back to a stale "command-r" from the OS environment again.
            model = os.getenv("COHERE_MODEL", "command-a-03-2025")
            self.providers.append({
                "name": "cohere",
                "provider": CohereProvider(api_key=cohere_api_key, model=model),
                "enabled": True
            })
            self.logger.info(f"Cohere provider initialized with model: {model}")

        # Hugging Face
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            model = os.getenv("HF_MODEL", "Qwen/Qwen2.5-VL-72B-Instruct")
            self.providers.append({
                "name": "huggingface",
                "provider": HuggingFaceProvider(api_key=hf_token, model=model),
                "enabled": True
            })
            self.logger.info(f"HuggingFace provider initialized with model: {model}")

        # Sort providers: primary first, then others
        if self.providers:
            self.providers.sort(key=lambda x: 0 if x["name"] == self.primary_provider_name else 1)
            self.logger.info(f"Provider order: {[p['name'] for p in self.providers]}")

    def get_primary_provider(self) -> Optional[LLMProvider]:
        """Get the primary provider"""
        for provider_info in self.providers:
            if provider_info["name"] == self.primary_provider_name:
                return provider_info["provider"]
        return self.providers[0]["provider"] if self.providers else None

    async def generate_with_fallback(self,
                                     prompt: str,
                                     system_prompt: Optional[str] = None,
                                     temperature: float = 0.1,
                                     max_tokens: int = 4096) -> Tuple[str, Dict[str, Any]]:
        """Generate with automatic fallback to next provider on failure"""

        last_error = None

        for provider_info in self.providers:
            if not provider_info["enabled"]:
                continue

            provider = provider_info["provider"]
            provider_name = provider_info["name"]

            try:
                self.logger.info(f"Attempting generation with {provider_name}")
                result = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                self.logger.info(f"Generation successful with {provider_name}")
                return result
            except Exception as e:
                self.logger.warning(f"{provider_name} failed: {str(e)}")
                last_error = e
                continue

        if last_error:
            raise last_error
        raise RuntimeError("No providers available or all providers failed")

    async def generate_structured_with_fallback(self,
                                               prompt: str,
                                               output_schema: Dict[str, Any],
                                               system_prompt: Optional[str] = None,
                                               temperature: float = 0.1) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Generate structured output with automatic fallback"""

        last_error = None

        for provider_info in self.providers:
            if not provider_info["enabled"]:
                continue

            provider = provider_info["provider"]
            provider_name = provider_info["name"]

            try:
                self.logger.info(f"Attempting structured generation with {provider_name}")
                result = await provider.generate_structured(
                    prompt=prompt,
                    output_schema=output_schema,
                    system_prompt=system_prompt,
                    temperature=temperature
                )
                self.logger.info(f"Structured generation successful with {provider_name}")
                return result
            except Exception as e:
                self.logger.warning(f"{provider_name} structured generation failed: {str(e)}")
                last_error = e
                continue

        if last_error:
            raise last_error
        raise RuntimeError("No providers available or all providers failed")

# ============================================================================
# PROMPT ENGINEERING
# ============================================================================

class PromptRegistry:
    """Central registry for all prompts with versioning"""

    SYSTEM_OBSERVATION = """You are an expert building inspector. Extract observations only from the provided documents.

RULES:
1. Extract ONLY information explicitly stated
2. Never hallucinate observations
3. Identify specific areas
4. Classify into categories: Structural, Water Intrusion, Electrical, HVAC, Plumbing, Roofing, Insulation, Safety, Other
5. Provide evidence with exact quotes
6. Be professional and precise"""

    SYSTEM_CONFLICT = """You are an expert in evidence reconciliation. Detect conflicts between observations.

RULES:
1. Compare observations carefully
2. Identify contradictions and inconsistencies
3. Provide resolution suggestions
4. Assess conflict severity
5. Return only detected conflicts"""

    SYSTEM_ROOT_CAUSE = """You are an expert forensic engineer. Perform root cause analysis.

APPROACH:
1. Analyze all observations holistically
2. Build causal chain from observations to cause
3. Consider multiple causes
4. Weight evidence strength
5. Provide confidence levels"""

    SYSTEM_SEVERITY = """You are an expert safety assessor. Score observation severity.

FACTORS (weighted):
1. Safety risk: 35%
2. Structural impact: 25%
3. Moisture/thermal: 20%
4. Urgency: 20%

Return scores from 0.0 to 1.0."""

    SYSTEM_RECOMMENDATION = """You are an expert building consultant. Generate actionable recommendations.

PRIORITIES:
1. Immediate: Do now
2. Short-Term: Within 30 days
3. Long-Term: Within 6-12 months
4. Preventive: Ongoing

Be specific and actionable."""

    PROMPT_OBSERVATION = """Analyze the inspection and thermal reports and extract ALL observations.

=== INSPECTION REPORT ===
{inspection_text}

=== THERMAL REPORT ===
{thermal_text}

Return EXACTLY this format:

{{
  "observations": [
    {{
      "area": "string",
      "observation": "string",
      "category": "string",
      "evidence": ["string"],
      "source": "inspection|thermal|both",
      "images": []
    }}
  ]
}}

Do not return explanations.
Do not return markdown.
Do not return code fences.
Return valid JSON only."""

    PROMPT_CONFLICT = """Detect conflicts in these observations:

{observations}

For each conflict:
- conflict_type: Type of conflict
- description: Explanation
- observation_ids: Involved observation IDs
- evidence: Supporting quotes
- severity: critical/high/medium/low
- resolution_suggestion: How to resolve

Return as JSON array. ONLY return raw JSON, no markdown."""

    PROMPT_ROOT_CAUSE = """Perform root cause analysis:

Observations:
{observations}

Conflicts:
{conflicts}

Provide:
- primary_cause: Most likely root cause
- supporting_evidence: Evidence list
- reasoning_chain: Step-by-step logic
- contributing_factors: Other factors
- confidence: 0.0 to 1.0

Return as JSON object. ONLY return raw JSON, no markdown."""

    PROMPT_SEVERITY = """Score severity of these observations:

{observations}

For each:
- severity: critical/high/medium/low
- severity_score: 0.0 to 1.0
- reasoning: Explanation

Return JSON object mapping IDs to scores. ONLY return raw JSON, no markdown."""

    PROMPT_RECOMMENDATION = """Generate recommendations:

Observations:
{observations}

Conflicts:
{conflicts}

Provide:
- action: Specific action
- priority: Immediate/Short-Term/Long-Term/Preventive
- category: Category
- observation_ids: Related observation IDs
- confidence: 0.0 to 1.0

Return as JSON array. ONLY return raw JSON, no markdown."""

    PROMPT_CONFIDENCE = """Assess confidence in:
- Observations: {observation_count}
- Conflicts: {conflict_count}
- Recommendations: {recommendation_count}

Score (0.0-1.0):
- evidence_quality: Evidence strength
- data_completeness: Data availability
- reasoning_confidence: Analysis confidence
- conflict_density: Conflict ratio
- observation_quality: Observation clarity

Return JSON object with all scores. ONLY return raw JSON, no markdown."""

    @classmethod
    def get_prompt(cls, stage: ReasoningStage, **kwargs) -> str:
        """Get prompt for specific stage"""
        prompt_map = {
            ReasoningStage.OBSERVATION_EXTRACTION: cls.PROMPT_OBSERVATION,
            ReasoningStage.CONFLICT_DETECTION: cls.PROMPT_CONFLICT,
            ReasoningStage.ROOT_CAUSE: cls.PROMPT_ROOT_CAUSE,
            ReasoningStage.SEVERITY_SCORING: cls.PROMPT_SEVERITY,
            ReasoningStage.RECOMMENDATION: cls.PROMPT_RECOMMENDATION,
            ReasoningStage.CONFIDENCE_SCORING: cls.PROMPT_CONFIDENCE,
        }

        prompt = prompt_map.get(stage, "")
        return prompt.format(**kwargs) if prompt else ""

    @classmethod
    def get_system_prompt(cls, stage: ReasoningStage) -> str:
        """Get system prompt for specific stage"""
        system_map = {
            ReasoningStage.OBSERVATION_EXTRACTION: cls.SYSTEM_OBSERVATION,
            ReasoningStage.CONFLICT_DETECTION: cls.SYSTEM_CONFLICT,
            ReasoningStage.ROOT_CAUSE: cls.SYSTEM_ROOT_CAUSE,
            ReasoningStage.SEVERITY_SCORING: cls.SYSTEM_SEVERITY,
            ReasoningStage.RECOMMENDATION: cls.SYSTEM_RECOMMENDATION,
        }
        return system_map.get(stage, "")

# ============================================================================
# REASONING PIPELINE
# ============================================================================

class ReasoningPipeline:
    """Multi-stage AI reasoning pipeline"""

    def __init__(self, provider_manager: ProviderManager, config: Optional[Dict[str, Any]] = None):
        self.provider_manager = provider_manager
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self._cache = LRUCache(maxsize=100)
        # PATCH: stage_errors replaces the old local `errors = []` in process(),
        # which was initialized but never appended to. Every stage now records
        # its own failures here so they actually reach processing_metadata.errors
        # instead of disappearing while the API still returns a 200.
        self.stage_errors: List[Dict[str, Any]] = []

    async def process(self,
                      inspection_text: str,
                      thermal_text: str,
                      images: Optional[List[str]] = None) -> DDRReport:
        """Execute complete reasoning pipeline"""

        processing_id = hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:12]
        start_time = datetime.utcnow()
        stages_completed = []
        self.stage_errors = []  # PATCH: reset per run
        token_usage = {}
        all_images = images or []

        try:
            # Stage 1: Observation Extraction
            self.logger.info("Stage 1: Observation Extraction")
            observations = await self._extract_observations(
                inspection_text, thermal_text, all_images
            )
            stages_completed.append(ReasoningStage.OBSERVATION_EXTRACTION)

            if not observations:
                self.logger.warning("No observations extracted, continuing anyway")
                # PATCH: make total extraction failure loud in the server logs,
                # since the API will still return HTTP 200 with an empty report.
                if self.stage_errors:
                    self.logger.critical(
                        f"processing_id={processing_id}: all providers failed during "
                        f"observation extraction. Report will have zero findings. "
                        f"See processing_metadata.errors for provider-level detail."
                    )

            # Stage 2: Conflict Detection
            self.logger.info("Stage 2: Conflict Detection")
            conflicts = await self._detect_conflicts(observations)
            stages_completed.append(ReasoningStage.CONFLICT_DETECTION)

            # Stage 3: Root Cause Analysis
            self.logger.info("Stage 3: Root Cause Analysis")
            root_cause = await self._analyze_root_cause(observations, conflicts)
            stages_completed.append(ReasoningStage.ROOT_CAUSE)

            # Stage 4: Severity Scoring
            self.logger.info("Stage 4: Severity Scoring")
            severity_assessment = await self._score_severity(observations)
            stages_completed.append(ReasoningStage.SEVERITY_SCORING)

            # Stage 5: Recommendation Generation
            self.logger.info("Stage 5: Recommendation Generation")
            recommendations = await self._generate_recommendations(observations, conflicts)
            stages_completed.append(ReasoningStage.RECOMMENDATION)

            # Stage 6: Confidence Scoring
            self.logger.info("Stage 6: Confidence Scoring")
            confidence_metrics = await self._score_confidence(
                observations, conflicts, recommendations
            )
            stages_completed.append(ReasoningStage.CONFIDENCE_SCORING)

            # Stage 7: Report Assembly
            self.logger.info("Stage 7: Report Assembly")
            report = self._assemble_report(
                observations, conflicts, root_cause,
                severity_assessment, recommendations,
                confidence_metrics, processing_id,
                start_time, stages_completed, token_usage,
                self.stage_errors  # PATCH: was the always-empty local `errors`
            )

            return report

        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
            return self._create_error_report(e, processing_id, start_time, stages_completed)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _extract_observations(self,
                                    inspection_text: str,
                                    thermal_text: str,
                                    images: List[str]) -> List[Observation]:
        """Stage 1: Extract observations from documents"""

        image_context = f"Images available: {len(images)}"

        # PATCH: max_chars reduced 20000 -> 8000. Note this alone does not fix
        # Groq's 413s — see GroqProvider.generate_structured, which independently
        # caps max_tokens, since Groq's TPM budget is (prompt tokens + max_tokens
        # requested) combined, not just what's actually generated.
        max_chars = 8000
        inspection_truncated = inspection_text[:max_chars] if inspection_text else ""
        thermal_truncated = thermal_text[:max_chars] if thermal_text else ""

        prompt = PromptRegistry.get_prompt(
            ReasoningStage.OBSERVATION_EXTRACTION,
            inspection_text=inspection_truncated,
            thermal_text=thermal_truncated,
            image_context=image_context
        )

        output_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "observation": {"type": "string"},
                    "category": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "source": {"type": "string"},
                    "images": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["area", "observation", "evidence"]
            }
        }

        try:
            result, metadata = await self.provider_manager.generate_structured_with_fallback(
                prompt=prompt,
                output_schema=output_schema,
                system_prompt=PromptRegistry.get_system_prompt(ReasoningStage.OBSERVATION_EXTRACTION),
                temperature=0.1
            )

            self.logger.info(f"Result type: {type(result)}")
            self.logger.info(f"Result preview: {str(result)[:1000]}")

        except Exception as e:
            self.logger.error(f"Observation extraction failed: {e}")
            # PATCH: surface the failure instead of silently returning []
            self.stage_errors.append({
                "stage": ReasoningStage.OBSERVATION_EXTRACTION.value,
                "error": str(e)
            })
            return []

        if isinstance(result, dict):
            if "observations" in result:
                result = result["observations"]
                self.logger.info(f"Found 'observations' key with {len(result)} items")
            elif "data" in result:
                result = result["data"]
                self.logger.info(f"Found 'data' key with {len(result)} items")
            elif "items" in result:
                result = result["items"]
                self.logger.info(f"Found 'items' key with {len(result)} items")
            elif "area" in result and "observation" in result:
                result = [result]
                self.logger.info("Single observation object detected, wrapped in list")
            else:
                self.logger.warning(f"Unexpected JSON keys: {list(result.keys())}")
                result = []

        if not isinstance(result, list):
            self.logger.warning(f"Expected list but got {type(result)}")
            result = []

        observations = []
        for obs_data in result:
            if not isinstance(obs_data, dict):
                self.logger.warning(f"Skipping non-dict observation: {obs_data}")
                continue

            try:
                evidence = []
                for e in obs_data.get("evidence", []):
                    source = DocumentType.INSPECTION
                    if "thermal" in str(e).lower():
                        source = DocumentType.THERMAL
                    elif "both" in str(e).lower():
                        source = DocumentType.BOTH

                    evidence.append(
                        Evidence(
                            source=source,
                            text=str(e),
                            confidence=0.8
                        )
                    )

                category = obs_data.get("category", "General")
                if not category or category == "General":
                    category = self._categorize_observation(obs_data.get("observation", ""))

                observation = Observation(
                    area=obs_data.get("area", "Unknown"),
                    observation=obs_data.get("observation", ""),
                    category=category,
                    evidence=evidence,
                    images=obs_data.get("images", [])
                )
                observations.append(observation)
            except Exception as ex:
                self.logger.warning(f"Failed observation parse: {ex}")
                self.logger.warning(f"Problematic data: {obs_data}")
                continue

        observations = self._merge_duplicate_observations(observations)

        self.logger.info(f"Extracted {len(observations)} observations")
        return observations

    def _categorize_observation(self, text: str) -> str:
        """Categorize observation based on keywords"""
        categories = {
            "Structural": ["structural", "foundation", "wall", "roof", "beam", "column", "crack"],
            "Water Intrusion": ["water", "leak", "moisture", "damp", "wet", "flood", "humidity"],
            "Electrical": ["electrical", "wiring", "circuit", "panel", "outlet", "breaker"],
            "HVAC": ["hvac", "heating", "cooling", "ventilation", "duct", "furnace", "ac"],
            "Plumbing": ["plumbing", "pipe", "drain", "fixture", "water supply", "faucet"],
            "Roofing": ["roof", "shingle", "membrane", "flashing", "gutter", "ridge"],
            "Insulation": ["insulation", "thermal", "energy", "r-value", "attic"],
            "Safety": ["safety", "hazard", "danger", "emergency", "code violation"]
        }

        text_lower = text.lower()
        for category, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                return category

        return "General"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _detect_conflicts(self, observations: List[Observation]) -> List[Conflict]:
        """Stage 2: Detect conflicts between observations"""

        if not observations or len(observations) < 2:
            return []

        obs_list = [
            {
                "id": obs.id,
                "area": obs.area,
                "observation": obs.observation[:100],
                "category": obs.category,
            }
            for obs in observations[:20]
        ]

        prompt = PromptRegistry.get_prompt(
            ReasoningStage.CONFLICT_DETECTION,
            observations=json.dumps(obs_list, indent=2)
        )

        output_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "conflict_type": {"type": "string"},
                    "description": {"type": "string"},
                    "observation_ids": {"type": "array", "items": {"type": "string"}},
                    "severity": {"type": "string"},
                    "resolution_suggestion": {"type": "string"}
                },
                "required": ["conflict_type", "description", "observation_ids"]
            }
        }

        try:
            result, metadata = await self.provider_manager.generate_structured_with_fallback(
                prompt=prompt,
                output_schema=output_schema,
                system_prompt=PromptRegistry.get_system_prompt(ReasoningStage.CONFLICT_DETECTION),
                temperature=0.1
            )
        except Exception as e:
            self.logger.warning(f"Conflict detection failed: {e}")
            # PATCH: surface the failure
            self.stage_errors.append({
                "stage": ReasoningStage.CONFLICT_DETECTION.value,
                "error": str(e)
            })
            return []

        conflicts = []
        if isinstance(result, list):
            for conflict_data in result:
                if not isinstance(conflict_data, dict):
                    continue
                try:
                    conflict_type_str = conflict_data.get("conflict_type", "discrepancy").lower()
                    try:
                        conflict_type = ConflictType(conflict_type_str)
                    except ValueError:
                        conflict_type = ConflictType.DISCREPANCY

                    severity_str = conflict_data.get("severity", "medium").lower()
                    try:
                        severity = SeverityLevel(severity_str)
                    except ValueError:
                        severity = SeverityLevel.MEDIUM

                    conflict = Conflict(
                        conflict_type=conflict_type,
                        description=conflict_data.get("description", ""),
                        observation_ids=conflict_data.get("observation_ids", []),
                        severity=severity,
                        resolution_suggestion=conflict_data.get("resolution_suggestion")
                    )
                    conflicts.append(conflict)
                except Exception as e:
                    self.logger.warning(f"Failed to parse conflict: {e}")
                    continue

        self.logger.info(f"Detected {len(conflicts)} conflicts")
        return conflicts

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _analyze_root_cause(self,
                                  observations: List[Observation],
                                  conflicts: List[Conflict]) -> RootCauseAnalysis:
        """Stage 3: Root cause analysis"""

        if not observations:
            return RootCauseAnalysis(
                primary_cause="No observations available for analysis",
                supporting_evidence=[],
                reasoning_chain=[],
                contributing_factors=[],
                confidence=0.0
            )

        obs_data = [
            {
                "area": obs.area,
                "observation": obs.observation[:100],
                "category": obs.category,
                "severity": obs.severity.value
            }
            for obs in observations[:10]
        ]

        conf_data = [
            {
                "conflict_type": conf.conflict_type.value,
                "description": conf.description[:100],
                "observation_ids": conf.observation_ids
            }
            for conf in conflicts[:5]
        ]

        prompt = PromptRegistry.get_prompt(
            ReasoningStage.ROOT_CAUSE,
            observations=json.dumps(obs_data, indent=2),
            conflicts=json.dumps(conf_data, indent=2)
        )

        output_schema = {
            "type": "object",
            "properties": {
                "primary_cause": {"type": "string"},
                "supporting_evidence": {"type": "array", "items": {"type": "string"}},
                "reasoning_chain": {"type": "array", "items": {"type": "string"}},
                "contributing_factors": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            },
            "required": ["primary_cause", "supporting_evidence", "reasoning_chain"]
        }

        try:
            result, metadata = await self.provider_manager.generate_structured_with_fallback(
                prompt=prompt,
                output_schema=output_schema,
                system_prompt=PromptRegistry.get_system_prompt(ReasoningStage.ROOT_CAUSE),
                temperature=0.2
            )
        except Exception as e:
            self.logger.warning(f"Root cause analysis failed: {e}")
            # PATCH: surface the failure
            self.stage_errors.append({
                "stage": ReasoningStage.ROOT_CAUSE.value,
                "error": str(e)
            })
            return RootCauseAnalysis(
                primary_cause="Unable to determine root cause",
                supporting_evidence=[],
                reasoning_chain=[],
                contributing_factors=[],
                confidence=0.0
            )

        return RootCauseAnalysis(
            primary_cause=result.get("primary_cause", "Unknown"),
            supporting_evidence=result.get("supporting_evidence", []),
            reasoning_chain=result.get("reasoning_chain", []),
            contributing_factors=result.get("contributing_factors", []),
            confidence=float(result.get("confidence", 0.5))
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _score_severity(self, observations: List[Observation]) -> Dict[str, Any]:
        """Stage 4: Severity scoring"""

        if not observations:
            return {"overall_severity": "info", "average_score": 0.0, "distribution": {}}

        obs_data = [
            {
                "id": obs.id,
                "area": obs.area,
                "observation": obs.observation[:100],
                "category": obs.category
            }
            for obs in observations[:15]
        ]

        prompt = PromptRegistry.get_prompt(
            ReasoningStage.SEVERITY_SCORING,
            observations=json.dumps(obs_data, indent=2)
        )

        output_schema = {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string"},
                    "severity_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning": {"type": "string"}
                },
                "required": ["severity", "severity_score", "reasoning"]
            }
        }

        try:
            result, metadata = await self.provider_manager.generate_structured_with_fallback(
                prompt=prompt,
                output_schema=output_schema,
                system_prompt=PromptRegistry.get_system_prompt(ReasoningStage.SEVERITY_SCORING),
                temperature=0.1
            )

            for obs in observations:
                if obs.id in result:
                    severity_data = result[obs.id]
                    try:
                        obs.severity = SeverityLevel(severity_data.get("severity", "low").lower())
                    except ValueError:
                        obs.severity = SeverityLevel.LOW
                    obs.severity_score = float(severity_data.get("severity_score", 0.5))

        except Exception as e:
            self.logger.warning(f"Severity scoring failed: {e}")
            # PATCH: surface the failure even though there's a heuristic fallback below
            self.stage_errors.append({
                "stage": ReasoningStage.SEVERITY_SCORING.value,
                "error": str(e)
            })
            for obs in observations:
                if obs.category in ["Structural", "Water Intrusion", "Safety"]:
                    obs.severity = SeverityLevel.HIGH
                    obs.severity_score = 0.7
                elif obs.category in ["Electrical", "HVAC", "Roofing"]:
                    obs.severity = SeverityLevel.MEDIUM
                    obs.severity_score = 0.5
                else:
                    obs.severity = SeverityLevel.LOW
                    obs.severity_score = 0.3

        severity_counts = {}
        total_score = 0
        for obs in observations:
            severity_counts[obs.severity.value] = severity_counts.get(obs.severity.value, 0) + 1
            total_score += obs.severity_score

        overall = max(severity_counts.items(), key=lambda x: x[1])[0] if severity_counts else "info"

        return {
            "overall_severity": overall,
            "average_score": total_score / len(observations) if observations else 0,
            "distribution": severity_counts
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_recommendations(self,
                                       observations: List[Observation],
                                       conflicts: List[Conflict]) -> List[Recommendation]:
        """Stage 5: Generate recommendations"""

        if not observations:
            return []

        obs_data = [
            {
                "id": obs.id,
                "area": obs.area,
                "observation": obs.observation[:80],
                "severity": obs.severity.value
            }
            for obs in observations[:15]
        ]

        conf_data = [
            {"conflict_type": conf.conflict_type.value, "description": conf.description[:80]}
            for conf in conflicts[:5]
        ]

        prompt = PromptRegistry.get_prompt(
            ReasoningStage.RECOMMENDATION,
            observations=json.dumps(obs_data, indent=2),
            conflicts=json.dumps(conf_data, indent=2)
        )

        output_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "priority": {"type": "string"},
                    "category": {"type": "string"},
                    "observation_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["action", "priority", "observation_ids"]
            }
        }

        try:
            result, metadata = await self.provider_manager.generate_structured_with_fallback(
                prompt=prompt,
                output_schema=output_schema,
                system_prompt=PromptRegistry.get_system_prompt(ReasoningStage.RECOMMENDATION),
                temperature=0.3
            )
        except Exception as e:
            self.logger.warning(f"Recommendation generation failed: {e}")
            # PATCH: surface the failure even though there's a heuristic fallback below
            self.stage_errors.append({
                "stage": ReasoningStage.RECOMMENDATION.value,
                "error": str(e)
            })
            recommendations = []
            for obs in observations[:5]:
                if obs.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                    recommendations.append(Recommendation(
                        action=f"Immediate inspection and repair of {obs.area}",
                        priority="Immediate",
                        category=obs.category,
                        observation_ids=[obs.id],
                        confidence=0.6
                    ))
            return recommendations

        recommendations = []
        if isinstance(result, list):
            for rec_data in result:
                if not isinstance(rec_data, dict):
                    continue
                try:
                    recommendation = Recommendation(
                        action=rec_data.get("action", ""),
                        priority=rec_data.get("priority", "Short-Term"),
                        category=rec_data.get("category", "General"),
                        observation_ids=rec_data.get("observation_ids", []),
                        confidence=float(rec_data.get("confidence", 0.7))
                    )
                    recommendations.append(recommendation)
                except Exception as e:
                    self.logger.warning(f"Failed to parse recommendation: {e}")
                    continue

        recommendations = self._prioritize_recommendations(recommendations)

        self.logger.info(f"Generated {len(recommendations)} recommendations")
        return recommendations

    async def _score_confidence(self,
                                observations: List[Observation],
                                conflicts: List[Conflict],
                                recommendations: List[Recommendation]) -> ConfidenceMetrics:
        """Stage 6: Confidence scoring"""

        evidence_quality = self._calculate_evidence_quality(observations)
        data_completeness = self._calculate_data_completeness(observations)
        reasoning_confidence = self._calculate_reasoning_confidence(observations, conflicts)
        conflict_density = self._calculate_conflict_density(observations, conflicts)
        observation_quality = self._calculate_observation_quality(observations)

        overall_confidence = (
            0.2 * evidence_quality +
            0.2 * data_completeness +
            0.25 * reasoning_confidence +
            0.15 * (1 - conflict_density) +
            0.2 * observation_quality
        )

        return ConfidenceMetrics(
            overall_confidence=min(1.0, overall_confidence),
            evidence_quality=evidence_quality,
            data_completeness=data_completeness,
            reasoning_confidence=reasoning_confidence,
            conflict_density=conflict_density,
            observation_quality=observation_quality
        )

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _merge_duplicate_observations(self, observations: List[Observation]) -> List[Observation]:
        """Merge duplicate observations"""

        seen_areas = {}
        merged = []

        for obs in observations:
            key = f"{obs.area.lower()}:{obs.category.lower()}"

            if key in seen_areas:
                existing = seen_areas[key]
                existing.evidence.extend(obs.evidence)
                if obs.images:
                    existing.images.extend(obs.images)
            else:
                seen_areas[key] = obs
                merged.append(obs)

        return merged

    def _prioritize_recommendations(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """Prioritize and deduplicate recommendations"""

        priority_order = {
            "immediate": 0, "Immediate": 0,
            "short-term": 1, "Short-Term": 1, "Short-term": 1,
            "long-term": 2, "Long-Term": 2, "Long-term": 2,
            "preventive": 3, "Preventive": 3
        }

        recommendations.sort(key=lambda r: priority_order.get(r.priority, 4))

        seen_actions = set()
        unique = []
        for rec in recommendations:
            action_key = rec.action.lower().strip()
            if action_key not in seen_actions:
                seen_actions.add(action_key)
                unique.append(rec)

        return unique[:20]

    def _calculate_evidence_quality(self, observations: List[Observation]) -> float:
        """Calculate evidence quality score"""

        if not observations:
            return 0.0

        scores = []
        for obs in observations:
            score = 0.0
            if obs.evidence:
                evidence_text = " ".join([e.text for e in obs.evidence])
                score += min(0.5, len(evidence_text) / 500)

                sources = set(e.source for e in obs.evidence)
                if len(sources) > 1:
                    score += 0.3
                else:
                    score += 0.1

                avg_confidence = np.mean([e.confidence for e in obs.evidence]) if obs.evidence else 0.5
                score += 0.2 * avg_confidence

            scores.append(min(1.0, score))

        return float(np.mean(scores)) if scores else 0.0

    def _calculate_data_completeness(self, observations: List[Observation]) -> float:
        """Calculate data completeness score"""

        if not observations:
            return 0.0

        completeness_scores = []
        for obs in observations:
            score = 0.0
            if obs.area and obs.area != "Unknown":
                score += 0.3
            if obs.observation and len(obs.observation) > 10:
                score += 0.3
            if obs.category and obs.category != "General":
                score += 0.2
            if obs.evidence:
                score += 0.2
            completeness_scores.append(score)

        return float(np.mean(completeness_scores)) if completeness_scores else 0.0

    def _calculate_reasoning_confidence(self,
                                       observations: List[Observation],
                                       conflicts: List[Conflict]) -> float:
        """Calculate reasoning confidence score"""

        if not observations:
            return 0.5

        conflict_impact = min(1.0, len(conflicts) * 0.05)
        obs_quality = np.mean([obs.confidence for obs in observations])

        return float(min(1.0, max(0.0, obs_quality * (1 - conflict_impact))))

    def _calculate_conflict_density(self,
                                   observations: List[Observation],
                                   conflicts: List[Conflict]) -> float:
        """Calculate conflict density score"""

        if not observations:
            return 0.0

        conflict_ratio = len(conflicts) / len(observations) if observations else 0
        return float(min(1.0, conflict_ratio * 2))

    def _calculate_observation_quality(self, observations: List[Observation]) -> float:
        """Calculate observation quality score"""

        if not observations:
            return 0.0

        scores = []
        for obs in observations:
            score = 0.0
            word_count = len(obs.observation.split())
            score += min(0.4, word_count / 20)

            if obs.evidence:
                score += 0.3

            if obs.severity_score > 0:
                score += 0.3

            scores.append(min(1.0, score))

        return float(np.mean(scores)) if scores else 0.0

    def _create_error_report(self, error: Exception, processing_id: str,
                             start_time: datetime, stages_completed: List[ReasoningStage]) -> DDRReport:
        """Create an error report"""

        return DDRReport(
            executive_summary={
                "error": str(error),
                "status": "failed",
                "stages_completed": [s.value for s in stages_completed]
            },
            property_summary="Error occurred during processing",
            area_observations=[],
            conflicts=[],
            root_cause_analysis=RootCauseAnalysis(
                primary_cause="Processing error",
                supporting_evidence=[],
                reasoning_chain=["Pipeline failed"],
                contributing_factors=[str(error)],
                confidence=0.0
            ),
            severity_assessment={},
            recommendations=[],
            missing_information=["Complete data unavailable"],
            confidence_metrics=ConfidenceMetrics(
                overall_confidence=0.0,
                evidence_quality=0.0,
                data_completeness=0.0,
                reasoning_confidence=0.0,
                conflict_density=0.0,
                observation_quality=0.0
            ),
            processing_metadata=ProcessingMetadata(
                processing_id=processing_id,
                start_time=start_time,
                end_time=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                stages_completed=stages_completed,
                token_usage={},
                model_used="unknown",
                retry_count=1,
                # PATCH: include any per-stage errors collected before the crash,
                # in addition to the top-level exception that ended the pipeline.
                errors=[{"error": str(error)}] + self.stage_errors
            )
        )

    def _assemble_report(self,
                         observations: List[Observation],
                         conflicts: List[Conflict],
                         root_cause: RootCauseAnalysis,
                         severity_assessment: Dict[str, Any],
                         recommendations: List[Recommendation],
                         confidence_metrics: ConfidenceMetrics,
                         processing_id: str,
                         start_time: datetime,
                         stages_completed: List[ReasoningStage],
                         token_usage: Dict[str, int],
                         errors: List[Dict[str, Any]]) -> DDRReport:
        """Assemble final report"""

        executive_summary = self._generate_executive_summary(
            observations, conflicts, recommendations
        )

        property_summary = self._build_property_summary(observations)
        missing_info = self._identify_missing_information(observations)

        processing_metadata = ProcessingMetadata(
            processing_id=processing_id,
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
            stages_completed=stages_completed,
            token_usage=token_usage,
            model_used=self.provider_manager.primary_provider_name if self.provider_manager.providers else "unknown",
            retry_count=0,
            errors=errors
        )

        return DDRReport(
            executive_summary=executive_summary,
            property_summary=property_summary,
            area_observations=observations,
            conflicts=conflicts,
            root_cause_analysis=root_cause,
            severity_assessment=severity_assessment,
            recommendations=recommendations,
            missing_information=missing_info,
            confidence_metrics=confidence_metrics,
            processing_metadata=processing_metadata
        )

    def _generate_executive_summary(self,
                                   observations: List[Observation],
                                   conflicts: List[Conflict],
                                   recommendations: List[Recommendation]) -> Dict[str, Any]:
        """Generate executive summary"""

        critical = [obs for obs in observations if obs.severity == SeverityLevel.CRITICAL]
        high = [obs for obs in observations if obs.severity == SeverityLevel.HIGH]

        key_findings = []
        for obs in critical[:3]:
            key_findings.append(f"CRITICAL: {obs.observation}")
        for obs in high[:3]:
            key_findings.append(f"HIGH: {obs.observation}")

        if critical:
            risk_overview = f"Immediate action required: {len(critical)} critical issues."
        elif high:
            risk_overview = f"Urgent attention needed: {len(high)} high severity issues."
        else:
            risk_overview = "No critical or high severity issues identified."

        # PATCH: if extraction produced nothing AND we recorded stage errors,
        # don't let the report read like a clean "all good" result.
        if not observations and self.stage_errors:
            risk_overview = (
                "AI analysis could not be completed — all configured providers "
                "failed during processing. See processing_metadata.errors for details."
            )

        immediate = [rec for rec in recommendations if rec.priority.lower() in ["immediate", "Immediate"]]
        short_term = [rec for rec in recommendations if "short" in rec.priority.lower()]
        long_term = [rec for rec in recommendations if "long" in rec.priority.lower()]

        return {
            "key_findings": key_findings,
            "risk_overview": risk_overview,
            "critical_observations": [obs.model_dump() for obs in critical[:5]],
            "property_health_score": max(0, 100 - (len(critical) * 20 + len(high) * 10)),
            "overall_recommendations": [rec.action for rec in immediate[:3] + short_term[:3]],
            "major_concerns": [obs.observation for obs in critical],
            "quick_wins": [rec.action for rec in immediate[:3]],
            "long_term_strategies": [rec.action for rec in long_term][:3]
        }

    def _build_property_summary(self, observations: List[Observation]) -> str:
        """Build property summary"""

        if not observations:
            # PATCH: distinguish "AI found nothing" from "AI failed to run"
            if self.stage_errors:
                return (
                    "Unable to generate a property summary — all AI providers failed "
                    "during processing. No observations were extracted from the source "
                    "documents. See processing_metadata.errors for details."
                )
            return "No observations available."

        categories = {}
        for obs in observations:
            if obs.category not in categories:
                categories[obs.category] = []
            categories[obs.category].append(obs)

        summary = f"Property assessment identified {len(observations)} observations across "
        summary += f"{len(categories)} categories. "

        critical_count = sum(1 for obs in observations if obs.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for obs in observations if obs.severity == SeverityLevel.HIGH)

        if critical_count > 0:
            summary += f"{critical_count} critical issues require immediate attention. "
        if high_count > 0:
            summary += f"{high_count} high-priority issues need urgent assessment. "

        return summary.strip()

    def _identify_missing_information(self, observations: List[Observation]) -> List[str]:
        """Identify missing information"""

        missing = []

        for obs in observations:
            if not obs.evidence:
                missing.append(f"No evidence: {obs.observation[:40]}...")

        return missing[:10]

# ============================================================================
# AI PROCESSOR FACADE - UPDATED to use ProviderManager with fallback
# ============================================================================

class AIProcessor:
    """Main facade for AI processing with automatic provider fallback"""

    def __init__(self, **kwargs):
        """Initialize AI Processor with ProviderManager"""

        # Create provider manager (handles all providers from environment)
        self.provider_manager = ProviderManager()

        if not self.provider_manager.providers:
            raise RuntimeError("No AI providers configured. Please set at least one API key.")

        # Create pipeline
        self.pipeline = ReasoningPipeline(self.provider_manager, kwargs)
        self.logger = logging.getLogger(__name__)

        primary = self.provider_manager.primary_provider_name
        available = [p['name'] for p in self.provider_manager.providers]
        self.logger.info(f"AIProcessor initialized with primary: {primary}, available: {available}")

    async def process_async(self,
                            inspection_text: str,
                            thermal_text: str,
                            images: Optional[List[str]] = None) -> DDRReport:
        """Process documents asynchronously"""

        self.logger.info("Starting AI processing pipeline")
        start_time = time.time()

        try:
            result = await self.pipeline.process(
                inspection_text,
                thermal_text,
                images or []
            )

            self.logger.info(f"Processing completed in {time.time() - start_time:.2f}s")
            return result

        except Exception as e:
            self.logger.error(f"Processing failed: {str(e)}", exc_info=True)
            raise

    def process(self,
                inspection_text: str,
                thermal_text: str,
                images: Optional[List[str]] = None) -> DDRReport:
        """Synchronous wrapper"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                self.process_async(inspection_text, thermal_text, images)
            )
        except Exception as e:
            self.logger.error(f"Processing failed: {e}", exc_info=True)
            raise

# ============================================================================
# LEGACY COMPATIBILITY - UPDATED to use new provider system
# ============================================================================

def generate_ddr_json(inspection_text: str,
                      thermal_text: str,
                      inspection_images: Optional[List[str]] = None,
                      thermal_images: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Legacy-compatible function for generating DDR JSON.

    Returns a properly structured DDR report with all fields that the
    frontend expects: area_observations, root_cause, recommendations,
    confidence_metrics, conflicts, severity_assessment, etc.

    Uses provider manager with automatic fallback between:
    - Gemini (primary, per AI_PROVIDER env var)
    - Groq (fallback)
    - Cohere (fallback)
    - HuggingFace (fallback)
    """

    logging.info("generate_ddr_json using ProviderManager with automatic fallback")

    try:
        # Initialize processor with ProviderManager
        processor = AIProcessor()
    except Exception as e:
        logging.error(f"Failed to initialize AIProcessor: {e}")
        return {
            "property_summary": "Error initializing AI processor. Check API keys.",
            "area_observations": [],
            "root_cause": "Initialization failed",
            "root_cause_analysis": {"primary_cause": "Initialization failed"},
            "recommendations": [],
            "recommended_actions": [],
            "conflicts": [],
            "severity_assessment": {},
            "missing_information": ["Provider initialization failed"],
            "confidence_metrics": {"overall_confidence": 0.0},
            "confidence_score": 0.0,
            "executive_summary": {
                "key_findings": ["Error during processing"],
                "risk_overview": "Unable to complete analysis"
            }
        }

    all_images = (inspection_images or []) + (thermal_images or [])

    try:
        # Get the full DDRReport object
        report = processor.process(inspection_text, thermal_text, all_images)

        # Convert to dict with proper field names that frontend expects
        result = report.model_dump()

        # Ensure area_observations is present and properly formatted
        if 'area_observations' not in result or not result['area_observations']:
            result['area_observations'] = []

        # Ensure recommendations is present
        if 'recommendations' not in result or not result['recommendations']:
            result['recommendations'] = []

        # Ensure conflicts is present
        if 'conflicts' not in result or not result['conflicts']:
            result['conflicts'] = []

        # Ensure root_cause_analysis is present
        if 'root_cause_analysis' not in result or result['root_cause_analysis'] is None:
            result['root_cause_analysis'] = {
                "primary_cause": "Unable to determine root cause from available data.",
                "supporting_evidence": [],
                "reasoning_chain": [],
                "contributing_factors": [],
                "confidence": 0.0
            }

        # Ensure confidence_metrics is present
        if 'confidence_metrics' not in result or result['confidence_metrics'] is None:
            result['confidence_metrics'] = {
                "overall_confidence": 0.0,
                "evidence_quality": 0.0,
                "data_completeness": 0.0,
                "reasoning_confidence": 0.0,
                "conflict_density": 0.0,
                "observation_quality": 0.0
            }

        # Ensure severity_assessment is present
        if 'severity_assessment' not in result or not result['severity_assessment']:
            result['severity_assessment'] = {
                "overall_severity": "info",
                "average_score": 0.0,
                "distribution": {}
            }

        # Ensure executive_summary is present
        if 'executive_summary' not in result or not result['executive_summary']:
            result['executive_summary'] = {
                "key_findings": [],
                "risk_overview": "No critical or high severity issues identified.",
                "critical_observations": [],
                "property_health_score": 100,
                "overall_recommendations": [],
                "major_concerns": [],
                "quick_wins": [],
                "long_term_strategies": []
            }

        # Ensure property_summary is present
        if 'property_summary' not in result or not result['property_summary']:
            result['property_summary'] = "Property assessment completed. No significant findings identified."

        # Ensure missing_information is present
        if 'missing_information' not in result or not result['missing_information']:
            result['missing_information'] = []

        # Add legacy fields for backward compatibility
        result['root_cause'] = result.get('root_cause_analysis', {}).get('primary_cause', '')
        result['confidence_score'] = result.get('confidence_metrics', {}).get('overall_confidence', 0.0)

        # PATCH: explicit, frontend-friendly signal that this report is degraded —
        # i.e. it returned HTTP 200 but the AI stages actually failed. Check
        # processing_metadata.errors rather than inferring this from empty lists.
        stage_errors = result.get('processing_metadata', {}).get('errors', [])
        result['degraded'] = bool(stage_errors) and not result['area_observations']

        # Convert observations to simple dict for frontend compatibility
        if 'area_observations' in result:
            result['area_observations'] = [
                {
                    'area': obs.get('area', ''),
                    'observation': obs.get('observation', ''),
                    'category': obs.get('category', 'General'),
                    'severity': obs.get('severity', 'info'),
                    'severity_score': obs.get('severity_score', 0.0),
                    'evidence': [e.get('text', '') for e in obs.get('evidence', [])],
                    'images': obs.get('images', [])
                }
                for obs in result['area_observations']
            ]

        # Convert recommendations to simple strings for frontend compatibility
        if 'recommendations' in result:
            result['recommended_actions'] = [
                rec.get('action', '') for rec in result['recommendations']
            ]

        # Convert conflicts to simple dict for frontend compatibility
        if 'conflicts' in result:
            result['conflicts'] = [
                {
                    'description': conf.get('description', ''),
                    'conflict_type': conf.get('conflict_type', ''),
                    'severity': conf.get('severity', 'medium'),
                    'observation_ids': conf.get('observation_ids', [])
                }
                for conf in result['conflicts']
            ]

        # Log success with provider info
        provider_info = getattr(processor.pipeline.provider_manager, 'primary_provider_name', 'unknown')
        available = [p['name'] for p in getattr(processor.pipeline.provider_manager, 'providers', [])]
        logging.info(f"Generated DDR report with primary provider: {provider_info}")
        logging.info(f"Available providers: {available}")
        logging.info(f"Generated {len(result.get('area_observations', []))} observations")
        logging.info(f"Generated {len(result.get('recommendations', []))} recommendations")
        logging.info(f"Generated {len(result.get('conflicts', []))} conflicts")
        if result.get('degraded'):
            logging.critical(
                "Report marked degraded=true: all providers failed and zero "
                "observations were extracted. See processing_metadata.errors."
            )

        return result

    except Exception as e:
        logging.error(f"Legacy processing failed: {e}", exc_info=True)
        return {
            "property_summary": "Error generating report",
            "area_observations": [],
            "root_cause": "Processing failed",
            "root_cause_analysis": {"primary_cause": "Processing failed"},
            "recommendations": [],
            "recommended_actions": [],
            "conflicts": [],
            "severity_assessment": {},
            "missing_information": ["Data unavailable"],
            "confidence_metrics": {"overall_confidence": 0.0},
            "confidence_score": 0.0,
            "degraded": True,
            "executive_summary": {
                "key_findings": ["Error during processing"],
                "risk_overview": "Unable to complete analysis"
            }
        }

# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Reasoning Engine")
    parser.add_argument("inspection_file", type=str, help="Inspection report file")
    parser.add_argument("thermal_file", type=str, help="Thermal report file")
    parser.add_argument("--output", "-o", type=str, default="report.json", help="Output file")

    args = parser.parse_args()

    async def main():
        # Read files
        with open(args.inspection_file, 'r', encoding='utf-8') as f:
            inspection_text = f.read()

        with open(args.thermal_file, 'r', encoding='utf-8') as f:
            thermal_text = f.read()

        # Process with auto fallback
        processor = AIProcessor()
        report = await processor.process_async(inspection_text, thermal_text)

        # Save
        with open(args.output, 'w') as f:
            json.dump(report.model_dump(), f, indent=2, default=str)

        print(f"Report generated: {args.output}")
        print(f"Observations: {len(report.area_observations)}")
        print(f"Conflicts: {len(report.conflicts)}")
        print(f"Recommendations: {len(report.recommendations)}")
        if report.confidence_metrics:
            print(f"Overall Confidence: {report.confidence_metrics.overall_confidence:.2f}")

    asyncio.run(main())