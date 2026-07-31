import pytest
from agents.orchestrator import extract_research_claims, validate_and_strip_claims

def test_extract_research_claims():
    research = """
    Here is the research output.
    ## Claims & Evidence
    - [Claim: C1] 85% of people like dark mode.
    - [Claim: C2] 12 million users were recorded.
    """
    claims = extract_research_claims(research)
    assert set(claims) == {"C1", "C2"}

def test_extract_research_claims_no_claims():
    research = "No claims here."
    assert extract_research_claims(research) == []

def test_validate_and_strip_claims_valid():
    final_text = "It is widely known that 85% of people like dark mode [Claim: C1]."
    valid_claims = ["C1", "C2"]
    
    clean_text, has_violation = validate_and_strip_claims(final_text, valid_claims)
    
    assert has_violation is False
    assert clean_text == "It is widely known that 85% of people like dark mode."

def test_validate_and_strip_claims_invalid_claim():
    final_text = "It is widely known that 85% of people like dark mode [Claim: X99]."
    valid_claims = ["C1", "C2"]
    
    clean_text, has_violation = validate_and_strip_claims(final_text, valid_claims)
    
    assert has_violation is True
    assert clean_text == "It is widely known that 85% of people like dark mode."

def test_validate_and_strip_claims_heuristic_violation():
    final_text = "It is widely known that 85% of people like dark mode."
    valid_claims = ["C1", "C2"]
    
    clean_text, has_violation = validate_and_strip_claims(final_text, valid_claims)
    
    assert has_violation is True  # 85% is present, but no claims used!
    assert clean_text == final_text

def test_validate_and_strip_claims_no_numbers_no_claims():
    final_text = "This is just a general statement about dark mode."
    valid_claims = ["C1", "C2"]
    
    clean_text, has_violation = validate_and_strip_claims(final_text, valid_claims)
    
    assert has_violation is False
    assert clean_text == final_text
