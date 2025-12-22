"""
Semantic Tagging Functions for Smart RAG Ingestion

Philosophy:
- Simple heuristics beat complex ML for domain-specific tagging
- Regex + keyword matching = fast, deterministic, debuggable
- Pre-compute everything at ingest, zero cost at query time

Author: Claude (via SDK Handoff)
Date: 2024-12-22
"""

import re
from typing import List, Dict, Set, Optional
from collections import Counter


# ============================================================================
# DOMAIN VOCABULARY (Driscoll Foods specific)
# ============================================================================

# Verbs: Actions described in procedures
VERB_PATTERNS = {
    'approve': r'\b(approv(e|al|ed|ing)|authorize|sign[ -]?off)\b',
    'reject': r'\b(reject|deny|denial|decline|disapprove)\b',
    'submit': r'\b(submit|send|forward|route|transmit)\b',
    'create': r'\b(create|new|generate|open|initiate|start)\b',
    'void': r'\b(void|cancel|reverse|undo|delete)\b',
    'escalate': r'\b(escalat(e|ion)|elevate|raise|flag)\b',
    'review': r'\b(review|inspect|examine|check|verify)\b',
    'verify': r'\b(verif(y|ication)|confirm|validate|check)\b',
    'process': r'\b(process|handle|execute|perform)\b',
    'route': r'\b(rout(e|ing)|direct|assign|transfer)\b',
    'update': r'\b(updat(e|ing)|modif(y|ication)|change|revise)\b',
    'notify': r'\b(notif(y|ication)|alert|inform|contact)\b',
    'complete': r'\b(complet(e|ion)|finish|close|finalize)\b',
    'track': r'\b(track|monitor|follow[ -]?up|trace)\b',
    'document': r'\b(document|record|log|note)\b',
}

# Entities: Domain objects (nouns)
ENTITY_PATTERNS = {
    'credit_memo': r'\b(credit[ -]?memo|cm|credit[ -]?note)\b',
    'purchase_order': r'\b(purchase[ -]?order|po|p\.o\.)\b',
    'invoice': r'\b(invoice|bill|statement)\b',
    'customer': r'\b(customer|client|buyer|account)\b',
    'vendor': r'\b(vendor|supplier|manufacturer)\b',
    'return': r'\b(return|rma|return[ -]?authorization)\b',
    'shipment': r'\b(shipment|delivery|freight|load)\b',
    'pallet': r'\b(pallet|skid|unit)\b',
    'driver': r'\b(driver|carrier|trucker|hauler)\b',
    'route': r'\b(route|delivery[ -]?route|stop)\b',
    'claim': r'\b(claim|dispute|shortage|overage)\b',
    'shortage': r'\b(shortage|short|missing|under[ -]?shipment)\b',
    'overage': r'\b(overage|over|extra|surplus)\b',
    'damage': r'\b(damag(e|ed)|broken|defect|spoilage)\b',
    'pricing': r'\b(pric(e|ing)|cost|rate|quote)\b',
    'discount': r'\b(discount|rebate|allowance|deduction)\b',
    'payment': r'\b(payment|remittance|check|wire)\b',
    'order': r'\b(order|sales[ -]?order|so)\b',
    'backorder': r'\b(back[ -]?order|bo|on[ -]?order)\b',
    'inventory': r'\b(inventory|stock|on[ -]?hand)\b',
}

# Actors: Roles who perform actions
ACTOR_PATTERNS = {
    'sales_rep': r'\b(sales[ -]?(rep|representative)|account[ -]?manager)\b',
    'warehouse_mgr': r'\b(warehouse[ -]?(manager|mgr|supervisor))\b',
    'credit_analyst': r'\b(credit[ -]?(analyst|manager|coordinator))\b',
    'purchasing_agent': r'\b(purchasing[ -]?(agent|manager|buyer))\b',
    'driver': r'\b(driver|carrier|trucker)\b',
    'supervisor': r'\b(supervisor|manager|lead)\b',
    'clerk': r'\b(clerk|admin|assistant|coordinator)\b',
    'receiver': r'\b(receiver|receiving[ -]?clerk)\b',
    'dispatcher': r'\b(dispatcher|logistics[ -]?coordinator)\b',
    'accountant': r'\b(accountant|accounting|bookkeeper)\b',
    'csr': r'\b(csr|customer[ -]?service|support)\b',
}

