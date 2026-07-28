import os
import re

f = 'tests/test_model_router.py'
c = open(f, encoding='utf-8').read()
ctx_str = '        ctx = GenerationContext(run_id="run-1", topic="", style="", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)\n        '
c = re.sub(r'events = \[evt async for evt in router.*\.stream_generation\(ModelExecutionRequest\(context=ctx', lambda m: ctx_str + m.group(0), c)
c = "from core.context import GenerationContext, LanguageCode\n" + c
open(f, 'w', encoding='utf-8').write(c)
