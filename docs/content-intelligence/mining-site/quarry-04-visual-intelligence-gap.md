# Quarry 04 — Visual Intelligence Gap

## Question

Why can current prodAgentic create attractive but semantically weak visuals for technical content?

## OBSERVED

1. Current `VisualAgent` system prompt describes itself as an expert art director / Midjourney prompt engineer.

2. Current rules explicitly optimize for:
   - highly descriptive prompts,
   - lighting/camera/artistic style,
   - striking visual metaphor,
   - cinematic/surreal/highly stylized digital art,
   - avoiding generic stock-photo concepts.

3. Current visual prompt input is essentially the final LinkedIn post + requested image prompt language.

4. There is no explicit visual-intent classifier/model in the current tree.

5. Current `VisualRenderService` already provides substantial production safety:
   - kill switch,
   - circuit breaker,
   - concurrency limit,
   - timeout/retries,
   - image signature checks,
   - size guard,
   - local asset ownership,
   - SHA-256 digest,
   - idempotency binding by render intent.

6. Visual generation failure is non-terminal to text content in the orchestrator.

## INFERRED

The primary visual weakness is not rendering reliability.

It is upstream semantic direction.

The current prompt strongly biases the model toward cinematic metaphor even when the communication job is explanatory, architectural, data-oriented or mechanical.

Therefore replacing the renderer would attack the wrong layer.

## PROPOSED

Add `VisualIntentService` before `VisualAgent`.

The intent layer decides:

- what the image is supposed to communicate,
- which visual class is appropriate,
- required elements,
- elements to avoid,
- preferred aspect/style.

Then `VisualAgent` converts post + intent into a rendering prompt.

Initial classes:

- `TECHNICAL_DIAGRAM`
- `TECHNICAL_ILLUSTRATION`
- `DATA_VISUALIZATION`
- `BEFORE_AFTER`
- `PRODUCT_HERO`
- `EDITORIAL`
- `CINEMATIC_METAPHOR`
- `NO_VISUAL`

## Example motivating case

For a corrosion-under-insulation post, a cinematic industrial tower may look premium but communicate the mechanism poorly.

Expected intent:

```text
TECHNICAL_ILLUSTRATION
- pipe cutaway
- external cladding
- wet insulation
- corroded steel surface
- sensor position / hotspot
- avoid generic refinery skyline and unrelated machinery
```

## REJECTED

- Replacing existing render/storage/digest pipeline.
- Always forcing technical diagrams.
- Making visual failure terminal to text generation.
- Adding a Canva-like editor during this phase.

## UNKNOWN

- Intent classification reliability must be evaluated on the Golden Dataset.
- Some posts legitimately benefit from metaphor; the goal is correct selection, not elimination of cinematic visuals.

## Pre-build verdict

GAP CONFIRMED — rendering boundary is strong; semantic visual-direction layer is missing.