# PR-MODEL-01G.3 — Executable Certification

- [x] Abrir el provider breaker de n8n tras agotar fallos de transporte, preservando presupuesto para el fallback.
- [x] Garantizar presupuesto para Google fallback actualizando la política productiva a `max_total_attempts = 5`.
- [x] Reescribir los tests usando errores `retryable=True` simulando los fallos reales de n8n y Google, y demostrando que el fallback se ejecuta exitosamente.
- [x] Cambiar `"lint": "next lint"` por `"lint": "eslint"` en `frontend/package.json`.
- [x] Añadir guard 503 para endpoints (`/api/ideas` y `/api/pipeline/stream`) cuando no exista provider viable mediante FastAPI `Depends`.
- [x] Probar rechazo de chunks tardíos después de `stage.failed` en el frontend.
- [x] Actualizar documentación.
- [ ] Crear Draft PR y esperar CI verde.
