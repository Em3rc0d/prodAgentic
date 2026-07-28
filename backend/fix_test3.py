import re

f = 'tests/test_model_router.py'
c = open(f, encoding='utf-8').read()

c = c.replace('REGISTRY', '')

# Replace old args with ModelExecutionRequest
c = c.replace('ModelProfile.QUALITY_TEXT, "sys", "prompt", "run-1"',
              'ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN)')

# Replace the generation context creation
c = c.replace('source_language=LanguageCode.AUTO, target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN',
              'requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN')

# Add imports
c = c.replace('from core.model_registry import ModelProfile',
              'from core.model_registry import ModelProfile\nfrom core.validator import ArtifactType\nfrom agents.router import ModelExecutionRequest')

open(f, 'w', encoding='utf-8').write(c)