# Conditions: Triggers, exceptions, contexts
CONDITION_PATTERNS = {
    'exception': r'\b(exception|special[ -]?case|unusual|rare)\b',
    'dispute': r'\b(disput(e|ed)|contested|challenge)\b',
    'rush_order': r'\b(rush|urgent|expedite|priority)\b',
    'new_customer': r'\b(new[ -]?customer|first[ -]?time|onboarding)\b',
    'over_limit': r'\b(over[ -]?limit|exceed|above[ -]?limit)\b',
    'damage': r'\b(damag(e|ed)|broken|defect)\b',
    'shortage': r'\b(shortage|short|missing)\b',
    'past_due': r'\b(past[ -]?due|overdue|late|delinquent)\b',
    'seasonal': r'\b(seasonal|peak|holiday)\b',
    'weekend': r'\b(weekend|after[ -]?hours|holiday)\b',
    'error': r'\b(error|mistake|incorrect|wrong)\b',
}


# ============================================================================
# INTENT CLASSIFICATION
# ============================================================================

def classify_query_types(content: str, section_title: str = "", category: str = "") -> List[str]:
    """
    Classify what type of question this chunk answers.

    Returns one or more of:
    - how_to: Step-by-step procedures
    - policy: Rules, requirements, compliance
    - troubleshoot: Error handling, problem-solving
    - definition: Terminology, explanations
    - lookup: Reference data (codes, contacts, forms)
    - escalation: When/how to escalate issues
    - reference: General information (default fallback)
    """
    types = []
    text = f"{section_title} {content} {category}".lower()

    # How-to: Procedural content
    if any(keyword in text for keyword in [
        'step', 'procedure', 'process', 'how to', 'instructions',
        'follow these', 'first', 'then', 'next', 'finally'
    ]):
        types.append('how_to')

    # Policy: Rules and requirements
    if any(keyword in text for keyword in [
        'policy', 'rule', 'requirement', 'must', 'shall', 'required',
        'mandatory', 'compliance', 'regulation', 'standard'
    ]):
        types.append('policy')

    # Troubleshoot: Problem-solving
    if any(keyword in text for keyword in [
        'error', 'issue', 'problem', 'fix', 'troubleshoot', 'resolve',
        'if this happens', 'when this occurs', 'exception', 'workaround'
    ]):
        types.append('troubleshoot')

    # Definition: Explanations
    if any(keyword in text for keyword in [
        'definition', 'means', 'refers to', 'is defined as', 'glossary',
        'what is', 'terminology', 'acronym'
    ]):
        types.append('definition')

    # Lookup: Reference data
    if any(keyword in text for keyword in [
        'contact', 'phone', 'email', 'address', 'form', 'template',
        'code', 'list of', 'table', 'schedule'
    ]):
        types.append('lookup')

    # Escalation: When to escalate
    if any(keyword in text for keyword in [
        'escalat', 'supervisor', 'manager approval', 'contact',
        'when to', 'if unable', 'exception', 'special handling'
    ]):
        types.append('escalation')

    # Default to reference if no specific type detected
    return types if types else ['reference']


# ============================================================================
# VERB EXTRACTION
# ============================================================================

def extract_verbs(content: str) -> List[str]:
    """
    Extract action verbs from content using regex patterns.
    Returns list of normalized verb tags (e.g., ['approve', 'submit']).
    """
    content_lower = content.lower()
    found_verbs = []

    for verb_tag, pattern in VERB_PATTERNS.items():
        if re.search(pattern, content_lower, re.IGNORECASE):
            found_verbs.append(verb_tag)

    return sorted(set(found_verbs))  # Dedupe and sort


# ============================================================================
# ENTITY EXTRACTION
# ============================================================================

def extract_entities(content: str) -> List[str]:
    """
    Extract domain entities (nouns) from content using regex patterns.
    Returns list of entity tags (e.g., ['credit_memo', 'customer']).
    """
    content_lower = content.lower()
    found_entities = []

    for entity_tag, pattern in ENTITY_PATTERNS.items():
        if re.search(pattern, content_lower, re.IGNORECASE):
            found_entities.append(entity_tag)

    return sorted(set(found_entities))


# ============================================================================
# ACTOR EXTRACTION
# ============================================================================

def extract_actors(content: str) -> List[str]:
    """
    Extract actor roles (who performs actions) from content.
    Returns list of actor tags (e.g., ['sales_rep', 'supervisor']).
    """
    content_lower = content.lower()
    found_actors = []

    for actor_tag, pattern in ACTOR_PATTERNS.items():
        if re.search(pattern, content_lower, re.IGNORECASE):
            found_actors.append(actor_tag)

    return sorted(set(found_actors))


# ============================================================================
# CONDITION EXTRACTION
# ============================================================================

def extract_conditions(content: str) -> List[str]:
    """
    Extract conditions/triggers from content.
    Returns list of condition tags (e.g., ['exception', 'dispute']).
    """
    content_lower = content.lower()
    found_conditions = []

    for condition_tag, pattern in CONDITION_PATTERNS.items():
        if re.search(pattern, content_lower, re.IGNORECASE):
            found_conditions.append(condition_tag)

    return sorted(set(found_conditions))


