"""
Enterprise DDR Intelligence Engine
Transforms AI outputs into professional diagnostic reports with intelligence layers
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
import re

from pydantic import BaseModel, Field, field_validator
import numpy as np

# ============================================================================
# DOMAIN MODELS
# ============================================================================

class SeverityLevel(str, Enum):
    """Standardized severity levels"""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Information"
    NOT_AVAILABLE = "Not Available"

class ConfidenceLevel(str, Enum):
    """Confidence levels for findings"""
    VERY_HIGH = "Very High"
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"
    VERY_LOW = "Very Low"

class RecommendationPriority(str, Enum):
    """Priority levels for recommendations"""
    IMMEDIATE = "Immediate"
    SHORT_TERM = "Short-Term"
    LONG_TERM = "Long-Term"
    PREVENTIVE = "Preventive"
    MONITORING = "Monitoring"

class ObservationCategory(str, Enum):
    """Categories for observations"""
    STRUCTURAL = "Structural"
    WATER_INTRUSION = "Water Intrusion"
    ELECTRICAL = "Electrical"
    HVAC = "HVAC"
    PLUMBING = "Plumbing"
    FOUNDATION = "Foundation"
    ROOFING = "Roofing"
    EXTERIOR = "Exterior"
    INTERIOR = "Interior"
    SAFETY = "Safety"
    GENERAL = "General"

class ConflictType(str, Enum):
    """Types of conflicts between findings"""
    CONTRADICTION = "Contradiction"
    INCONSISTENCY = "Inconsistency"
    ANOMALY = "Anomaly"
    DISCREPANCY = "Discrepancy"

class ReportType(str, Enum):
    """Supported report types"""
    DDR = "DDR"
    INSURANCE = "Insurance"
    STRUCTURAL = "Structural"
    THERMAL = "Thermal"
    ENGINEERING = "Engineering"
    PROPERTY = "Property"

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class Observation(BaseModel):
    """Structured observation model"""
    id: str = Field(default_factory=lambda: hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:8])
    area: str = Field(..., description="Property area being observed")
    category: ObservationCategory = Field(default=ObservationCategory.GENERAL)
    observation: str = Field(..., description="Detailed observation description")
    evidence: str = Field(default="", description="Supporting evidence for observation")
    severity: SeverityLevel = Field(default=SeverityLevel.NOT_AVAILABLE)
    severity_score: float = Field(default=0.0, ge=0, le=1.0)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MODERATE)
    confidence_score: float = Field(default=0.5, ge=0, le=1.0)
    images: List[str] = Field(default_factory=list)
    related_findings: List[str] = Field(default_factory=list)
    normalized_text: str = Field(default="")
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('severity_score')
    @classmethod
    def validate_severity_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "area": "Basement",
                "category": "Water Intrusion",
                "observation": "Signs of water damage on south wall",
                "severity": "High",
                "confidence": "High"
            }
        }
    }

class Conflict(BaseModel):
    """Conflict detection model"""
    id: str = Field(default_factory=lambda: hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:8])
    conflict_type: ConflictType
    description: str
    observation_a_id: str
    observation_b_id: str
    confidence: ConfidenceLevel
    resolution_suggestion: str = Field(default="")
    impact_score: float = Field(default=0.0, ge=0, le=1.0)
    
    @field_validator('impact_score')
    @classmethod
    def validate_impact_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

class Recommendation(BaseModel):
    """Structured recommendation model"""
    id: str = Field(default_factory=lambda: hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:8])
    action: str
    priority: RecommendationPriority
    category: str
    observation_ids: List[str] = Field(default_factory=list)
    estimated_cost: Optional[str] = None
    timeframe: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MODERATE)

class ExecutiveSummary(BaseModel):
    """Executive summary model"""
    key_findings: List[str] = Field(default_factory=list)
    risk_overview: str = ""
    critical_observations: List[Observation] = Field(default_factory=list)
    property_health_score: float = Field(default=0.0, ge=0, le=100)
    overall_recommendations: List[str] = Field(default_factory=list)
    major_concerns: List[str] = Field(default_factory=list)
    quick_wins: List[str] = Field(default_factory=list)
    long_term_strategies: List[str] = Field(default_factory=list)
    
    @field_validator('property_health_score')
    @classmethod
    def validate_health_score(cls, v: float) -> float:
        return max(0.0, min(100.0, v))

class DDRReport(BaseModel):
    """Complete DDR Report model"""
    # Metadata
    report_id: str = Field(default_factory=lambda: hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:12])
    report_type: ReportType = ReportType.DDR
    version: str = "2.0"
    generated_date: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = "AI DDR Intelligence Engine"
    
    # Core Sections
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    property_summary: str = ""
    area_observations: List[Observation] = Field(default_factory=list)
    
    # Intelligence Layers
    conflicts: List[Conflict] = Field(default_factory=list)
    severity_assessment: Dict[str, Any] = Field(default_factory=dict)
    root_cause_analysis: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Recommendation] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    
    # Quality & Metrics
    quality_metrics: Dict[str, Any] = Field(default_factory=dict)
    confidence_metrics: Dict[str, Any] = Field(default_factory=dict)
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)

class ReportGenerationMetrics(BaseModel):
    """Metrics for report generation"""
    generation_duration_seconds: float = 0.0
    observation_count: int = 0
    conflict_count: int = 0
    recommendation_count: int = 0
    completeness_score: float = Field(default=0.0, ge=0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0, le=1.0)
    confidence_score: float = Field(default=0.0, ge=0, le=1.0)
    processing_steps: List[Dict[str, Any]] = Field(default_factory=list)
    
    @field_validator('completeness_score', 'quality_score', 'confidence_score')
    @classmethod
    def validate_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

# ============================================================================
# INTERFACE ABSTRACTIONS
# ============================================================================

class IObservationNormalizer(ABC):
    """Normalizes and cleans observations"""
    @abstractmethod
    async def normalize(self, observations: List[Dict[str, Any]]) -> List[Observation]:
        pass

class IDuplicateDetector(ABC):
    """Detects duplicate observations"""
    @abstractmethod
    async def find_duplicates(self, observations: List[Observation]) -> List[List[Observation]]:
        pass

class IRelationshipAnalyzer(ABC):
    """Analyzes relationships between observations"""
    @abstractmethod
    async def find_relationships(self, observations: List[Observation]) -> Dict[str, List[str]]:
        pass

class ISeverityEngine(ABC):
    """Calculates severity scores"""
    @abstractmethod
    async def calculate_severity(self, observation: Observation) -> Tuple[SeverityLevel, float]:
        pass

class IConfidenceEngine(ABC):
    """Calculates confidence scores"""
    @abstractmethod
    async def calculate_confidence(self, report: DDRReport) -> Dict[str, float]:
        pass

class IConflictDetector(ABC):
    """Detects conflicts between observations"""
    @abstractmethod
    async def detect_conflicts(self, observations: List[Observation]) -> List[Conflict]:
        pass

class IRecommendationEngine(ABC):
    """Generates recommendations"""
    @abstractmethod
    async def generate_recommendations(self, observations: List[Observation], conflicts: List[Conflict]) -> List[Recommendation]:
        pass

class IExecutiveSummaryBuilder(ABC):
    """Builds executive summaries"""
    @abstractmethod
    async def build_summary(self, observations: List[Observation], recommendations: List[Recommendation]) -> ExecutiveSummary:
        pass

class IQualityEngine(ABC):
    """Evaluates report quality"""
    @abstractmethod
    async def evaluate_quality(self, report: DDRReport) -> Dict[str, Any]:
        pass

# ============================================================================
# OBSERVATION NORMALIZATION LAYER
# ============================================================================

class ObservationNormalizer(IObservationNormalizer):
    """Normalizes observations with advanced text processing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._category_keywords = {
            ObservationCategory.STRUCTURAL: ['structural', 'foundation', 'wall', 'ceiling', 'floor', 'beam', 'column'],
            ObservationCategory.WATER_INTRUSION: ['water', 'moisture', 'damp', 'wet', 'leak', 'flood', 'humidity'],
            ObservationCategory.ELECTRICAL: ['electrical', 'wiring', 'circuit', 'breaker', 'panel', 'outlet', 'switch'],
            ObservationCategory.HVAC: ['hvac', 'heating', 'cooling', 'ventilation', 'ac', 'furnace', 'duct'],
            ObservationCategory.PLUMBING: ['plumbing', 'pipe', 'drain', 'toilet', 'sink', 'faucet', 'water heater'],
            ObservationCategory.FOUNDATION: ['foundation', 'crack', 'settlement', 'sinking', 'base'],
            ObservationCategory.ROOFING: ['roof', 'shingle', 'tile', 'leak', 'gutter', 'downspout'],
            ObservationCategory.EXTERIOR: ['exterior', 'siding', 'paint', 'deck', 'porch', 'fence', 'landscaping'],
            ObservationCategory.INTERIOR: ['interior', 'paint', 'wallpaper', 'flooring', 'carpet', 'tile'],
            ObservationCategory.SAFETY: ['safety', 'hazard', 'danger', 'risk', 'fire', 'carbon monoxide'],
        }
    
    async def normalize(self, observations: List[Dict[str, Any]]) -> List[Observation]:
        """Normalize raw observations into structured models"""
        
        normalized = []
        
        for obs in observations:
            try:
                # 1. Clean and normalize text
                clean_obs = self._normalize_text(obs.get("observation", ""))
                clean_area = self._normalize_text(obs.get("area", ""))
                
                # 2. Categorize observation
                category = self._categorize_observation(clean_obs)
                
                # 3. Extract severity
                raw_severity = obs.get("severity", "Not Available")
                severity, severity_score = await self._normalize_severity(raw_severity)
                
                # 4. Extract confidence
                raw_confidence = obs.get("confidence", "Moderate")
                confidence, confidence_score = await self._normalize_confidence(raw_confidence)
                
                # 5. Create observation model
                observation = Observation(
                    area=clean_area or "General Area",
                    category=category,
                    observation=clean_obs,
                    evidence=self._normalize_text(obs.get("supporting_evidence", obs.get("evidence", ""))),
                    severity=severity,
                    severity_score=severity_score,
                    confidence=confidence,
                    confidence_score=confidence_score,
                    images=obs.get("images", []),
                    normalized_text=self._generate_normalized_text(clean_obs)
                )
                
                normalized.append(observation)
                
            except Exception as e:
                self.logger.error(f"Failed to normalize observation: {str(e)}")
                continue
        
        return normalized
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text by cleaning, standardizing, and formatting"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Standardize capitalization
        if text:
            text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
        
        # Ensure proper punctuation
        if text and not text.endswith(('.', '!', '?')):
            text += '.'
        
        return text
    
    def _categorize_observation(self, observation: str) -> ObservationCategory:
        """Categorize observation based on keywords"""
        if not observation:
            return ObservationCategory.GENERAL
        
        observation_lower = observation.lower()
        
        for category, keywords in self._category_keywords.items():
            for keyword in keywords:
                if keyword in observation_lower:
                    return category
        
        return ObservationCategory.GENERAL
    
    async def _normalize_severity(self, severity: str) -> Tuple[SeverityLevel, float]:
        """Normalize severity to standardized levels with scores"""
        severity_map = {
            "critical": (SeverityLevel.CRITICAL, 1.0),
            "high": (SeverityLevel.HIGH, 0.8),
            "medium": (SeverityLevel.MEDIUM, 0.5),
            "low": (SeverityLevel.LOW, 0.2),
            "info": (SeverityLevel.INFO, 0.0),
            "information": (SeverityLevel.INFO, 0.0),
        }
        
        severity_lower = severity.lower().strip()
        for key, (level, score) in severity_map.items():
            if key in severity_lower:
                return level, score
        
        return SeverityLevel.NOT_AVAILABLE, 0.0
    
    async def _normalize_confidence(self, confidence: str) -> Tuple[ConfidenceLevel, float]:
        """Normalize confidence to standardized levels with scores"""
        confidence_map = {
            "very high": (ConfidenceLevel.VERY_HIGH, 1.0),
            "high": (ConfidenceLevel.HIGH, 0.8),
            "moderate": (ConfidenceLevel.MODERATE, 0.5),
            "low": (ConfidenceLevel.LOW, 0.2),
            "very low": (ConfidenceLevel.VERY_LOW, 0.0),
        }
        
        confidence_lower = confidence.lower().strip()
        for key, (level, score) in confidence_map.items():
            if key in confidence_lower:
                return level, score
        
        return ConfidenceLevel.MODERATE, 0.5
    
    def _generate_normalized_text(self, observation: str) -> str:
        """Generate normalized text for deduplication"""
        # Remove punctuation and lowercase
        text = re.sub(r'[^\w\s]', '', observation.lower())
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'of', 'for', 'on', 'at', 'to', 'with', 'without'}
        words = [w for w in text.split() if w not in stop_words]
        return ' '.join(words)

