from agents.adapters.google_adapter import GoogleDirectAdapter


class _ProviderErrorDetail:
    message = "Request contains an invalid argument."

    def __init__(self, details):
        self.details = details


def test_invalid_request_diagnostic_classifies_schema_cardinality_without_raw_body():
    exc = _ProviderErrorDetail({
        "error": {
            "status": "INVALID_ARGUMENT",
            "details": [{"detail": "generationConfig.responseJsonSchema.properties.ideas.maxItems"}],
        }
    })

    assert GoogleDirectAdapter._safe_invalid_request_reason(exc) == "SCHEMA_CARDINALITY"


def test_invalid_request_diagnostic_classifies_response_schema():
    exc = _ProviderErrorDetail({
        "error": {
            "status": "INVALID_ARGUMENT",
            "details": [{"field": "response_json_schema"}],
        }
    })

    assert GoogleDirectAdapter._safe_invalid_request_reason(exc) == "RESPONSE_SCHEMA"


def test_invalid_request_diagnostic_fails_closed_to_unknown():
    exc = _ProviderErrorDetail({
        "error": {
            "status": "INVALID_ARGUMENT",
            "details": [{"detail": "opaque provider detail"}],
        }
    })

    assert GoogleDirectAdapter._safe_invalid_request_reason(exc) == "UNKNOWN"
