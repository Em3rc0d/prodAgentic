import os

f = 'tests/test_model_router.py'
content = open(f, encoding='utf-8').read()

old = 'ModelProfile.QUALITY_TEXT, "sys", "prompt", "run-1"'
new = 'ModelExecutionRequest(context=ctx, model_profile=ModelProfile.QUALITY_TEXT, artifact_type=ArtifactType.FINAL, system_instruction="sys", user_prompt="prompt", expected_output_language=LanguageCode.EN)'
content = content.replace(old, new)

content = content.replace('from core.model_registry import ModelProfile', 
'''from core.model_registry import ModelProfile
from core.validator import ArtifactType
from agents.router import ModelExecutionRequest''')

open(f, 'w', encoding='utf-8').write(content)
