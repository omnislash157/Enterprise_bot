"""
Query Heuristics Engine - Deep analysis of query content and patterns.

This module provides sophisticated heuristic analysis beyond simple categorization:
- Query complexity and intent detection
- Department context inference from query content
- Session pattern detection and temporal analysis

Usage:
    from auth.analytics_engine.query_heuristics import (
        QueryComplexityAnalyzer,
        DepartmentContextAnalyzer,
        QueryPatternDetector
    )

    complexity_analyzer = QueryComplexityAnalyzer()
    dept_analyzer = DepartmentContextAnalyzer()
    pattern_detector = QueryPatternDetector(db_pool)

    # Analyze a query
    complexity = complexity_analyzer.analyze(query_text)
    dept_context = dept_analyzer.infer_department_context(query_text, keywords)
    primary_dept = dept_analyzer.get_primary_department(query_text, keywords)
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# =============================================================================
# QUERY COMPLEXITY ANALYZER
# =============================================================================

class QueryComplexityAnalyzer:
    """Analyze query complexity, intent, specificity, and temporal urgency.

    This analyzer provides deep insights into query characteristics beyond
    simple categorization. It evaluates:
    - Complexity (sentence structure, conditional logic, multi-part queries)
    - Intent (information seeking, action-oriented, decision support, verification)
    - Specificity (presence of named entities, numbers, technical terms)
    - Temporal urgency (low, medium, high, urgent)
    """

    # Intent detection patterns
    INTENT_PATTERNS = {
        'INFORMATION_SEEKING': [
            r'\bwhat is\b', r'\btell me about\b', r'\bexplain\b',
            r'\bdefine\b', r'\bdescribe\b', r'\bwho is\b', r'\bwhere is\b'
        ],
        'ACTION_ORIENTED': [
            r'\bhow do i\b', r'\bhow to\b', r'\bsteps to\b',
            r'\bprocedure for\b', r'\bwalk me through\b', r'\bguide me\b',
            r'\bshow me how\b', r'\bhelp me\b'
        ],
        'DECISION_SUPPORT': [
            r'\bshould i\b', r'\bwhich option\b', r'\bbetter to\b',
            r'\brecommend\b', r'\badvise\b', r'\bsuggest\b',
            r'\bcompare\b', r'\bchoose between\b'
        ],
        'VERIFICATION': [
            r'\bis it correct\b', r'\bconfirm\b', r'\bverify\b',
            r'\bcheck if\b', r'\bam i right\b', r'\bis this\b',
            r'\bdoes this\b', r'\bvalidate\b'
        ]
    }

    # Temporal urgency patterns (ordered from most to least urgent)
    URGENCY_PATTERNS = {
        'URGENT': [
            r'\bemergency\b', r'\basap\b', r'\bimmediately\b',
            r'\bright now\b', r'\bcritical\b', r'\bcrisis\b'
        ],
        'HIGH': [
            r'\btoday\b', r'\bnow\b', r'\burgent\b',
            r'\bquickly\b', r'\bsoon as possible\b', r'\bthis hour\b'
        ],
        'MEDIUM': [
            r'\bsoon\b', r'\bthis week\b', r'\bby friday\b',
            r'\bshortly\b', r'\bin a few days\b', r'\bwithin\b'
        ]
    }

    # Multi-part query indicators
    MULTI_PART_PATTERNS = [
        r'\band also\b', r'\badditionally\b', r'\bfurthermore\b',
        r'\bbesides\b', r'\bmoreover\b', r'\bplus\b', r'\balso\b',
        r'\d+[\.\)]\s+',  # Numbered lists like "1. " or "1) "
        r'\n\s*-\s+',     # Bullet points
        r'\?.*\?'         # Multiple question marks
    ]

    # Conditional/complexity indicators
    COMPLEXITY_INDICATORS = [
        r'\bif\b.*\bthen\b', r'\bdepending on\b', r'\bin case of\b',
        r'\bunless\b', r'\bprovided that\b', r'\bwhereas\b',
        r'\bhowever\b', r'\balternatively\b', r'\botherwise\b'
    ]

    # Specificity indicators
    SPECIFICITY_INDICATORS = {
        'numbers': r'\b\d+\b',              # Any number
        'dates': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # Date patterns
        'codes': r'\b[A-Z]{2,}\d{2,}\b',    # Product/part codes like "WH123"
        'technical_terms': r'\b[A-Z]{3,}\b',  # Acronyms (3+ capital letters)
        'proper_nouns': r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'  # Capitalized names
    }

    def analyze(self, query_text: str) -> Dict[str, Any]:
        """Perform comprehensive complexity analysis on a query.

        Args:
            query_text: The query text to analyze

        Returns:
            Dictionary containing:
                - complexity_score (float): 0-1 score indicating overall complexity
                - intent_type (str): Primary intent category
                - specificity_score (float): 0-1 score indicating specificity
                - temporal_indicator (str): Urgency level (LOW/MEDIUM/HIGH/URGENT)
                - multi_part (bool): Whether query has multiple parts

        Example:
            >>> analyzer = QueryComplexityAnalyzer()
            >>> result = analyzer.analyze("How do I process a return for order #12345 immediately?")
            >>> result
            {
                'complexity_score': 0.65,
                'intent_type': 'ACTION_ORIENTED',
                'specificity_score': 0.8,
                'temporal_indicator': 'URGENT',
                'multi_part': False
            }
        """
        if not query_text or not query_text.strip():
            logger.warning("[HEURISTICS] Empty query text provided to analyzer")
            return self._empty_analysis()

        query_lower = query_text.lower().strip()

        complexity_score = self._calculate_complexity(query_text, query_lower)
        intent_type = self._detect_intent(query_lower)
        specificity_score = self._calculate_specificity(query_text)
        temporal_indicator = self._detect_temporal_urgency(query_lower)
        multi_part = self._detect_multi_part(query_text)

        result = {
            'complexity_score': round(complexity_score, 3),
            'intent_type': intent_type,
            'specificity_score': round(specificity_score, 3),
            'temporal_indicator': temporal_indicator,
            'multi_part': multi_part
        }

        logger.debug(
            f"[HEURISTICS] Complexity analysis: "
            f"complexity={result['complexity_score']:.2f}, "
            f"intent={result['intent_type']}, "
            f"specificity={result['specificity_score']:.2f}, "
            f"urgency={result['temporal_indicator']}"
        )

        return result

    def _calculate_complexity(self, query_text: str, query_lower: str) -> float:
        """Calculate query complexity score (0-1).

        Complexity is determined by:
        - Number of sentences (more sentences = more complex)
        - Presence of conditional phrases ("if...then", "depending on")
        - Multi-criteria requests
        - Question depth (nested sub-questions)

        Args:
            query_text: Original query text (for case-sensitive analysis)
            query_lower: Lowercased query text

        Returns:
            Complexity score between 0 and 1
        """
        score = 0.0
        factors = []

        # Factor 1: Sentence count (normalize to 0-0.3 range)
        sentences = re.split(r'[.!?]+', query_text)
        sentence_count = len([s for s in sentences if s.strip()])
        sentence_score = min(sentence_count / 5.0, 1.0) * 0.3
        score += sentence_score
        factors.append(f"sentences={sentence_count}")

        # Factor 2: Conditional phrases (0-0.3 range)
        conditional_count = sum(
            1 for pattern in self.COMPLEXITY_INDICATORS
            if re.search(pattern, query_lower)
        )
        conditional_score = min(conditional_count / 3.0, 1.0) * 0.3
        score += conditional_score
        if conditional_count > 0:
            factors.append(f"conditionals={conditional_count}")

        # Factor 3: Word count (0-0.2 range)
        word_count = len(query_text.split())
        word_score = min(word_count / 50.0, 1.0) * 0.2
        score += word_score
        factors.append(f"words={word_count}")

        # Factor 4: Question count (0-0.2 range)
        question_count = query_text.count('?')
        question_score = min(question_count / 3.0, 1.0) * 0.2
        score += question_score
        if question_count > 1:
            factors.append(f"questions={question_count}")

        logger.debug(f"[HEURISTICS] Complexity factors: {', '.join(factors)} -> {score:.3f}")
        return min(score, 1.0)  # Cap at 1.0

    def _detect_intent(self, query_lower: str) -> str:
        """Detect primary query intent.

        Intent categories:
        - INFORMATION_SEEKING: User wants to learn/understand something
        - ACTION_ORIENTED: User wants to do something (how-to)
        - DECISION_SUPPORT: User needs help choosing/deciding
        - VERIFICATION: User wants to confirm something

        Args:
            query_lower: Lowercased query text

        Returns:
            Intent type string
        """
        intent_scores = {}

        for intent_type, patterns in self.INTENT_PATTERNS.items():
            match_count = sum(1 for pattern in patterns if re.search(pattern, query_lower))
            if match_count > 0:
                intent_scores[intent_type] = match_count

        if intent_scores:
            primary_intent = max(intent_scores.items(), key=lambda x: x[1])[0]
            logger.debug(f"[HEURISTICS] Intent detected: {primary_intent} (scores: {intent_scores})")
            return primary_intent

        # Default to INFORMATION_SEEKING if no patterns match
        logger.debug("[HEURISTICS] No intent patterns matched, defaulting to INFORMATION_SEEKING")
        return 'INFORMATION_SEEKING'

    def _calculate_specificity(self, query_text: str) -> float:
        """Calculate query specificity score (0-1).

        Specificity is determined by presence of:
        - Named entities (proper nouns, product codes)
        - Numerical values
        - Technical terms and acronyms
        - Dates and specific times

        Args:
            query_text: Original query text (case-sensitive)

        Returns:
            Specificity score between 0 and 1
        """
        score = 0.0
        indicators_found = []

        for indicator_type, pattern in self.SPECIFICITY_INDICATORS.items():
            matches = re.findall(pattern, query_text)
            if matches:
                # Weight each indicator type
                weight = 0.25 if indicator_type in ['numbers', 'codes'] else 0.15
                indicator_score = min(len(matches) / 5.0, 1.0) * weight
                score += indicator_score
                indicators_found.append(f"{indicator_type}={len(matches)}")

        if indicators_found:
            logger.debug(f"[HEURISTICS] Specificity indicators: {', '.join(indicators_found)} -> {score:.3f}")
        else:
            logger.debug("[HEURISTICS] No specificity indicators found (generic query)")

        return min(score, 1.0)  # Cap at 1.0

    def _detect_temporal_urgency(self, query_lower: str) -> str:
        """Detect temporal urgency level.

        Urgency levels (from highest to lowest):
        - URGENT: Emergency, immediate action required
        - HIGH: Should be addressed today
        - MEDIUM: Should be addressed soon (this week)
        - LOW: No specific time constraint

        Args:
            query_lower: Lowercased query text

        Returns:
            Urgency level string
        """
        # Check in order of urgency (highest to lowest)
        for urgency_level, patterns in self.URGENCY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    logger.debug(f"[HEURISTICS] Temporal urgency: {urgency_level} (matched: {pattern})")
                    return urgency_level

        # Default to LOW if no temporal indicators
        return 'LOW'

    def _detect_multi_part(self, query_text: str) -> bool:
        """Detect if query has multiple parts.

        Multi-part queries include:
        - Multiple questions
        - Numbered/bulleted lists
        - Explicit connectors ("and also", "additionally")

        Args:
            query_text: Original query text

        Returns:
            True if query has multiple parts
        """
        query_lower = query_text.lower()

        # Check for multi-part patterns
        for pattern in self.MULTI_PART_PATTERNS:
            if re.search(pattern, query_lower):
                logger.debug(f"[HEURISTICS] Multi-part query detected (pattern: {pattern})")
                return True

        # Check for multiple question marks
        question_count = query_text.count('?')
        if question_count > 1:
            logger.debug(f"[HEURISTICS] Multi-part query detected ({question_count} questions)")
            return True

        return False

    def _empty_analysis(self) -> Dict[str, Any]:
        """Return default analysis for empty queries."""
        return {
            'complexity_score': 0.0,
            'intent_type': 'INFORMATION_SEEKING',
            'specificity_score': 0.0,
            'temporal_indicator': 'LOW',
            'multi_part': False
        }


# =============================================================================
# DEPARTMENT CONTEXT ANALYZER
# =============================================================================

class DepartmentContextAnalyzer:
    """Infer department context from query content using keyword matching.

    This analyzer determines which department's knowledge base is being queried
    based on the actual content, not just user dropdown selection. It provides:
    - Probability distribution over all departments
    - Primary (most likely) department
    - Confidence scores for multi-department queries
    """

    # Department-specific keyword dictionaries
    # These are domain knowledge signals that indicate which department is relevant
    DEPARTMENT_SIGNALS = {
        'warehouse': [
            'inventory', 'stock', 'shipping', 'receiving', 'pallet', 'forklift',
            'dock', 'loading', 'unloading', 'warehouse', 'storage', 'bin',
            'pick', 'pack', 'ship', 'freight', 'carrier', 'tracking',
            'backorder', 'restock', 'location', 'aisle', 'shelf'
        ],
        'hr': [
            'payroll', 'benefits', 'vacation', 'pto', 'onboarding', 'performance review',
            'employee', 'hire', 'firing', 'termination', 'salary', 'compensation',
            '401k', 'insurance', 'fmla', 'time off', 'sick leave', 'bereavement',
            'training', 'orientation', 'handbook', 'policy', 'discipline'
        ],
        'it': [
            'password', 'laptop', 'vpn', 'network', 'software', 'access', 'ticket',
            'computer', 'login', 'email', 'printer', 'server', 'database',
            'application', 'system', 'install', 'upgrade', 'backup', 'security',
            'wifi', 'internet', 'connection', 'error message', 'bug'
        ],
        'finance': [
            'invoice', 'payment', 'expense', 'budget', 'reimbursement', 'po',
            'purchase order', 'vendor', 'accounting', 'accounts payable',
            'accounts receivable', 'ledger', 'transaction', 'credit', 'debit',
            'tax', 'audit', 'reconcile', 'billing', 'charge', 'cost'
        ],
        'safety': [
            'accident', 'injury', 'hazard', 'ppe', 'osha', 'incident', 'lockout',
            'tagout', 'loto', 'fall protection', 'first aid', 'emergency',
            'fire extinguisher', 'evacuation', 'safety glasses', 'gloves',
            'hardhat', 'boots', 'chemical', 'spill', 'msds', 'sds'
        ],
        'maintenance': [
            'repair', 'equipment', 'breakdown', 'preventive', 'work order',
            'maintenance', 'fix', 'broken', 'malfunction', 'inspect',
            'service', 'parts', 'replace', 'calibrate', 'lubricate',
            'troubleshoot', 'diagnostic', 'downtime', 'pm schedule'
        ],
        'purchasing': [
            'order', 'supplier', 'quote', 'rfq', 'purchase', 'buy',
            'procurement', 'sourcing', 'vendor selection', 'contract',
            'pricing', 'negotiation', 'lead time', 'delivery', 'catalog',
            'requisition', 'approval', 'budget approval'
        ]
    }

    def infer_department_context(
        self,
        query_text: str,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Infer probability distribution over departments based on query content.

        This method analyzes the query text and extracted keywords to determine
        which department(s) are most relevant. Returns a probability distribution
        showing confidence for each department.

        Args:
            query_text: The query text to analyze
            keywords: Optional list of extracted keywords (can enhance matching)

        Returns:
            Dictionary mapping department names to probability scores (0-1).
            Probabilities sum to 1.0 (normalized distribution).

        Example:
            >>> analyzer = DepartmentContextAnalyzer()
            >>> query = "How do I request a new forklift for the warehouse?"
            >>> result = analyzer.infer_department_context(query)
            >>> result
            {'warehouse': 0.65, 'maintenance': 0.20, 'purchasing': 0.15, ...}
        """
        if not query_text or not query_text.strip():
            logger.warning("[HEURISTICS] Empty query text for department inference")
            return {}

        query_lower = query_text.lower()
        scores = defaultdict(float)

        # Count keyword matches for each department
        for dept, signals in self.DEPARTMENT_SIGNALS.items():
            match_count = 0
            matched_signals = []

            for signal in signals:
                # Use word boundary matching to avoid partial matches
                pattern = r'\b' + re.escape(signal) + r'\b'
                if re.search(pattern, query_lower):
                    match_count += 1
                    matched_signals.append(signal)

            if match_count > 0:
                # Score is match count normalized by total signals for this dept
                # This prevents departments with more signals from dominating
                score = match_count / len(signals)
                scores[dept] = score
                logger.debug(
                    f"[HEURISTICS] Department '{dept}': {match_count} matches "
                    f"({', '.join(matched_signals[:3])}{'...' if len(matched_signals) > 3 else ''})"
                )

        # If we have extracted keywords, boost departments that match them
        if keywords:
            keywords_lower = [kw.lower() for kw in keywords]
            for dept, signals in self.DEPARTMENT_SIGNALS.items():
                keyword_matches = sum(
                    1 for kw in keywords_lower
                    if any(signal in kw or kw in signal for signal in signals)
                )
                if keyword_matches > 0:
                    scores[dept] += keyword_matches * 0.1  # Boost by 10% per keyword match
                    logger.debug(f"[HEURISTICS] Department '{dept}' boosted by {keyword_matches} keyword matches")

        # Normalize to probability distribution
        total = sum(scores.values())
        if total > 0:
            normalized = {dept: score / total for dept, score in scores.items()}
            logger.debug(
                f"[HEURISTICS] Department inference: "
                f"{', '.join(f'{d}={s:.2f}' for d, s in sorted(normalized.items(), key=lambda x: -x[1])[:3])}"
            )
            return normalized

        logger.debug("[HEURISTICS] No department signals detected (general query)")
        return {}

    def get_primary_department(
        self,
        query_text: str,
        keywords: Optional[List[str]] = None,
        min_confidence: float = 0.2
    ) -> str:
        """Get the most likely department based on content.

        Args:
            query_text: The query text to analyze
            keywords: Optional list of extracted keywords
            min_confidence: Minimum confidence threshold (default 0.2)

        Returns:
            Department name (lowercase) or 'general' if no strong signal.
            Only returns a department if confidence exceeds min_confidence.

        Example:
            >>> analyzer = DepartmentContextAnalyzer()
            >>> dept = analyzer.get_primary_department("Reset my password please")
            >>> dept
            'it'
        """
        scores = self.infer_department_context(query_text, keywords)

        if not scores:
            logger.debug("[HEURISTICS] No department context, defaulting to 'general'")
            return 'general'

        # Get department with highest probability
        primary_dept, confidence = max(scores.items(), key=lambda x: x[1])

        # Only return if confidence exceeds threshold
        if confidence >= min_confidence:
            logger.info(
                f"[HEURISTICS] Primary department: '{primary_dept}' "
                f"(confidence: {confidence:.2f})"
            )
            return primary_dept

        logger.debug(
            f"[HEURISTICS] Low confidence ({confidence:.2f} < {min_confidence}), "
            f"defaulting to 'general'"
        )
        return 'general'

    def get_department_confidence(
        self,
        query_text: str,
        keywords: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """Get primary department and its confidence score.

        Args:
            query_text: The query text to analyze
            keywords: Optional list of extracted keywords

        Returns:
            Tuple of (department_name, confidence_score)

        Example:
            >>> analyzer = DepartmentContextAnalyzer()
            >>> dept, conf = analyzer.get_department_confidence("File a safety incident")
            >>> dept, conf
            ('safety', 0.85)
        """
        scores = self.infer_department_context(query_text, keywords)

        if not scores:
            return ('general', 0.0)

        primary_dept, confidence = max(scores.items(), key=lambda x: x[1])
        return (primary_dept, confidence)


# =============================================================================
# QUERY PATTERN DETECTOR
# =============================================================================

class QueryPatternDetector:
    """Detect temporal patterns and anomalies in query behavior.

    This analyzer looks at sequences of queries within sessions and across
    time to identify patterns like:
    - Exploratory behavior (diverse questions)
    - Focused troubleshooting (repeated topic)
    - Escalation patterns (increasing frustration)
    - Onboarding sequences (procedural questions)
    """

    def __init__(self, db_pool):
        """Initialize pattern detector with database pool.

        Args:
            db_pool: PostgreSQL connection pool for querying query logs
        """
        self.db_pool = db_pool
        self.pattern_cache = {}  # Cache recent pattern analysis

    @contextmanager
    def _get_cursor(self):
        """Get database cursor from pool."""
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                yield cur
        finally:
            self.db_pool.putconn(conn)

    def detect_query_sequence_pattern(
        self,
        user_email: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Analyze the sequence of queries in a session to detect patterns.

        Pattern types:
        - EXPLORATORY: Many diverse questions across different topics/departments
        - FOCUSED: Repeated queries on the same topic (drilling down)
        - TROUBLESHOOTING_ESCALATION: Questions showing increasing frustration
        - ONBOARDING: Sequential procedural questions (how-to pattern)
        - SINGLE_QUERY: Only one query in session (no pattern yet)

        Args:
            user_email: User's email address
            session_id: Current session ID

        Returns:
            Dictionary containing:
                - pattern_type (str): Detected pattern category
                - confidence (float): Confidence in pattern detection (0-1)
                - query_count (int): Number of queries in session
                - details (dict): Additional pattern-specific details

        Example:
            >>> detector = QueryPatternDetector(db_pool)
            >>> pattern = detector.detect_query_sequence_pattern(
            ...     "user@example.com", "session123"
            ... )
            >>> pattern
            {
                'pattern_type': 'TROUBLESHOOTING_ESCALATION',
                'confidence': 0.85,
                'query_count': 5,
                'details': {'frustration_increase': True, 'repeat_queries': 2}
            }
        """
        # Check cache first (reduces DB load)
        cache_key = f"{user_email}:{session_id}"
        if cache_key in self.pattern_cache:
            cached_time, cached_result = self.pattern_cache[cache_key]
            # Cache valid for 60 seconds
            if (datetime.utcnow() - cached_time).total_seconds() < 60:
                logger.debug(f"[HEURISTICS] Using cached pattern for session {session_id}")
                return cached_result

        try:
            with self._get_cursor() as cur:
                # Get all queries in this session, ordered by time
                cur.execute("""
                    SELECT
                        query_text,
                        query_category,
                        frustration_signals,
                        is_repeat_question,
                        department_context_inferred,
                        created_at
                    FROM enterprise.query_log
                    WHERE user_email = %s
                      AND session_id = %s
                    ORDER BY created_at ASC
                """, (user_email, session_id))

                queries = cur.fetchall()

        except Exception as e:
            logger.error(f"[HEURISTICS] Failed to fetch session queries: {e}")
            return self._default_pattern()

        if not queries:
            return self._default_pattern()

        query_count = len(queries)

        # Single query - no pattern yet
        if query_count == 1:
            result = {
                'pattern_type': 'SINGLE_QUERY',
                'confidence': 1.0,
                'query_count': 1,
                'details': {}
            }
            self._cache_pattern(cache_key, result)
            return result

        # Analyze query sequence
        pattern_type, confidence, details = self._analyze_sequence(queries)

        result = {
            'pattern_type': pattern_type,
            'confidence': round(confidence, 3),
            'query_count': query_count,
            'details': details
        }

        logger.info(
            f"[HEURISTICS] Session pattern detected: {pattern_type} "
            f"(confidence={confidence:.2f}, queries={query_count})"
        )

        self._cache_pattern(cache_key, result)
        return result

    def _analyze_sequence(self, queries: List[tuple]) -> Tuple[str, float, Dict[str, Any]]:
        """Analyze query sequence to determine pattern type.

        Args:
            queries: List of query tuples from database

        Returns:
            Tuple of (pattern_type, confidence, details)
        """
        query_count = len(queries)
        categories = [q[1] for q in queries if q[1]]  # query_category
        departments = [q[4] for q in queries if q[4]]  # department_context_inferred
        frustration_signals = [q[2] for q in queries if q[2]]  # frustration_signals
        repeat_count = sum(1 for q in queries if q[3])  # is_repeat_question

        # Pattern detection heuristics

        # 1. TROUBLESHOOTING_ESCALATION: Frustration increasing + repeats
        if len(frustration_signals) >= 2 or repeat_count >= 2:
            confidence = min(
                0.5 + (len(frustration_signals) * 0.15) + (repeat_count * 0.2),
                1.0
            )
            details = {
                'frustration_signals': len(frustration_signals),
                'repeat_queries': repeat_count,
                'frustration_increase': len(frustration_signals) > query_count / 3
            }
            return ('TROUBLESHOOTING_ESCALATION', confidence, details)

        # 2. FOCUSED: Same category or department repeated
        if categories:
            most_common_category = Counter(categories).most_common(1)[0]
            category_concentration = most_common_category[1] / len(categories)

            if category_concentration >= 0.7:  # 70% same category
                confidence = category_concentration
                details = {
                    'dominant_category': most_common_category[0],
                    'concentration': round(category_concentration, 2)
                }
                return ('FOCUSED', confidence, details)

        # 3. ONBOARDING: High proportion of procedural queries
        if categories:
            procedural_count = sum(1 for cat in categories if cat == 'PROCEDURAL')
            procedural_ratio = procedural_count / len(categories)

            if procedural_ratio >= 0.6:  # 60% procedural
                confidence = procedural_ratio
                details = {
                    'procedural_queries': procedural_count,
                    'total_queries': len(categories)
                }
                return ('ONBOARDING', confidence, details)

        # 4. EXPLORATORY: Diverse topics/departments
        unique_categories = len(set(categories)) if categories else 0
        unique_departments = len(set(departments)) if departments else 0

        diversity_score = (unique_categories / query_count) if query_count > 0 else 0

        if diversity_score >= 0.6:  # High diversity
            confidence = diversity_score
            details = {
                'unique_categories': unique_categories,
                'unique_departments': unique_departments,
                'diversity_score': round(diversity_score, 2)
            }
            return ('EXPLORATORY', confidence, details)

        # Default: Insufficient data for pattern
        return ('MIXED', 0.5, {
            'query_count': query_count,
            'unique_categories': unique_categories
        })

    def _cache_pattern(self, cache_key: str, result: Dict[str, Any]):
        """Cache pattern analysis result."""
        self.pattern_cache[cache_key] = (datetime.utcnow(), result)

        # Limit cache size to 1000 entries
        if len(self.pattern_cache) > 1000:
            # Remove oldest 100 entries
            sorted_items = sorted(
                self.pattern_cache.items(),
                key=lambda x: x[1][0]
            )
            for key, _ in sorted_items[:100]:
                del self.pattern_cache[key]

    def _default_pattern(self) -> Dict[str, Any]:
        """Return default pattern when no data available."""
        return {
            'pattern_type': 'SINGLE_QUERY',
            'confidence': 0.0,
            'query_count': 0,
            'details': {}
        }

    def detect_department_usage_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze department query trends over time.

        This method provides insights into:
        - Peak usage times per department
        - Emerging topics (sudden spike in category)
        - Declining topics
        - Cross-department query flows

        Args:
            hours: Number of hours to analyze (default 24)

        Returns:
            Dictionary containing trend analysis data
        """
        try:
            with self._get_cursor() as cur:
                # Get hourly department usage
                cur.execute("""
                    SELECT
                        department_context_inferred,
                        DATE_TRUNC('hour', created_at) as hour,
                        COUNT(*) as query_count
                    FROM enterprise.query_log
                    WHERE created_at > NOW() - INTERVAL '%s hours'
                      AND department_context_inferred IS NOT NULL
                    GROUP BY department_context_inferred, hour
                    ORDER BY hour ASC
                """, (hours,))

                hourly_data = cur.fetchall()

                # Get category trends
                cur.execute("""
                    SELECT
                        query_category,
                        DATE_TRUNC('hour', created_at) as hour,
                        COUNT(*) as query_count
                    FROM enterprise.query_log
                    WHERE created_at > NOW() - INTERVAL '%s hours'
                      AND query_category IS NOT NULL
                    GROUP BY query_category, hour
                    ORDER BY hour ASC
                """, (hours,))

                category_trends = cur.fetchall()

        except Exception as e:
            logger.error(f"[HEURISTICS] Failed to fetch department trends: {e}")
            return {'error': str(e)}

        # Process hourly data to find peaks
        dept_peaks = self._find_peak_hours(hourly_data)
        emerging = self._detect_emerging_topics(category_trends)

        result = {
            'peak_hours': dept_peaks,
            'emerging_topics': emerging,
            'hours_analyzed': hours,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(
            f"[HEURISTICS] Department trends: {len(dept_peaks)} peak hours, "
            f"{len(emerging)} emerging topics"
        )

        return result

    def _find_peak_hours(self, hourly_data: List[tuple]) -> List[Dict[str, Any]]:
        """Find peak usage hours for each department."""
        dept_hours = defaultdict(list)

        for dept, hour, count in hourly_data:
            dept_hours[dept].append((hour, count))

        peaks = []
        for dept, hours in dept_hours.items():
            if not hours:
                continue

            # Find hour with max queries
            peak_hour, peak_count = max(hours, key=lambda x: x[1])
            avg_count = sum(h[1] for h in hours) / len(hours)

            peaks.append({
                'department': dept,
                'peak_hour': peak_hour.isoformat() if hasattr(peak_hour, 'isoformat') else str(peak_hour),
                'peak_count': peak_count,
                'avg_count': round(avg_count, 1)
            })

        return peaks

    def _detect_emerging_topics(self, category_trends: List[tuple]) -> List[Dict[str, Any]]:
        """Detect emerging topics (categories with sudden spike)."""
        category_hours = defaultdict(list)

        for category, hour, count in category_trends:
            category_hours[category].append(count)

        emerging = []
        for category, counts in category_hours.items():
            if len(counts) < 3:  # Need at least 3 hours of data
                continue

            # Check if recent counts are significantly higher than average
            recent_avg = sum(counts[-3:]) / 3
            overall_avg = sum(counts) / len(counts)

            if recent_avg > overall_avg * 1.5:  # 50% increase
                emerging.append({
                    'category': category,
                    'recent_avg': round(recent_avg, 1),
                    'overall_avg': round(overall_avg, 1),
                    'increase_factor': round(recent_avg / overall_avg, 2)
                })

        return sorted(emerging, key=lambda x: x['increase_factor'], reverse=True)

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalous query patterns.

        Anomalies include:
        - Sudden spike in error rate
        - Unusual query volume
        - New query categories appearing
        - Repeated failed queries (same user, same question)

        Returns:
            List of detected anomalies with details
        """
        anomalies = []

        try:
            with self._get_cursor() as cur:
                # Check for spike in repeat questions (last hour vs previous 24h)
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour' AND is_repeat_question = true) as recent_repeats,
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as recent_total,
                        COUNT(*) FILTER (WHERE created_at BETWEEN NOW() - INTERVAL '25 hours' AND NOW() - INTERVAL '1 hour' AND is_repeat_question = true) as historical_repeats,
                        COUNT(*) FILTER (WHERE created_at BETWEEN NOW() - INTERVAL '25 hours' AND NOW() - INTERVAL '1 hour') as historical_total
                    FROM enterprise.query_log
                """)

                repeat_stats = cur.fetchone()

                if repeat_stats:
                    recent_repeats, recent_total, hist_repeats, hist_total = repeat_stats

                    if recent_total > 0 and hist_total > 0:
                        recent_rate = recent_repeats / recent_total
                        hist_rate = hist_repeats / hist_total if hist_total > 0 else 0

                        # Alert if recent repeat rate is 2x historical average
                        if recent_rate > hist_rate * 2 and recent_rate > 0.3:
                            anomalies.append({
                                'type': 'HIGH_REPEAT_RATE',
                                'severity': 'WARNING',
                                'recent_rate': round(recent_rate, 2),
                                'historical_rate': round(hist_rate, 2),
                                'message': f'Repeat question rate spiked to {recent_rate:.0%} (normal: {hist_rate:.0%})'
                            })

        except Exception as e:
            logger.error(f"[HEURISTICS] Failed to detect anomalies: {e}")
            anomalies.append({
                'type': 'DETECTION_ERROR',
                'severity': 'ERROR',
                'message': f'Anomaly detection failed: {str(e)}'
            })

        logger.info(f"[HEURISTICS] Detected {len(anomalies)} anomalies")
        return anomalies
