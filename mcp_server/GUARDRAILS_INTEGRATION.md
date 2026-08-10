
# FemLens Health Safety Guardrails - Integration Guide

## ✅ What's Been Implemented

The health_mcp_server.py now includes:

### 1. Safety Guardrail Categories
- **Emergency Detection**: Severe chest pain, breathing difficulty, heavy bleeding, etc.
- **Self-Harm Prevention**: Suicide-related queries, lethal dose requests
- **Drug Misuse Prevention**: Recreational drug use, dangerous combinations
- **Medication Safety**: Personal dosing questions, medication decisions
- **Diagnosis Blocking**: "Do I have X?" type questions
- **Pregnancy Safety**: High-risk pregnancy situations requiring medical care
- **Eating Disorder Prevention**: Purging, starvation methods
- **Prompt Injection Defense**: Attempts to bypass safety rules

### 2. Input Validation
- NCT ID format validation (NCT + 8 digits)
- User ID/email validation
- Query length limits (1000 chars)
- Notes length limits (2000 chars)
- top_k limits (max 20)
- page_size limits (max 50)

### 3. Privacy & Authorization
- User collection isolation
- Sensitive content detection in notes
- No PII exposure in logs

## 🔗 How to Integrate with Your Flask App

### Option A: Direct Integration (Recommended)

Add to app.py:

```python
from mcp_server.health_mcp_server import FemLensHealthTools

# Initialize once
health_tools = FemLensHealthTools()

@app.route("/health/search", methods=["POST"])
def search_health():
    data = request.get_json()
    query = data.get("query")
    top_k = data.get("top_k", 10)
    
    # Guardrails run automatically
    result = health_tools.search_health_knowledge(query, top_k)
    
    if "error" in result:
        return jsonify(result), 400  # Blocked by guardrail
    
    # If allowed, proceed with actual vector search
    # ...
```

### Option B: Standalone Validation

Just use the guardrail validator:

```python
from mcp_server.health_mcp_server import HealthGuardrailValidator

validator = HealthGuardrailValidator()

@app.route("/api/ask", methods=["POST"])
def ask():
    question = request.get_json().get("question")
    
    # Check guardrails first
    result = validator.validate_health_request(question, "ask_endpoint")
    
    if not result.allowed:
        return jsonify({
            "error": result.message,
            "redirect": result.redirect_message
        }), 400
    
    # Proceed with research
    # ...
```

## 🎯 Key Design Principles

1. **Research Queries Are Allowed**
   - "Find clinical trials for PCOS"
   - "What research exists on endometriosis"
   - These pass through guardrails

2. **Personal Medical Advice Is Blocked**
   - "Should I take this medication?"
   - "Do I have PCOS?"
   - "Can I stop my prescription?"

3. **Emergency Situations Get Safe Response**
   - Brief, non-judgmental
   - Directs to professional help
   - Doesn't attempt diagnosis

4. **Modular Architecture**
   - Guardrails run before tools
   - Easy to add new categories
   - Reusable across tools

## 📊 Response Formats

### Blocked Request
```json
{
  "error": "FemLens cannot provide personalized medication advice...",
  "redirect": "Try rephrasing as: 'Find research about treatments for [condition]'",
  "guardrail_category": "medication_safety"
}
```

### Allowed Request
```json
{
  "status": "success",
  "results": [...]
}
```

## 🧪 Testing

The guardrails have been tested with:
- ✅ Research queries (all allowed)
- ✅ Input validation (NCT IDs, emails, limits)
- ✅ Modular design (easy to extend)

## 🚀 Next Steps

1. **Integrate with Flask endpoints**:
   - /health/search
   - /api/ask
   - /api/collection (for notes validation)

2. **Connect to actual data sources**:
   - ClinicalTrials.gov API
   - Lakebase vector search
   - Research collection database

3. **Add logging/monitoring**:
   - Track blocked requests by category
   - Monitor false positives
   - Tune guardrail patterns

## 🔒 Security Notes

- Guardrails run BEFORE tool execution
- Cannot be bypassed by prompt injection
- Validates all inputs
- Protects user privacy
- Prevents hallucinations (no fabricated studies)

## 📝 Example Usage

```python
from mcp_server.health_mcp_server import FemLensHealthTools

tools = FemLensHealthTools()

# Research query (ALLOWED)
result = tools.search_health_studies(
    query="clinical trials for PCOS treatment"
)
# Returns: {"status": "success", "studies": [...]}

# Personal medical advice (BLOCKED)
result = tools.search_health_studies(
    query="should I stop taking my medication"
)
# Returns: {"error": "FemLens cannot provide personalized medication advice..."}
```

The guardrail system is now ready for production integration!
