# Q-VISUAL-01 — Visual quality and advanced formats

**State:** PARKED (non-blocking for static V1)

## Question

Which layout families/render strategies create consistently signature, high-quality outputs across Profiles, and when should GIF/short-video enter scope?

## Inputs

- static golden renders from S5;
- human visual rejection reasons;
- renderer latency/resource metrics;
- format performance observations only as secondary evidence.

## Method

Benchmark composition families on hierarchy, readability, brand distinctiveness, repeat-pattern rate, render stability and accessibility.

## Current architecture answer

Single image, carousel and infographic are sufficient V1. ChromiumRenderer + VisualSpec is the stable base.

## Promotion

New layout family may update DesignProfile/VisualSpec-compatible policy. Motion requiring new semantics must use VisualSpec V2/ADR rather than hidden fields.
