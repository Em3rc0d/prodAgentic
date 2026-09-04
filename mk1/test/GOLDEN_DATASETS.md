# MK1 Golden Datasets

Status: **FROZEN DATASET DESIGN; fixtures populated during slices**

Golden datasets are regression assets representing different editorial demands. They include positive and negative/adversarial cases.

# GD-01 — Content Seller

Purpose:

- relatable/educational/personal/community role balance;
- strong hooks without repetitive templates;
- short social-friendly visual copy;
- avoid repeating recent concepts/creative mechanics.

Fixture categories:

```text
recent published memory
scheduled future memory
allowed fresh candidates
same-topic/same-angle collisions
same-hook-pattern collisions
off-brand corporate copy
excellent concise visual concepts
poor generic template visuals
```

# GD-02 — Logan / automotive

Purpose:

- maintenance/symptom/safety/mechanical explainer diversity;
- aggressive recent-topic cooldown;
- careful safety language;
- high-quality photo/diagram/carousel direction.

Adversarial pairs include paraphrases that change wording but not the diagnosis/angle.

Claim fixtures include:

- safe general maintenance statement;
- statement requiring qualification;
- unsupported mechanical certainty that must be removed/researched.

# GD-03 — Tech

Purpose:

- technical education, humor, system design and trade-off diversity;
- architecture/diagram VisualSpecs;
- precise claims and terminology;
- avoid superficial “X vs Y” repetition.

Fixtures include:

- supported technical claim with evidence;
- fashionable but unsupported statistic;
- diagram requiring exact labels;
- system-design post that should use a flow visual rather than decorative AI art.

# Output labels

Every Profile dataset stores examples/rubrics for:

```text
GOOD
EXCELLENT
BAD
UNSAFE_OR_UNSUPPORTED
REPETITIVE
OFF_BRAND
POOR_VISUAL
```

# Novelty benchmark pairs

Each dataset contains candidate-memory pairs labeled:

```text
BLOCK
REWRITE_ANGLE
WARNING
PASS
```

Threshold calibration quarry uses these labels. Architecture does not encode one embedding threshold as truth.

# Visual goldens

For each first-class format/Profile combination, store approved reference outputs or structural snapshots:

```text
single image
carousel
infographic/diagram where relevant
```

References include semantic layout expectations, not only pixel snapshots, so legitimate typography/render upgrades can be reviewed intentionally.

# Dataset governance

- fixture provenance recorded;
- no secrets/private tokens;
- user-provided examples retained only according to product/data policy;
- changes to expected labels receive review because they can mask regressions;
- generative evaluation uses frozen inputs and model/config metadata.