# ============================================================================
# DUPLICATE DETECTION LAYER
# ============================================================================

class DuplicateDetector(IDuplicateDetector):
    """Advanced duplicate detection using multiple strategies"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._similarity_threshold = 0.8
    
    async def find_duplicates(self, observations: List[Observation]) -> List[List[Observation]]:
        """Find duplicate observations using multiple methods"""
        
        duplicates = []
        processed = set()
        
        for i, obs1 in enumerate(observations):
            if i in processed:
                continue
            
            current_group = [obs1]
            
            for j, obs2 in enumerate(observations[i+1:], i+1):
                if j in processed:
                    continue
                
                # Check for duplicates
                if await self._is_duplicate(obs1, obs2):
                    current_group.append(obs2)
                    processed.add(j)
            
            if len(current_group) > 1:
                duplicates.append(current_group)
            
            processed.add(i)
        
        return duplicates
    
    async def _is_duplicate(self, obs1: Observation, obs2: Observation) -> bool:
        """Check if two observations are duplicates"""
        
        # 1. Exact text match
        if obs1.normalized_text == obs2.normalized_text:
            return True
        
        # 2. Area and severity match
        if obs1.area == obs2.area and obs1.severity == obs2.severity:
            # Check text similarity
            similarity = self._calculate_similarity(obs1.normalized_text, obs2.normalized_text)
            if similarity >= self._similarity_threshold:
                return True
        
        return False
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using Jaccard similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)

# ============================================================================
# RELATIONSHIP ANALYSIS LAYER
# ============================================================================

class RelationshipAnalyzer(IRelationshipAnalyzer):
    """Analyzes relationships between observations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def find_relationships(self, observations: List[Observation]) -> Dict[str, List[str]]:
        """Find relationships between observations"""
        
        relationships = defaultdict(list)
        
        # Group by area
        area_groups = defaultdict(list)
        for obs in observations:
            area_groups[obs.area].append(obs.id)
        
        # Areas with multiple observations are related
        for area, obs_ids in area_groups.items():
            if len(obs_ids) > 1:
                for obs_id in obs_ids:
                    relationships[obs_id].extend([oid for oid in obs_ids if oid != obs_id])
        
        # Find cross-area relationships (e.g., water damage tracing)
        for i, obs1 in enumerate(observations):
            for obs2 in observations[i+1:]:
                if await self._are_related(obs1, obs2):
                    relationships[obs1.id].append(obs2.id)
                    relationships[obs2.id].append(obs1.id)
        
        return dict(relationships)
    
    async def _are_related(self, obs1: Observation, obs2: Observation) -> bool:
        """Check if two observations are related"""
        
        # Same category
        if obs1.category == obs2.category:
            return True
        
        # Cause and effect patterns
        cause_effect = {
            ObservationCategory.WATER_INTRUSION: [ObservationCategory.STRUCTURAL, ObservationCategory.FOUNDATION],
            ObservationCategory.STRUCTURAL: [ObservationCategory.SAFETY],
            ObservationCategory.ELECTRICAL: [ObservationCategory.SAFETY],
        }
        
        if obs1.category in cause_effect:
            if obs2.category in cause_effect[obs1.category]:
                return True
        
        return False

