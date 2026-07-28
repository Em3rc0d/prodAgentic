# PR-MODEL-01G.2 — Certification Gate

- [x] Definir una ruta explícita que garantice el intento de Google fallback (corregido en `test_model_router.py`).
- [x] Eliminar la doble fuente de verdad del bypass n8n (corregido en `router.py` usando `self.policy`).
- [x] Corregir los dos tests frontend con selectores (`e.g. Kafka, Spring Boot...`) y eventos reales (`stage.attempt_started`, `stage.failed`).
- [x] Verificar estado, attempt invalidado y controles rehabilitados (corregido en `page.test.tsx`).
- [x] Añadir script `"test": "jest --runInBand"` en `frontend/package.json`.
- [x] Reescribir `task.md` y `walkthrough.md` con datos reales.
- [ ] Crear Draft PR (siguiente paso en GH CLI).
- [ ] Añadir CI (crear `.github/workflows/ci.yml`).
