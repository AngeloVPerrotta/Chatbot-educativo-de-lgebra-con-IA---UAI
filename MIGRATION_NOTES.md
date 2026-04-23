# Migración a Groq (Llama 3.3 70B)

**Fecha:** 2026-04-22
**Razón:** Usar API gratuita con 14,400 requests/día

**Cambios:**
- Provider: Anthropic Claude → Groq Llama 3.3 70B
- Modelo: claude-sonnet-4-6 → llama-3.3-70b-versatile
- Límite diario: ~2,500 requests (con $5) → 14,400 requests gratis

**Configuración:**
- API Key: GROQ_API_KEY en .env
- Modelo: llama-3.3-70b-versatile (más potente y rápido)
- Mantiene toda la lógica pedagógica de AlgorIA