# ============================================================================
# SEVERITY ENGINE
# ============================================================================

class SeverityEngine(ISeverityEngine):
    """Advanced severity calculation engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._severity_weights = {
            ObservationCategory.STRUCTURAL: 1.2,
            ObservationCategory.WATER_INTRUSION: 1.3,
            ObservationCategory.ELECTRICAL: 1.4,
            ObservationCategory.SAFETY: 1.5,
            ObservationCategory.FOUNDATION: 1.3,
        }
    
    async def calculate_severity(self, observation: Observation) -> Tuple[SeverityLevel, float]:
        """Calculate severity score with weighted logic"""
        
        base_score = 0.0
        
        # 1. Keyword-based scoring
        severity_keywords = {
            'critical': 1.0,
            'severe': 0.9,
            'danger': 0.9,
            'risk': 0.8,
            'significant': 0.7,
            'moderate': 0.5,
            'minor': 0.2,
            'slight': 0.1,
        }
        
        obs_lower = observation.observation.lower()
        for keyword, score in severity_keywords.items():
            if keyword in obs_lower:
                base_score = max(base_score, score)
                break
        
        # 2. Category-based weighting
        category_weight = self._severity_weights.get(observation.category, 1.0)
        weighted_score = min(1.0, base_score * category_weight)
        
        # 3. Evidence-based adjustment
        if observation.evidence and len(observation.evidence) > 20:
            weighted_score = min(1.0, weighted_score * 1.1)
        
        # 4. Map to severity level
        if weighted_score >= 0.8:
            severity = SeverityLevel.CRITICAL
        elif weighted_score >= 0.6:
            severity = SeverityLevel.HIGH
        elif weighted_score >= 0.4:
            severity = SeverityLevel.MEDIUM
        elif weighted_score >= 0.2:
            severity = SeverityLevel.LOW
        else:
            severity = SeverityLevel.INFO
        
        return severity, weighted_score

# ============================================================================
# CONFIDENCE ENGINE
# ============================================================================

class ConfidenceEngine(IConfidenceEngine):
    """Comprehensive confidence scoring engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def calculate_confidence(self, report: DDRReport) -> Dict[str, float]:
        """Calculate confidence metrics for the report"""
        
        # 1. Data completeness score
        completeness_score = await self._calculate_completeness(report)
        
        # 2. Observation quality score
        quality_score = await self._calculate_observation_quality(report.area_observations)
        
        # 3. AI certainty score
        certainty_score = await self._calculate_ai_certainty(report)
        
        # 4. Conflict density score
        conflict_score = await self._calculate_conflict_score(report.conflicts)
        
        # 5. Overall confidence
        overall_confidence = (
            0.3 * completeness_score +
            0.3 * quality_score +
            0.2 * certainty_score +
            0.2 * conflict_score
        )
        
        return {
            "overall_confidence": round(overall_confidence, 3),
            "data_completeness": round(completeness_score, 3),
            "observation_quality": round(quality_score, 3),
            "ai_certainty": round(certainty_score, 3),
            "conflict_density": round(conflict_score, 3)
        }
    
    async def _calculate_completeness(self, report: DDRReport) -> float:
        """Calculate data completeness score"""
        
        required_sections = [
            report.property_summary,
            report.area_observations,
            report.recommendations,
            report.executive_summary.key_findings
        ]
        
        filled_sections = sum(1 for section in required_sections if section)
        
        return filled_sections / len(required_sections) if required_sections else 0.0
    
    async def _calculate_observation_quality(self, observations: List[Observation]) -> float:
        """Calculate observation quality score"""
        
        if not observations:
            return 0.0
        
        quality_scores = []
        for obs in observations:
            score = 0.0
            if obs.evidence:
                score += 0.3
            if obs.images:
                score += 0.3
            if obs.confidence_score >= 0.7:
                score += 0.4
            quality_scores.append(score)
        
        return float(np.mean(quality_scores))
    
    async def _calculate_ai_certainty(self, report: DDRReport) -> float:
        """Calculate AI certainty score"""
        
        certainty_scores = []
        for obs in report.area_observations:
            certainty_scores.append(obs.confidence_score)
        
        if not certainty_scores:
            return 0.5
        
        return float(np.mean(certainty_scores))
    
    async def _calculate_conflict_score(self, conflicts: List[Conflict]) -> float:
        """Calculate conflict impact score"""
        
        if not conflicts:
            return 1.0
        
        # More conflicts = lower confidence
        conflict_impact = min(1.0, len(conflicts) * 0.1)
        return 1.0 - conflict_impact

