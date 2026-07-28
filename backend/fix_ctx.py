import os

f = 'tests/test_model_router.py'
c = open(f, encoding='utf-8').read()

imports = 'from core.context import GenerationContext, LanguageCode\nctx = GenerationContext(run_id="run-1", topic="", style="", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)\n'

if 'ctx = GenerationContext' not in c:
    c = c.replace('from core.context import GenerationContext, LanguageCode', imports)
    if 'from core.context import GenerationContext, LanguageCode' not in c:
        c = imports + c

open(f, 'w', encoding='utf-8').write(c)
