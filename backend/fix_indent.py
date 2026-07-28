import re

f = 'tests/test_model_router.py'
c = open(f, encoding='utf-8').read()

# Remove existing ctx
c = re.sub(r'^[ \t]*ctx = GenerationContext.*?$', '', c, flags=re.MULTILINE)

ctx_str = 'ctx = GenerationContext(run_id="run-1", topic="", style="", requested_source_language=LanguageCode.AUTO, detected_source_language=LanguageCode.EN, source_detection_confidence=0.0, requested_target_language=LanguageCode.EN, resolved_target_language=LanguageCode.EN, image_prompt_language=LanguageCode.EN)\n'

def replacer(m):
    indent = m.group(1)
    return indent + ctx_str + indent + 'events = [evt async for evt in router' + m.group(0).split('router', 1)[1]

c = re.sub(r'([ \t]*)events = \[evt async for evt in router.*?\.stream_generation\(ModelExecutionRequest\(context=ctx', replacer, c)
open(f, 'w', encoding='utf-8').write(c)