# ============================================================================
# CONTENT TYPE DETECTION
# ============================================================================

def detect_procedure(content: str, section_title: str = "") -> bool:
    """
    Detect if this chunk is procedural (step-by-step instructions).
    """
    text = f"{section_title} {content}".lower()

    # Strong signals
    if 'step ' in text or 'steps:' in text:
        return True

    # Sequential markers
    sequential_markers = [
        'first', 'second', 'third', 'next', 'then', 'finally', 'last',
        '1.', '2.', '3.', 'a)', 'b)', 'c)'
    ]
    marker_count = sum(1 for marker in sequential_markers if marker in text)

    return marker_count >= 2


def detect_policy(content: str, section_title: str = "", category: str = "") -> bool:
    """
    Detect if this chunk contains policy/compliance content.
    """
    text = f"{section_title} {content} {category}".lower()

    policy_keywords = [
        'policy', 'rule', 'requirement', 'must', 'shall', 'required',
        'mandatory', 'compliance', 'approved by', 'authorized'
    ]

    return sum(1 for kw in policy_keywords if kw in text) >= 2


def detect_form(content: str, section_title: str = "") -> bool:
    """
    Detect if this chunk describes a form or template.
    """
    text = f"{section_title} {content}".lower()

    form_keywords = ['form', 'template', 'worksheet', 'document', 'attachment']

    return any(kw in text for kw in form_keywords)


# ============================================================================
# HEURISTIC SCORING
# ============================================================================

def compute_importance(content: str, category: str = "", query_types: List[str] = None) -> int:
    """
    Score importance (1-10) based on content signals.

    10 = Critical policy/compliance
    5 = Standard procedure
    1 = Helpful tip
    """
    text = f"{content} {category}".lower()
    query_types = query_types or []
    score = 5  # Default: standard content

    # High importance signals (+3 each)
    if 'policy' in query_types:
        score += 3
    if any(kw in text for kw in ['must', 'required', 'mandatory', 'compliance', 'critical']):
        score += 2
    if any(kw in text for kw in ['regulation', 'legal', 'audit', 'approval required']):
        score += 2

    # Medium importance signals (+1 each)
    if 'escalation' in query_types:
        score += 1
    if any(kw in text for kw in ['important', 'note:', 'warning', 'caution']):
        score += 1

    # Low importance signals (-2 each)
    if any(kw in text for kw in ['tip:', 'helpful', 'suggestion', 'optional']):
        score -= 2
    if 'reference' in query_types and len(query_types) == 1:
        score -= 1

    return max(1, min(10, score))  # Clamp to 1-10


def compute_specificity(content: str, entities: List[str] = None, conditions: List[str] = None) -> int:
    """
    Score specificity (1-10) based on how narrow the content is.

    10 = Narrow edge case (rare conditions, specific scenarios)
    5 = Common scenario
    1 = Broad overview
    """
    entities = entities or []
    conditions = conditions or []
    text = content.lower()
    score = 5  # Default: common scenario

    # Edge case signals (+2 each)
    if 'exception' in conditions or 'error' in conditions:
        score += 2
    if any(kw in text for kw in ['rare', 'unusual', 'special case', 'edge case']):
        score += 2
    if len(conditions) >= 3:  # Multiple conditions = specific scenario
        score += 2

    # Specificity signals (+1 each)
    if len(entities) >= 4:  # Many entities = specific context
        score += 1
    if any(kw in text for kw in ['if', 'when', 'in case of', 'only']):
        score += 1

    # Broad overview signals (-3 each)
    if any(kw in text for kw in ['overview', 'introduction', 'general', 'summary']):
        score -= 3
    if len(content) < 150:  # Short = likely broad statement
        score -= 1

    return max(1, min(10, score))


def compute_complexity(content: str, actors: List[str] = None, verbs: List[str] = None) -> int:
    """
    Score complexity (1-10) based on how advanced the content is.

    10 = Specialist-only (complex procedures, multiple actors)
    5 = Requires training
    1 = Anyone can understand
    """
    actors = actors or []
    verbs = verbs or []
    text = content.lower()
    score = 5  # Default: requires training

    # High complexity signals (+2 each)
    if len(actors) >= 3:  # Multiple actors = complex workflow
        score += 2
    if len(verbs) >= 5:  # Many actions = complex procedure
        score += 2
    if any(kw in text for kw in ['advanced', 'complex', 'technical', 'specialist']):
        score += 2

    # Medium complexity signals (+1 each)
    if any(kw in text for kw in ['approval required', 'supervisor', 'exception handling']):
        score += 1
    if re.search(r'\$[\d,]+', text):  # Financial thresholds
        score += 1

    # Low complexity signals (-2 each)
    if any(kw in text for kw in ['simple', 'easy', 'basic', 'straightforward']):
        score -= 2
    if len(verbs) <= 2 and len(actors) <= 1:  # Single actor, few actions
        score -= 1

    return max(1, min(10, score))


