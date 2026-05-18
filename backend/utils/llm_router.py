import os
import logging

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'groq')

# Contadores en memoria para observabilidad
_stats = {'groq_calls': 0, 'anthropic_fallback_calls': 0, 'errors': 0}

# Status codes de Groq que justifican fallback (no 400 = bug en el prompt)
_FALLBACK_STATUS_CODES = {429, 500, 502, 503}


def get_llm_stats() -> dict:
    return dict(_stats)


def call_llm(messages: list, system: str) -> str:
    if LLM_PROVIDER == 'groq':
        return _call_groq_with_fallback(messages, system)
    return _call_anthropic(messages, system)


def _call_groq(messages: list, system: str) -> str:
    from groq import Groq
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{"role": "system", "content": system}] + messages,
        max_tokens=700,
        temperature=0.7,
    )
    return response.choices[0].message.content


def _call_anthropic(messages: list, system: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=700,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def _is_fallback_error(exc: Exception) -> bool:
    try:
        from groq import RateLimitError, APIConnectionError, APIStatusError
        if isinstance(exc, (RateLimitError, APIConnectionError)):
            return True
        if isinstance(exc, APIStatusError) and exc.status_code in _FALLBACK_STATUS_CODES:
            return True
    except ImportError:
        pass

    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return True
    except ImportError:
        pass

    return False


def _call_groq_with_fallback(messages: list, system: str) -> str:
    try:
        result = _call_groq(messages, system)
        _stats['groq_calls'] += 1
        return result
    except Exception as e:
        if not _is_fallback_error(e):
            _stats['errors'] += 1
            raise

        logger.warning(f'FALLBACK: Groq falló con {type(e).__name__}: {e}, usando Anthropic como fallback')
        try:
            result = _call_anthropic(messages, system)
            _stats['anthropic_fallback_calls'] += 1
            return result
        except Exception as e2:
            _stats['errors'] += 1
            raise RuntimeError(f'Groq y Anthropic fallaron. Groq: {e} | Anthropic: {e2}') from e2