# ============================================================================
# CONFLICT DETECTION LAYER
# ============================================================================

class ConflictDetector(IConflictDetector):
    """Advanced conflict detection engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._conflict_patterns = {
            'moisture': ['dry', 'no water', 'no moisture'],
            'damage': ['no damage', 'undamaged', 'intact'],
            'crack': ['no crack', 'solid', 'no structural issues'],
            'leak': ['no leak', 'sealed', 'waterproof'],
        }
    
    async def detect_conflicts(self, observations: List[Observation]) -> List[Conflict]:
        """Detect conflicts between observations"""
        
        conflicts = []
        
        for i, obs1 in enumerate(observations):
            for obs2 in observations[i+1:]:
                conflict = await self._check_conflict(obs1, obs2)
                if conflict:
                    conflicts.append(conflict)
        
        return conflicts
    
    async def _check_conflict(self, obs1: Observation, obs2: Observation) -> Optional[Conflict]:
        """Check if two observations conflict"""
        
        # 1. Same area, different findings
        if obs1.area == obs2.area and obs1.category == obs2.category:
            if obs1.severity != obs2.severity:
                return Conflict(
                    conflict_type=ConflictType.DISCREPANCY,
                    description=f"Different severity assessments for same area: {obs1.severity.value} vs {obs2.severity.value}",
                    observation_a_id=obs1.id,
                    observation_b_id=obs2.id,
                    confidence=ConfidenceLevel.HIGH,
                    impact_score=0.7
                )
        
        # 2. Pattern-based conflicts (e.g., moisture vs no moisture)
        for keyword, opposites in self._conflict_patterns.items():
            if keyword in obs1.observation.lower():
                for opposite in opposites:
                    if opposite in obs2.observation.lower():
                        return Conflict(
                            conflict_type=ConflictType.CONTRADICTION,
                            description=f"Contradictory findings: '{keyword}' vs '{opposite}'",
                            observation_a_id=obs1.id,
                            observation_b_id=obs2.id,
                            confidence=ConfidenceLevel.VERY_HIGH,
                            impact_score=0.9
                        )
        
        return None

# ============================================================================
# RECOMMENDATION ENGINE
# ============================================================================

class RecommendationEngine(IRecommendationEngine):
    """Intelligent recommendation generation engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._recommendation_templates = {
            ObservationCategory.STRUCTURAL: {
                SeverityLevel.CRITICAL: "Immediately engage structural engineer for emergency assessment",
                SeverityLevel.HIGH: "Schedule structural assessment within 48 hours",
                SeverityLevel.MEDIUM: "Monitor structural conditions weekly",
                SeverityLevel.LOW: "Document structural observations for future reference"
            },
            ObservationCategory.WATER_INTRUSION: {
                SeverityLevel.CRITICAL: "Emergency water extraction and remediation required",
                SeverityLevel.HIGH: "Professional water damage restoration needed",
                SeverityLevel.MEDIUM: "Install dehumidifiers and monitor moisture levels",
                SeverityLevel.LOW: "Improve ventilation and check for leaks"
            },
        }
    
    async def generate_recommendations(self, observations: List[Observation], conflicts: List[Conflict]) -> List[Recommendation]:
        """Generate intelligent recommendations"""
        
        recommendations = []
        
        # Group observations by severity
        by_severity = defaultdict(list)
        for obs in observations:
            by_severity[obs.severity].append(obs)
        
        # 1. Critical issues first
        for obs in by_severity.get(SeverityLevel.CRITICAL, []):
            rec = await self._generate_recommendation(obs, RecommendationPriority.IMMEDIATE)
            if rec:
                recommendations.append(rec)
        
        # 2. High severity issues
        for obs in by_severity.get(SeverityLevel.HIGH, []):
            rec = await self._generate_recommendation(obs, RecommendationPriority.SHORT_TERM)
            if rec:
                recommendations.append(rec)
        
        # 3. Medium severity issues
        for obs in by_severity.get(SeverityLevel.MEDIUM, []):
            rec = await self._generate_recommendation(obs, RecommendationPriority.LONG_TERM)
            if rec:
                recommendations.append(rec)
        
        # 4. Preventive recommendations
        for obs in by_severity.get(SeverityLevel.LOW, []):
            rec = await self._generate_recommendation(obs, RecommendationPriority.PREVENTIVE)
            if rec:
                recommendations.append(rec)
        
        # 5. Conflict-based recommendations
        for conflict in conflicts:
            rec = await self._generate_conflict_recommendation(conflict)
            if rec:
                recommendations.append(rec)
        
        # 6. Remove duplicates
        recommendations = await self._remove_duplicates(recommendations)
        
        return recommendations
    
    async def _generate_recommendation(self, observation: Observation, priority: RecommendationPriority) -> Optional[Recommendation]:
        """Generate recommendation for an observation"""
        
        # Use template if available
        templates = self._recommendation_templates.get(observation.category, {})
        action = templates.get(observation.severity, f"Address: {observation.observation}")
        
        return Recommendation(
            action=action,
            priority=priority,
            category=observation.category.value,
            observation_ids=[observation.id],
            confidence=observation.confidence
        )
    
    async def _generate_conflict_recommendation(self, conflict: Conflict) -> Optional[Recommendation]:
        """Generate recommendation for a conflict"""
        
        return Recommendation(
            action=f"Resolve conflict: {conflict.description}",
            priority=RecommendationPriority.IMMEDIATE if conflict.impact_score > 0.7 else RecommendationPriority.SHORT_TERM,
            category="Conflict Resolution",
            observation_ids=[conflict.observation_a_id, conflict.observation_b_id],
            confidence=conflict.confidence
        )
    
    async def _remove_duplicates(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """Remove duplicate recommendations"""
        
        seen_actions = set()
        unique_recommendations = []
        
        for rec in recommendations:
            action_key = rec.action.lower().strip()
            if action_key not in seen_actions:
                seen_actions.add(action_key)
                unique_recommendations.append(rec)
        
        return unique_recommendations

# ============================================================================
# EXECUTIVE SUMMARY BUILDER
# ============================================================================

class ExecutiveSummaryBuilder(IExecutiveSummaryBuilder):
    """Intelligent executive summary builder"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def build_summary(self, observations: List[Observation], recommendations: List[Recommendation]) -> ExecutiveSummary:
        """Build comprehensive executive summary"""
        
        # 1. Extract key findings
        key_findings = self._extract_key_findings(observations)
        
        # 2. Identify critical observations
        critical_observations = [obs for obs in observations if obs.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]
        
        # 3. Calculate property health score
        health_score = await self._calculate_health_score(observations)
        
        # 4. Generate risk overview
        risk_overview = self._generate_risk_overview(observations)
        
        # 5. Extract major concerns
        major_concerns = self._extract_major_concerns(critical_observations)
        
        # 6. Identify quick wins
        quick_wins = self._identify_quick_wins(observations, recommendations)
        
        # 7. Generate long-term strategies
        long_term_strategies = self._generate_long_term_strategies(observations, recommendations)
        
        # 8. Overall recommendations
        overall_recommendations = [rec.action for rec in recommendations[:5]]
        
        return ExecutiveSummary(
            key_findings=key_findings,
            risk_overview=risk_overview,
            critical_observations=critical_observations,
            property_health_score=health_score,
            overall_recommendations=overall_recommendations,
            major_concerns=major_concerns,
            quick_wins=quick_wins,
            long_term_strategies=long_term_strategies
        )
    
    def _extract_key_findings(self, observations: List[Observation]) -> List[str]:
        """Extract key findings from observations"""
        
        key_findings = []
        
        # Group by severity
        severity_groups = defaultdict(list)
        for obs in observations:
            severity_groups[obs.severity].append(obs)
        
        # Critical findings
        for obs in severity_groups.get(SeverityLevel.CRITICAL, []):
            key_findings.append(f"CRITICAL: {obs.observation}")
        
        # High severity findings
        for obs in severity_groups.get(SeverityLevel.HIGH, []):
            key_findings.append(f"HIGH: {obs.observation}")
        
        # Limit to top findings
        return key_findings[:10]
    
    async def _calculate_health_score(self, observations: List[Observation]) -> float:
        """Calculate property health score"""
        
        if not observations:
            return 100.0
        
        # Base score
        score = 100.0
        
        # Deduct based on severity
        for obs in observations:
            if obs.severity == SeverityLevel.CRITICAL:
                score -= 20
            elif obs.severity == SeverityLevel.HIGH:
                score -= 10
            elif obs.severity == SeverityLevel.MEDIUM:
                score -= 5
            elif obs.severity == SeverityLevel.LOW:
                score -= 2
        
        return max(0.0, min(100.0, score))
    
    def _generate_risk_overview(self, observations: List[Observation]) -> str:
        """Generate risk overview summary"""
        
        critical_count = sum(1 for obs in observations if obs.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for obs in observations if obs.severity == SeverityLevel.HIGH)
        
        if critical_count > 0:
            return f"Immediate attention required: {critical_count} critical issue(s) identified requiring emergency action."
        elif high_count > 0:
            return f"{high_count} high severity issue(s) identified requiring professional assessment within 48 hours."
        else:
            return "No critical or high severity issues identified. Property appears to be in generally good condition."
    
    def _extract_major_concerns(self, critical_observations: List[Observation]) -> List[str]:
        """Extract major concerns from critical observations"""
        
        concerns = []
        for obs in critical_observations[:5]:
            concerns.append(f"{obs.category.value}: {obs.observation}")
        
        return concerns
    
    def _identify_quick_wins(self, observations: List[Observation], recommendations: List[Recommendation]) -> List[str]:
        """Identify quick win recommendations"""
        
        quick_wins = []
        
        # Look for low/medium severity issues with easy fixes
        for obs in observations:
            if obs.severity in [SeverityLevel.LOW, SeverityLevel.MEDIUM]:
                if "clean" in obs.observation.lower() or "repair" in obs.observation.lower():
                    quick_wins.append(f"Quick fix: {obs.observation}")
        
        return quick_wins[:5]
    
    def _generate_long_term_strategies(self, observations: List[Observation], recommendations: List[Recommendation]) -> List[str]:
        """Generate long-term strategies"""
        
        strategies = []
        
        # Group by category
        category_groups = defaultdict(list)
        for obs in observations:
            category_groups[obs.category].append(obs)
        
        for category, obs_list in category_groups.items():
            if len(obs_list) >= 3:
                strategies.append(f"Long-term {category.value} maintenance plan needed based on {len(obs_list)} observations")
        
        # Add prevention strategies
        prevention_strategies = [
            "Implement regular preventive maintenance schedule",
            "Monitor and document all property conditions",
            "Establish emergency response protocols",
            "Maintain comprehensive property documentation"
        ]
        
        strategies.extend(prevention_strategies[:3])
        
        return strategies[:5]

# ============================================================================
# QUALITY ENGINE
# ============================================================================

class QualityEngine(IQualityEngine):
    """Comprehensive quality evaluation engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def evaluate_quality(self, report: DDRReport) -> Dict[str, Any]:
        """Evaluate report quality across multiple dimensions"""
        
        quality_scores = {}
        
        # 1. Completeness score
        completeness = await self._evaluate_completeness(report)
        quality_scores["completeness"] = completeness
        
        # 2. Observation quality
        observation_quality = await self._evaluate_observation_quality(report.area_observations)
        quality_scores["observation_quality"] = observation_quality
        
        # 3. Recommendation quality
        recommendation_quality = await self._evaluate_recommendation_quality(report.recommendations)
        quality_scores["recommendation_quality"] = recommendation_quality
        
        # 4. Overall quality
        overall = np.mean([completeness, observation_quality, recommendation_quality])
        quality_scores["overall_quality"] = round(overall, 3)
        
        # 5. Identified issues
        quality_scores["issues"] = await self._identify_quality_issues(report)
        
        return quality_scores
    
    async def _evaluate_completeness(self, report: DDRReport) -> float:
        """Evaluate report completeness"""
        
        required_sections = [
            report.property_summary,
            report.area_observations,
            report.recommendations,
            report.executive_summary.key_findings,
            report.executive_summary.risk_overview
        ]
        
        filled = sum(1 for section in required_sections if section)
        return filled / len(required_sections) if required_sections else 0.0
    
    async def _evaluate_observation_quality(self, observations: List[Observation]) -> float:
        """Evaluate observation quality"""
        
        if not observations:
            return 0.0
        
        scores = []
        for obs in observations:
            score = 0.0
            
            # Evidence quality
            if obs.evidence and len(obs.evidence) > 10:
                score += 0.3
            
            # Image evidence
            if obs.images:
                score += 0.3
            
            # Confidence score
            if obs.confidence_score >= 0.7:
                score += 0.4
            
            scores.append(score)
        
        return float(np.mean(scores))
    
    async def _evaluate_recommendation_quality(self, recommendations: List[Recommendation]) -> float:
        """Evaluate recommendation quality"""
        
        if not recommendations:
            return 0.0
        
        scores = []
        for rec in recommendations:
            score = 0.0
            
            # Has priority
            if rec.priority:
                score += 0.3
            
            # Has category
            if rec.category:
                score += 0.3
            
            # Has observation references
            if rec.observation_ids:
                score += 0.4
            
            scores.append(score)
        
        return float(np.mean(scores))
    
    async def _identify_quality_issues(self, report: DDRReport) -> List[str]:
        """Identify quality issues in the report"""
        
        issues = []
        
        # Missing sections
        if not report.property_summary:
            issues.append("Missing property summary")
        
        if not report.area_observations:
            issues.append("No area observations provided")
        
        if not report.recommendations:
            issues.append("No recommendations provided")
        
        # Weak recommendations
        weak_recommendations = [rec for rec in report.recommendations if len(rec.action) < 20]
        if weak_recommendations:
            issues.append(f"{len(weak_recommendations)} weak recommendations detected")
        
        # Low confidence observations
        low_confidence = [obs for obs in report.area_observations if obs.confidence_score < 0.4]
        if low_confidence:
            issues.append(f"{len(low_confidence)} observations with low confidence")
        
        return issues

# ============================================================================
# DDR GENERATOR ENGINE
# ============================================================================

class DDRGeneratorEngine:
    """Orchestration engine for DDR report generation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all processing components"""
        self.normalizer = ObservationNormalizer()
        self.duplicate_detector = DuplicateDetector()
        self.relationship_analyzer = RelationshipAnalyzer()
        self.severity_engine = SeverityEngine()
        self.confidence_engine = ConfidenceEngine()
        self.conflict_detector = ConflictDetector()
        self.recommendation_engine = RecommendationEngine()
        self.executive_summary_builder = ExecutiveSummaryBuilder()
        self.quality_engine = QualityEngine()
    
    async def generate_report(self, raw_ddr_data: Dict[str, Any], report_type: ReportType = ReportType.DDR) -> DDRReport:
        """Generate complete DDR report from raw data"""
        
        start_time = time.time()
        self.logger.info(f"Starting report generation: {report_type.value}")
        
        try:
            # Step 1: Validate input
            self._validate_input(raw_ddr_data)
            
            # Step 2: Normalize observations
            raw_observations = raw_ddr_data.get("area_observations", [])
            observations = await self.normalizer.normalize(raw_observations)
            
            # Step 3: Detect duplicates
            duplicates = await self.duplicate_detector.find_duplicates(observations)
            if duplicates:
                self.logger.info(f"Found {len(duplicates)} duplicate groups")
                observations = self._merge_duplicates(observations, duplicates)
            
            # Step 4: Calculate severity
            for obs in observations:
                severity, score = await self.severity_engine.calculate_severity(obs)
                obs.severity = severity
                obs.severity_score = score
            
            # Step 5: Find relationships
            relationships = await self.relationship_analyzer.find_relationships(observations)
            for obs_id, related_ids in relationships.items():
                for obs in observations:
                    if obs.id == obs_id:
                        obs.related_findings = related_ids
            
            # Step 6: Detect conflicts
            conflicts = await self.conflict_detector.detect_conflicts(observations)
            
            # Step 7: Generate recommendations
            recommendations = await self.recommendation_engine.generate_recommendations(observations, conflicts)
            
            # Step 8: Build executive summary
            executive_summary = await self.executive_summary_builder.build_summary(observations, recommendations)
            
            # Step 9: Build complete report
            report = DDRReport(
                report_type=report_type,
                executive_summary=executive_summary,
                property_summary=self._extract_property_summary(raw_ddr_data),
                area_observations=observations,
                conflicts=conflicts,
                severity_assessment=self._build_severity_assessment(observations),
                root_cause_analysis=self._build_root_cause_analysis(raw_ddr_data),
                recommendations=recommendations,
                missing_information=self._extract_missing_information(raw_ddr_data),
                quality_metrics={},
                confidence_metrics={},
                generation_metadata={
                    "duration_seconds": time.time() - start_time,
                    "report_type": report_type.value,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # Step 10: Calculate confidence metrics
            report.confidence_metrics = await self.confidence_engine.calculate_confidence(report)
            
            # Step 11: Evaluate quality
            report.quality_metrics = await self.quality_engine.evaluate_quality(report)
            
            # Step 12: Log metrics
            self._log_generation_metrics(report, start_time)
            
            self.logger.info(f"Report generation completed in {time.time() - start_time:.2f}s")
            return report
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {str(e)}", exc_info=True)
            raise
    
    def _validate_input(self, data: Dict[str, Any]) -> None:
        """Validate input data"""
        
        if not data:
            raise ValueError("Input data is empty")
        
        if not isinstance(data, dict):
            raise ValueError(f"Invalid input format: expected dict, got {type(data)}")
    
    def _merge_duplicates(self, observations: List[Observation], duplicate_groups: List[List[Observation]]) -> List[Observation]:
        """Merge duplicate observations"""
        
        to_remove = set()
        
        for group in duplicate_groups:
            # Keep the observation with most evidence
            best_obs = max(group, key=lambda o: len(o.evidence) + len(o.images))
            to_remove.update([obs.id for obs in group if obs.id != best_obs.id])
        
        return [obs for obs in observations if obs.id not in to_remove]
    
    def _extract_property_summary(self, data: Dict[str, Any]) -> str:
        """Extract and format property summary"""
        
        summary = data.get("property_summary", "")
        if not summary:
            summary = "No property summary provided. Please refer to observations below."
        
        return summary.strip()
    
    def _build_severity_assessment(self, observations: List[Observation]) -> Dict[str, Any]:
        """Build severity assessment"""
        
        severity_counts = defaultdict(int)
        for obs in observations:
            severity_counts[obs.severity.value] += 1
        
        # Calculate average severity score
        avg_score = np.mean([obs.severity_score for obs in observations]) if observations else 0.0
        
        return {
            "overall_severity": max(severity_counts.items(), key=lambda x: x[1])[0] if severity_counts else "Not Available",
            "severity_distribution": dict(severity_counts),
            "average_severity_score": round(float(avg_score), 3)
        }
    
    def _build_root_cause_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build root cause analysis"""
        
        root_cause = data.get("root_cause", "")
        if not root_cause:
            root_cause = "Unable to determine root cause from available data."
        
        return {
            "primary_cause": root_cause,
            "contributing_factors": data.get("contributing_factors", []),
            "analysis_method": "AI-assisted pattern recognition"
        }
    
    def _extract_missing_information(self, data: Dict[str, Any]) -> List[str]:
        """Extract missing information"""
        
        missing = data.get("missing_information", [])
        if not missing:
            return ["No missing information identified."]
        
        return [item.strip() for item in missing if item.strip()]
    
    def _log_generation_metrics(self, report: DDRReport, start_time: float) -> None:
        """Log report generation metrics"""
        
        duration = time.time() - start_time
        
        metrics = {
            "report_id": report.report_id,
            "report_type": report.report_type.value,
            "duration_seconds": round(duration, 2),
            "observation_count": len(report.area_observations),
            "conflict_count": len(report.conflicts),
            "recommendation_count": len(report.recommendations),
            "completeness_score": report.quality_metrics.get("completeness", 0),
            "quality_score": report.quality_metrics.get("overall_quality", 0),
            "confidence_score": report.confidence_metrics.get("overall_confidence", 0)
        }
        
        self.logger.info(f"Generation metrics: {json.dumps(metrics)}")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def build_ddr_report(ddr_json: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy-compatible function"""
    
    engine = DDRGeneratorEngine()
    report = await engine.generate_report(ddr_json)
    
    # Convert to dictionary format
    return report.model_dump()

def validate_ddr_report(ddr_report: Dict[str, Any]) -> bool:
    """Validate DDR report structure"""
    
    required_keys = [
        "executive_summary",
        "property_summary",
        "area_observations",
        "conflicts",
        "recommendations",
        "quality_metrics",
        "confidence_metrics"
    ]
    
    for key in required_keys:
        if key not in ddr_report:
            return False
    
    return True

# ============================================================================
# MAIN FUNCTION FOR PDF GENERATION
# ============================================================================

def generate_pdf(ddr_json: Dict[str, Any], images: List[str], output_dir: str) -> str:
    """
    Generate a PDF report from DDR JSON data.
    This is the main function called by main.py
    
    Args:
        ddr_json: DDR report data as dictionary
        images: List of image paths
        output_dir: Directory to save the PDF
    
    Returns:
        Path to the generated PDF file
    """
    import asyncio
    import json
    from datetime import datetime
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_id = hashlib.md5(json.dumps(ddr_json).encode()).hexdigest()[:8]
    filename = f"ddr_report_{timestamp}_{report_id}.pdf"
    full_path = output_path / filename
    
    # Build the report
    async def build_report():
        # Normalize and structure the data
        engine = DDRGeneratorEngine()
        report = await engine.generate_report(ddr_json)
        return report
    
    try:
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        report = loop.run_until_complete(build_report())
        loop.close()
    except Exception as e:
        logging.error(f"Failed to generate DDR report: {str(e)}")
        # Create a fallback report
        report = DDRReport(
            property_summary=ddr_json.get("property_summary", "Report generation failed"),
            area_observations=[],
            recommendations=[],
            conflicts=[],
            executive_summary=ExecutiveSummary(
                key_findings=["Error generating report"],
                risk_overview=f"An error occurred: {str(e)}",
                property_health_score=0
            ),
            severity_assessment={},
            root_cause_analysis={"primary_cause": "Error during generation"},
            missing_information=["Complete report unavailable due to error"],
            quality_metrics={"overall_quality": 0},
            confidence_metrics={"overall_confidence": 0}
        )
    
    # Generate PDF content
    try:
        pdf_content = _generate_pdf_content(report, images)
        
        # Write PDF file
        with open(full_path, 'wb') as f:
            f.write(pdf_content)
        
        return str(full_path)
        
    except Exception as e:
        logging.error(f"Failed to generate PDF file: {str(e)}")
        raise

def _generate_pdf_content(report: DDRReport, images: List[str]) -> bytes:
    """
    Generate PDF content from a DDR report.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib import colors
    import io
    
    # Create a buffer for the PDF
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#1a365d')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor('#2d3748')
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubheading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        textColor=colors.HexColor('#4a5568')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6
    )
    
    # Build the story
    story = []
    
    # Title
    story.append(Paragraph(f"Detailed Diagnostic Report", title_style))
    story.append(Paragraph(f"Report ID: {report.report_id}", body_style))
    story.append(Paragraph(f"Generated: {report.generated_date.strftime('%Y-%m-%d %H:%M:%S')}", body_style))
    story.append(Spacer(1, 0.25 * inch))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(f"Property Health Score: {report.executive_summary.property_health_score:.1f}/100", body_style))
    story.append(Paragraph(report.executive_summary.risk_overview, body_style))
    story.append(Spacer(1, 0.15 * inch))
    
    # Key Findings
    story.append(Paragraph("Key Findings", subheading_style))
    for finding in report.executive_summary.key_findings[:5]:
        story.append(Paragraph(f"• {finding}", body_style))
    story.append(Spacer(1, 0.15 * inch))
    
    # Property Summary
    story.append(Paragraph("Property Summary", heading_style))
    story.append(Paragraph(report.property_summary, body_style))
    story.append(Spacer(1, 0.15 * inch))
    
    # Observations
    story.append(Paragraph(f"Area Observations ({len(report.area_observations)})", heading_style))
    for obs in report.area_observations[:10]:
        story.append(Paragraph(f"<b>{obs.area}</b> - {obs.category.value}", subheading_style))
        story.append(Paragraph(obs.observation, body_style))
        if obs.evidence:
            story.append(Paragraph(f"Evidence: {obs.evidence}", body_style))
        story.append(Paragraph(f"Severity: {obs.severity.value} (Score: {obs.severity_score:.2f})", body_style))
        story.append(Spacer(1, 0.1 * inch))
    
    # If there are many observations, add a note
    if len(report.area_observations) > 10:
        story.append(Paragraph(f"... and {len(report.area_observations) - 10} more observations", body_style))
    story.append(PageBreak())
    
    # Recommendations
    story.append(Paragraph(f"Recommendations ({len(report.recommendations)})", heading_style))
    
    # Group recommendations by priority
    by_priority = defaultdict(list)
    for rec in report.recommendations:
        by_priority[rec.priority].append(rec)
    
    priority_order = [
        RecommendationPriority.IMMEDIATE,
        RecommendationPriority.SHORT_TERM,
        RecommendationPriority.LONG_TERM,
        RecommendationPriority.PREVENTIVE
    ]
    
    for priority in priority_order:
        if by_priority[priority]:
            story.append(Paragraph(f"{priority.value}", subheading_style))
            for rec in by_priority[priority]:
                story.append(Paragraph(f"• {rec.action}", body_style))
                if rec.category:
                    story.append(Paragraph(f"  Category: {rec.category}", body_style))
                if rec.timeframe:
                    story.append(Paragraph(f"  Timeframe: {rec.timeframe}", body_style))
                story.append(Spacer(1, 0.05 * inch))
    
    story.append(PageBreak())
    
    # Conflicts
    if report.conflicts:
        story.append(Paragraph(f"Conflicts Detected ({len(report.conflicts)})", heading_style))
        for conflict in report.conflicts:
            story.append(Paragraph(f"<b>{conflict.conflict_type.value}</b>", subheading_style))
            story.append(Paragraph(conflict.description, body_style))
            if conflict.resolution_suggestion:
                story.append(Paragraph(f"Resolution: {conflict.resolution_suggestion}", body_style))
            story.append(Spacer(1, 0.1 * inch))
    
    # Missing Information
    if report.missing_information:
        story.append(Paragraph("Missing Information", heading_style))
        for info in report.missing_information:
            story.append(Paragraph(f"• {info}", body_style))
    
    # Quality Metrics
    story.append(PageBreak())
    story.append(Paragraph("Quality Metrics", heading_style))
    if report.quality_metrics:
        story.append(Paragraph(f"Overall Quality: {report.quality_metrics.get('overall_quality', 0):.2f}", body_style))
        story.append(Paragraph(f"Completeness: {report.quality_metrics.get('completeness', 0):.2f}", body_style))
        story.append(Paragraph(f"Observation Quality: {report.quality_metrics.get('observation_quality', 0):.2f}", body_style))
        story.append(Paragraph(f"Recommendation Quality: {report.quality_metrics.get('recommendation_quality', 0):.2f}", body_style))
        
        if report.quality_metrics.get('issues'):
            story.append(Paragraph("Issues Identified:", subheading_style))
            for issue in report.quality_metrics['issues']:
                story.append(Paragraph(f"• {issue}", body_style))
    
    # Confidence Metrics
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Confidence Metrics", heading_style))
    if report.confidence_metrics:
        story.append(Paragraph(f"Overall Confidence: {report.confidence_metrics.get('overall_confidence', 0):.2f}", body_style))
        story.append(Paragraph(f"Data Completeness: {report.confidence_metrics.get('data_completeness', 0):.2f}", body_style))
        story.append(Paragraph(f"Observation Quality: {report.confidence_metrics.get('observation_quality', 0):.2f}", body_style))
        story.append(Paragraph(f"AI Certainty: {report.confidence_metrics.get('ai_certainty', 0):.2f}", body_style))
    
    # Build the PDF
    doc.build(story)
    
    # Get the PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes

# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Domain Models
    "SeverityLevel",
    "ConfidenceLevel",
    "RecommendationPriority",
    "ObservationCategory",
    "ConflictType",
    "ReportType",
    "Observation",
    "Conflict",
    "Recommendation",
    "ExecutiveSummary",
    "DDRReport",
    "ReportGenerationMetrics",
    
    # Interfaces
    "IObservationNormalizer",
    "IDuplicateDetector",
    "IRelationshipAnalyzer",
    "ISeverityEngine",
    "IConfidenceEngine",
    "IConflictDetector",
    "IRecommendationEngine",
    "IExecutiveSummaryBuilder",
    "IQualityEngine",
    
    # Implementations
    "ObservationNormalizer",
    "DuplicateDetector",
    "RelationshipAnalyzer",
    "SeverityEngine",
    "ConfidenceEngine",
    "ConflictDetector",
    "RecommendationEngine",
    "ExecutiveSummaryBuilder",
    "QualityEngine",
    "DDRGeneratorEngine",
    
    # Utilities
    "build_ddr_report",
    "validate_ddr_report",
    "generate_pdf",
]

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json
    import sys
    
    parser = argparse.ArgumentParser(description="DDR Intelligence Engine")
    parser.add_argument("input_file", type=str, help="Input JSON file")
    parser.add_argument("--output", "-o", type=str, default="report.pdf", help="Output PDF file")
    parser.add_argument("--images", "-i", type=str, nargs='*', help="Image files")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON instead of PDF")
    
    args = parser.parse_args()
    
    async def main():
        # Load input data
        with open(args.input_file, 'r') as f:
            data = json.load(f)
        
        if args.json:
            # Generate JSON report
            engine = DDRGeneratorEngine()
            report = await engine.generate_report(data)
            print(json.dumps(report.model_dump(), indent=2, default=str))
        else:
            # Generate PDF
            output_path = generate_pdf(data, args.images or [], str(Path(args.output).parent))
            print(f"Report generated successfully: {output_path}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)