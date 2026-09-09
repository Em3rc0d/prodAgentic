# S5 Implementation Inventory

This inventory fixes the intended S5 source boundary before candidate certification.

```text
.github/workflows/s5-cert.yml
backend/application/rendering/
backend/domain/rendering/
backend/infrastructure/assets/
backend/infrastructure/rendering/
backend/infrastructure/mongo/rendering.py
backend/routes/rendering.py
backend/scripts/s5_generate_goldens.py
backend/tests/test_s5_api_surface.py
backend/tests/test_s5_rendering.py
backend/tests/test_mk1_s5_mongo.py
backend/tests/test_s5_retryable_recovery.py
backend/db/mongo.py
backend/main.py
docker-compose.yml
renderer/
frontend/lib/rendering.ts
frontend/app/review/[revisionId]/
frontend/e2e/s5-review-preview.spec.ts
mk1/build/slices/S5/
mk1/test/evidence/S5/
```

Files outside this boundary require explicit review before the candidate can be frozen. S5 does not authorize modifications to the certified S4 domain/application implementation.
