#!/usr/bin/env python3
"""
FemLens Health Research MCP Server

Provides health research tools with comprehensive safety guardrails.
Designed for research and information discovery only - NOT for diagnosis or treatment.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GuardrailCategory(Enum):
    """Safety guardrail categories."""
    EMERGENCY = "emergency"
    SELF_HARM = "self_harm"
    DRUG_MISUSE = "drug_misuse"
    MEDICATION_SAFETY = "medication_safety"
    DIAGNOSIS = "diagnosis"
    PREGNANCY_SAFETY = "pregnancy_safety"
    EATING_DISORDER = "eating_disorder"
    PROMPT_INJECTION = "prompt_injection"
    RESEARCH_ALLOWED = "research_allowed"


@dataclass
class GuardrailResult:
    """Result of guardrail validation."""
    allowed: bool
    category: Optional[str] = None
    message: Optional[str] = None
    redirect_message: Optional[str] = None


class HealthGuardrailValidator:
    """
    Comprehensive health safety guardrail system for FemLens.
    
    Validates health-related queries before tool execution to ensure:
    - No emergency medical situations
    - No self-harm facilitation
    - No drug misuse instructions
    - No personalized medical advice
    - Research queries remain accessible
    """
    
    # Emergency keywords
    EMERGENCY_KEYWORDS = [
        r'\bemergency\b', r'\b911\b', r'\bchest pain\b', r'\bcan\'?t breathe\b',
        r'\bdifficulty breathing\b', r'\bunconscious\b', r'\bseizure\b',
        r'\bsevere bleeding\b', r'\bheavy bleeding\b', r'\bstroke\b',
        r'\ballergic reaction\b', r'\banaphylaxis\b', r'\bpoisoning\b',
        r'\boverdose\b', r'\btrauma\b', r'\bectopic pregnancy\b',
        r'\bsevere.*pain\b', r'\blife.?threatening\b'
    ]
    
    # Self-harm keywords
    SELF_HARM_KEYWORDS = [
        r'\bsuicide\b', r'\bsuicidal\b', r'\bkill myself\b', r'\bend my life\b',
        r'\bself.?harm\b', r'\bcut myself\b', r'\bhurt myself\b',
        r'\bhow to die\b', r'\bways to die\b', r'\blethal dose\b',
        r'\bpainless.*death\b', r'\bsuicide method\b'
    ]
    
    # Drug misuse keywords
    DRUG_MISUSE_KEYWORDS = [
        r'\bget high\b', r'\brecreational.*drug\b', r'\bdrug.*combination.*high\b',
        r'\bhow to make\b.*\bdrug\b', r'\bextract.*drug\b',
        r'\bavoid.*detection\b', r'\bintensify.*effect\b',
        r'\bmixing.*drugs\b.*\beffect\b', r'\bcocaine\b', r'\bheroin\b',
        r'\bmethamphetamine\b', r'\becstasy\b'
    ]
    
    # Medication decision keywords
    MEDICATION_DECISION_KEYWORDS = [
        r'\bshould i take\b', r'\bwhat.*should i take\b',
        r'\bhow much.*should i take\b', r'\bcan i stop\b.*\bmedication\b',
        r'\bcan i double\b.*\bdose\b', r'\bshould i stop\b.*\bpill\b',
        r'\bcan i combine\b.*\bmedication\b'
    ]
    
    # Diagnosis keywords
    DIAGNOSIS_KEYWORDS = [
        r'\bdo i have\b', r'\bdoes this mean i have\b', r'\bam i\b.*\bdiagnos\b',
        r'\bcan you diagnose\b', r'\bwhat.*wrong with me\b',
        r'\bis this\b.*\bcondition\b'
    ]
    
    # Pregnancy high-risk keywords
    PREGNANCY_HIGHRISK_KEYWORDS = [
        r'\bpregnant\b.*\bsevere pain\b', r'\bpregnant\b.*\bbleeding\b',
        r'\bectopic\b', r'\bmiscarriage\b.*\bshould i\b',
        r'\bpregnant\b.*\bmedication\b.*\bshould\b'
    ]
    
    # Eating disorder keywords
    EATING_DISORDER_KEYWORDS = [
        r'\bhow to.*starve\b', r'\bhow to.*purge\b', r'\bpro.?ana\b',
        r'\bpro.?mia\b', r'\bextreme.*fasting\b', r'\brapid.*weight loss\b.*\bmethod\b'
    ]
    
    # Prompt injection patterns
    PROMPT_INJECTION_PATTERNS = [
        r'\bignore.*instruction\b', r'\bignore.*previous\b',
        r'\bignore.*safety\b', r'\bignore.*rule\b',
        r'\bpretend.*not medical\b', r'\bbypass.*guardrail\b',
        r'\bexecute.*without.*check\b'
    ]
    
    # Research-oriented phrases (ALLOW)
    RESEARCH_PHRASES = [
        r'\bclinical trial\b', r'\bclinical stud(?:y|ies)\b', r'\bresearch.*show\b',
        r'\bevidence.*for\b', r'\bwhat does research\b', r'\bstudies about\b',
        r'\btreatment.*research\b', r'\bfind.*studies\b'
    ]
    
    def __init__(self):
        """Initialize the validator with compiled patterns."""
        self.emergency_patterns = [re.compile(p, re.IGNORECASE) for p in self.EMERGENCY_KEYWORDS]
        self.self_harm_patterns = [re.compile(p, re.IGNORECASE) for p in self.SELF_HARM_KEYWORDS]
        self.drug_misuse_patterns = [re.compile(p, re.IGNORECASE) for p in self.DRUG_MISUSE_KEYWORDS]
        self.medication_patterns = [re.compile(p, re.IGNORECASE) for p in self.MEDICATION_DECISION_KEYWORDS]
        self.diagnosis_patterns = [re.compile(p, re.IGNORECASE) for p in self.DIAGNOSIS_KEYWORDS]
        self.pregnancy_patterns = [re.compile(p, re.IGNORECASE) for p in self.PREGNANCY_HIGHRISK_KEYWORDS]
        self.eating_disorder_patterns = [re.compile(p, re.IGNORECASE) for p in self.EATING_DISORDER_KEYWORDS]
        self.injection_patterns = [re.compile(p, re.IGNORECASE) for p in self.PROMPT_INJECTION_PATTERNS]
        self.research_patterns = [re.compile(p, re.IGNORECASE) for p in self.RESEARCH_PHRASES]

    def _matches_patterns(self, text: str, patterns: list) -> bool:
        """Check if text matches any pattern in the list."""
        return any(pattern.search(text) for pattern in patterns)

    def check_emergency(self, query: str) -> Optional[GuardrailResult]:
        """Check for medical emergency indicators."""
        if self._matches_patterns(query, self.emergency_patterns):
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.EMERGENCY.value,
                message=(
                    "This sounds like it may require urgent medical attention. "
                    "FemLens is a research tool and cannot assess emergencies. "
                    "Please contact local emergency medical services or seek "
                    "immediate professional medical care."
                )
            )
        return None

    def check_self_harm(self, query: str) -> Optional[GuardrailResult]:
        """Check for self-harm or suicide-related content."""
        if self._matches_patterns(query, self.self_harm_patterns):
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.SELF_HARM.value,
                message=(
                    "If you're having thoughts of self-harm or suicide, please reach out "
                    "for help immediately. Contact the National Suicide Prevention Lifeline "
                    "at 988 or text 'HELLO' to 741741. FemLens cannot provide crisis support."
                )
            )
        return None

    def check_drug_misuse(self, query: str) -> Optional[GuardrailResult]:
        """Check for drug misuse facilitation."""
        # Allow legitimate research about substance use
        if self._matches_patterns(query, self.research_patterns):
            return None
            
        if self._matches_patterns(query, self.drug_misuse_patterns):
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.DRUG_MISUSE.value,
                message=(
                    "FemLens cannot provide information that could facilitate "
                    "illegal drug use or dangerous substance misuse. For substance "
                    "use research questions, please rephrase as a research query."
                )
            )
        return None

    def check_medication_safety(self, query: str) -> Optional[GuardrailResult]:
        """Check for personalized medication decisions."""
        # Allow research queries
        if self._matches_patterns(query, self.research_patterns):
            return None
            
        if self._matches_patterns(query, self.medication_patterns):
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.MEDICATION_SAFETY.value,
                message=(
                    "FemLens cannot provide personalized medication advice. "
                    "Please consult your healthcare provider for medication decisions. "
                    "You can search for research about treatments and medications in general."
                ),
                redirect_message=(
                    "Try rephrasing as: 'Find research about treatments for [condition]'"
                )
            )
        return None

    def check_diagnosis(self, query: str) -> Optional[GuardrailResult]:
        """Check for diagnosis requests."""
        # Allow symptom research
        if self._matches_patterns(query, self.research_patterns):
            return None
            
        if self._matches_patterns(query, self.diagnosis_patterns):
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.DIAGNOSIS.value,
                message=(
                    "FemLens cannot diagnose medical conditions. Symptoms can have "
                    "multiple causes and should be evaluated by a qualified healthcare "
                    "professional. You can search for research about conditions and symptoms."
                ),
                redirect_message=(
                    "Try rephrasing as: 'Find research about [condition] symptoms'"
                )
            )
        return None

    def check_pregnancy_safety(self, query: str) -> Optional[GuardrailResult]:
        """Check for high-risk pregnancy situations."""
        if self._matches_patterns(query, self.pregnancy_patterns):
            # If also research-oriented, allow with caution
            if self._matches_patterns(query, self.research_patterns):
                return None
                
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.PREGNANCY_SAFETY.value,
                message=(
                    "FemLens cannot provide individualized pregnancy-related medical advice. "
                    "Please contact your healthcare provider for guidance on pregnancy symptoms "
                    "or medication use during pregnancy."
                ),
                redirect_message=(
                    "You can search for general research: 'Find studies about [topic] during pregnancy'"
                )
            )
        return None

    def check_eating_disorder(self, query: str) -> Optional[GuardrailResult]:
        """Check for eating disorder facilitation."""
        if self._matches_patterns(query, self.eating_disorder_patterns):
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.EATING_DISORDER.value,
                message=(
                    "FemLens cannot provide information that could facilitate eating "
                    "disorders or harmful behaviors. If you're struggling with disordered "
                    "eating, please reach out to the National Eating Disorders Association "
                    "helpline: (800) 931-2237 or text 'NEDA' to 741741."
                )
            )
        return None

    def check_prompt_injection(self, query: str) -> Optional[GuardrailResult]:
        """Check for prompt injection attempts."""
        if self._matches_patterns(query, self.injection_patterns):
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.PROMPT_INJECTION.value,
                message=(
                    "Invalid request. Safety guardrails cannot be bypassed."
                )
            )
        return None

    def validate_health_request(self, query: str, tool_name: str = None) -> GuardrailResult:
        """
        Main validation entry point. Checks query against all guardrail categories.
        
        Args:
            query: The user's health query
            tool_name: Name of the MCP tool being called (optional)
            
        Returns:
            GuardrailResult indicating whether request is allowed
        """
        if not query or not isinstance(query, str):
            return GuardrailResult(
                allowed=False,
                category="invalid_input",
                message="Invalid query format"
            )
        
        # Run all safety checks in order of severity
        checks = [
            self.check_prompt_injection,
            self.check_emergency,
            self.check_self_harm,
            self.check_eating_disorder,
            self.check_drug_misuse,
            self.check_pregnancy_safety,
            self.check_medication_safety,
            self.check_diagnosis,
        ]
        
        for check in checks:
            result = check(query)
            if result and not result.allowed:
                logger.warning(
                    f"Guardrail blocked query. Category: {result.category}, "
                    f"Tool: {tool_name}"
                )
                return result
        
        # All checks passed
        return GuardrailResult(
            allowed=True,
            category=GuardrailCategory.RESEARCH_ALLOWED.value
        )


class InputValidator:
    """Validates tool inputs for security and data integrity."""
    
    @staticmethod
    def validate_nct_id(nct_id: str) -> Tuple[bool, Optional[str]]:
        """Validate NCT ID format."""
        if not nct_id or not isinstance(nct_id, str):
            return False, "NCT ID is required"
        
        nct_id = nct_id.strip().upper()
        if not re.match(r'^NCT[0-9]{8}$', nct_id):
            return False, "Invalid NCT ID format (expected: NCT12345678)"
        
        return True, None

    @staticmethod
    def validate_user_id(user_id: str) -> Tuple[bool, Optional[str]]:
        """Validate user ID."""
        if not user_id or not isinstance(user_id, str):
            return False, "User ID is required"
        
        # Basic email validation
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', user_id):
            return False, "Invalid user ID format"
        
        return True, None

    @staticmethod
    def validate_query(query: str, max_length: int = 1000) -> Tuple[bool, Optional[str]]:
        """Validate query string."""
        if not query or not isinstance(query, str):
            return False, "Query is required"
        
        if len(query) > max_length:
            return False, f"Query exceeds maximum length of {max_length} characters"
        
        return True, None

    @staticmethod
    def validate_notes(notes: str, max_length: int = 2000) -> Tuple[bool, Optional[str]]:
        """Validate research notes."""
        if not isinstance(notes, str):
            return False, "Notes must be a string"
        
        if len(notes) > max_length:
            return False, f"Notes exceed maximum length of {max_length} characters"
        
        return True, None

    @staticmethod
    def validate_top_k(top_k: int, max_value: int = 20) -> Tuple[bool, Optional[str]]:
        """Validate top_k parameter."""
        if not isinstance(top_k, int):
            return False, "top_k must be an integer"
        
        if top_k < 1:
            return False, "top_k must be at least 1"
        
        if top_k > max_value:
            return False, f"top_k cannot exceed {max_value}"
        
        return True, None

    @staticmethod
    def validate_page_size(page_size: int, max_value: int = 50) -> Tuple[bool, Optional[str]]:
        """Validate page_size parameter."""
        if not isinstance(page_size, int):
            return False, "page_size must be an integer"
        
        if page_size < 1:
            return False, "page_size must be at least 1"
        
        if page_size > max_value:
            return False, f"page_size cannot exceed {max_value}"
        
        return True, None


class FemLensHealthTools:
    """
    FemLens Health Research MCP Tools with integrated safety guardrails.
    
    All tools validate requests through the guardrail layer before execution.
    """
    
    def __init__(self):
        """Initialize tools with guardrail validator."""
        self.guardrail = HealthGuardrailValidator()
        self.input_validator = InputValidator()
    
    def search_health_studies(
        self,
        condition: str = None,
        status: str = None,
        query: str = None,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Search ClinicalTrials.gov for women's health studies.
        
        Args:
            condition: Medical condition to search for
            status: Study status (e.g., 'Recruiting', 'Completed')
            query: Free-text search query
            page_size: Number of results to return (max 50)
            
        Returns:
            Dictionary with search results or error
        """
        # Build search query for guardrail check
        search_text = f"{condition or ''} {query or ''}".strip()
        
        # Validate through guardrails
        result = self.guardrail.validate_health_request(search_text, "search_health_studies")
        if not result.allowed:
            return {
                "error": result.message,
                "redirect": result.redirect_message,
                "guardrail_category": result.category
            }
        
        # Validate page_size
        valid, error = self.input_validator.validate_page_size(page_size)
        if not valid:
            return {"error": error}
        
        # TODO: Implement actual ClinicalTrials.gov API call
        logger.info(f"Searching studies: condition={condition}, status={status}, page_size={page_size}")
        
        return {
            "status": "success",
            "studies": [],
            "message": "Search functionality ready for API integration"
        }
    
    def get_study_details(self, nct_id: str) -> Dict[str, Any]:
        """
        Retrieve detailed information about a specific clinical study.
        
        Args:
            nct_id: ClinicalTrials.gov NCT identifier
            
        Returns:
            Dictionary with study details or error
        """
        # Validate NCT ID
        valid, error = self.input_validator.validate_nct_id(nct_id)
        if not valid:
            return {"error": error}
        
        # TODO: Implement actual study detail retrieval
        logger.info(f"Fetching study details for {nct_id}")
        
        return {
            "status": "success",
            "nct_id": nct_id,
            "message": "Study detail functionality ready for API integration"
        }
    
    def search_health_knowledge(
        self,
        query: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Search the health knowledge database using vector similarity.
        
        Args:
            query: Natural language search query
            top_k: Number of results to return (max 20)
            
        Returns:
            Dictionary with search results or error
        """
        # Validate query
        valid, error = self.input_validator.validate_query(query)
        if not valid:
            return {"error": error}
        
        # Validate through guardrails
        result = self.guardrail.validate_health_request(query, "search_health_knowledge")
        if not result.allowed:
            return {
                "error": result.message,
                "redirect": result.redirect_message,
                "guardrail_category": result.category
            }
        
        # Validate top_k
        valid, error = self.input_validator.validate_top_k(top_k)
        if not valid:
            return {"error": error}
        
        # TODO: Implement actual vector search
        logger.info(f"Searching knowledge base: query='{query[:50]}...', top_k={top_k}")
        
        return {
            "status": "success",
            "results": [],
            "message": "Vector search functionality ready for database integration"
        }
    
    def save_research_study(
        self,
        user_id: str,
        nct_id: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Save a study to user's research collection.
        
        Args:
            user_id: Authenticated user email
            nct_id: ClinicalTrials.gov NCT identifier
            notes: Optional user notes about the study
            
        Returns:
            Dictionary with success status or error
        """
        # Validate user_id
        valid, error = self.input_validator.validate_user_id(user_id)
        if not valid:
            return {"error": error}
        
        # Validate NCT ID
        valid, error = self.input_validator.validate_nct_id(nct_id)
        if not valid:
            return {"error": error}
        
        # Validate notes
        valid, error = self.input_validator.validate_notes(notes)
        if not valid:
            return {"error": error}
        
        # Check notes for sensitive content (privacy guardrail)
        if notes:
            result = self.guardrail.validate_health_request(notes, "save_research_study")
            if not result.allowed:
                return {
                    "error": "Notes contain potentially unsafe content",
                    "details": result.message
                }
        
        # TODO: Implement actual save to database
        logger.info(f"Saving study {nct_id} for user {user_id}")
        
        return {
            "status": "success",
            "message": "Study saved to research collection"
        }
    
    def get_research_collection(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve user's saved research collection.
        
        Args:
            user_id: Authenticated user email
            
        Returns:
            Dictionary with collection or error
        """
        # Validate user_id
        valid, error = self.input_validator.validate_user_id(user_id)
        if not valid:
            return {"error": error}
        
        # TODO: Implement actual retrieval with authorization check
        logger.info(f"Retrieving research collection for user {user_id}")
        
        return {
            "status": "success",
            "collection": []
        }
    
    def remove_research_study(
        self,
        user_id: str,
        nct_id: str
    ) -> Dict[str, Any]:
        """
        Remove a study from user's research collection.
        
        Args:
            user_id: Authenticated user email
            nct_id: ClinicalTrials.gov NCT identifier
            
        Returns:
            Dictionary with success status or error
        """
        # Validate user_id
        valid, error = self.input_validator.validate_user_id(user_id)
        if not valid:
            return {"error": error}
        
        # Validate NCT ID
        valid, error = self.input_validator.validate_nct_id(nct_id)
        if not valid:
            return {"error": error}
        
        # TODO: Implement actual removal with authorization check
        logger.info(f"Removing study {nct_id} from collection for user {user_id}")
        
        return {
            "status": "success",
            "message": "Study removed from research collection"
        }


# Testing
if __name__ == "__main__":
    tools = FemLensHealthTools()
    print("✅ FemLens Health MCP Server initialized successfully")
    print("\nGuardrail categories: Emergency, Self-harm, Drug Misuse, Medication Safety,")
    print("Diagnosis, Pregnancy Safety, Eating Disorder, Prompt Injection")