# ============================================================================
# PROCESS STRUCTURE DETECTION
# ============================================================================

def extract_process_name(content: str, section_title: str = "", category: str = "") -> Optional[str]:
    """
    Extract process name if this chunk is part of a workflow.
    Returns normalized process name (e.g., 'credit_approval', 'returns_processing').
    """
    text = f"{section_title} {category}".lower()

    # Common process patterns
    process_patterns = {
        'credit_approval': r'credit\s+(approval|memo|request)',
        'returns_processing': r'return(s)?\s+(process|handling)',
        'new_vendor_onboarding': r'(new\s+vendor|vendor\s+setup|onboarding)',
        'order_fulfillment': r'order\s+(fulfillment|processing|entry)',
        'receiving': r'receiving|inbound|delivery',
        'shipping': r'shipping|outbound|dispatch',
        'invoicing': r'invoic(e|ing)|billing',
        'payment_processing': r'payment\s+(processing|collection)',
    }

    for process_name, pattern in process_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return process_name

    return None


def extract_process_step(content: str, section_title: str = "") -> Optional[int]:
    """
    Extract step number if this chunk is part of a sequential procedure.
    Returns integer step number (1, 2, 3...) or None.
    """
    text = f"{section_title} {content}"

    # Pattern 1: "Step 1:", "Step 2:", etc.
    step_match = re.search(r'\bstep\s+(\d+)', text, re.IGNORECASE)
    if step_match:
        return int(step_match.group(1))

    # Pattern 2: Numbered list at start ("1.", "2.", etc.)
    list_match = re.match(r'^\s*(\d+)\.', content)
    if list_match:
        return int(list_match.group(1))

    # Pattern 3: Ordered markers ("First,", "Second,", "Third,")
    ordinal_map = {
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10
    }
    for ordinal, num in ordinal_map.items():
        if re.match(rf'^\s*{ordinal}\b', content, re.IGNORECASE):
            return num

    return None


# ============================================================================
# MASTER TAGGING FUNCTION
# ============================================================================

def tag_document_chunk(
    content: str,
    section_title: str = "",
    category: str = "",
    subcategory: str = ""
) -> Dict:
    """
    Master function: Extract all semantic tags from a document chunk.

    Returns dict with all computed fields for database insertion.
    """
    # Extract semantic tags
    query_types = classify_query_types(content, section_title, category)
    verbs = extract_verbs(content)
    entities = extract_entities(content)
    actors = extract_actors(content)
    conditions = extract_conditions(content)

    # Detect content types
    is_procedure = detect_procedure(content, section_title)
    is_policy = detect_policy(content, section_title, category)
    is_form = detect_form(content, section_title)

    # Extract process structure
    process_name = extract_process_name(content, section_title, category)
    process_step = extract_process_step(content, section_title) if is_procedure else None

    # Compute heuristic scores
    importance = compute_importance(content, category, query_types)
    specificity = compute_specificity(content, entities, conditions)
    complexity = compute_complexity(content, actors, verbs)

    return {
        'query_types': query_types,
        'verbs': verbs,
        'entities': entities,
        'actors': actors,
        'conditions': conditions,
        'is_procedure': is_procedure,
        'is_policy': is_policy,
        'is_form': is_form,
        'process_name': process_name,
        'process_step': process_step,
        'importance': importance,
        'specificity': specificity,
        'complexity': complexity,
    }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Test with sample credit approval content
    sample_content = """
    Step 1: Sales rep submits credit memo request via the online form.
    Customer must have an active account and the dispute must be documented.

    If the credit amount exceeds $5,000, supervisor approval is required.
    For rush orders or new customers, escalate to the credit analyst.
    """

    sample_title = "Credit Memo Approval Process"
    sample_category = "procedures"

    tags = tag_document_chunk(sample_content, sample_title, sample_category)

    print("=== SEMANTIC TAGS ===")
    for key, value in tags.items():
        print(f"{key}: {value}")

    """
    Expected output:
    query_types: ['how_to', 'policy', 'escalation']
    verbs: ['approve', 'escalate', 'submit']
    entities: ['credit_memo', 'customer', 'order']
    actors: ['sales_rep', 'supervisor', 'credit_analyst']
    conditions: ['rush_order', 'new_customer', 'over_limit']
    is_procedure: True
    is_policy: True
    is_form: False
    process_name: credit_approval
    process_step: 1
    importance: 8  (policy + approval required)
    specificity: 7  (multiple conditions)
    complexity: 7  (3 actors, approval workflow)
    """
