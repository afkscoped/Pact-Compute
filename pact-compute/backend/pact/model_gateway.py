import hashlib
import json
import threading
import time
from collections import OrderedDict

import httpx

from . import ratelimit
from .config import LLM_KEY, LLM_MODEL, LLM_PROVIDER, LLM_URL

_lock = threading.Lock()
_cache = OrderedDict()
MAX_PER_MINUTE = 4
CACHE_SECONDS = 900


def available():
    return bool(LLM_KEY and LLM_MODEL)


def ask_json(purpose, instruction, text, validate):
    """Return a validated draft or an explicit local fallback reason."""
    if not available():
        return None, 'provider_disabled'
    key = hashlib.sha256(json.dumps([purpose, LLM_MODEL, instruction, text], ensure_ascii=False).encode()).hexdigest()
    now = time.monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and now < cached[0]:
            _cache.move_to_end(key)
            return cached[1], 'cached_' + LLM_PROVIDER
    # Budget, single-flight and cooldown live in the database so every replica shares them.
    if ratelimit.blocked('llm:cooldown'):
        return None, 'provider_budget'
    flight = ratelimit.hit('llm:flight', 1, 20)
    if flight is None:
        return None, 'provider_budget'
    if ratelimit.hit('llm:minute', MAX_PER_MINUTE, 60) is None:
        ratelimit.release(flight)
        return None, 'provider_budget'
    try:
        response = httpx.post(f'{LLM_URL}/chat/completions', headers={'Authorization': 'Bearer ' + LLM_KEY},
                              json={'model': LLM_MODEL, 'response_format': {'type': 'json_object'},
                                    'max_completion_tokens': 1600,
                                    'messages': [{'role': 'system', 'content': instruction + ' Return JSON.'},
                                                 {'role': 'user', 'content': text}]},
                              timeout=httpx.Timeout(10, connect=4))
        if response.status_code == 429:
            try:
                wait = max(5.0, min(600.0, float(response.headers.get('Retry-After', '60'))))
            except ValueError:
                wait = 60
            ratelimit.mark('llm:cooldown', wait)
            return None, 'provider_rate_limited'
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        result = validate(json.loads(content))
        with _lock:
            _cache[key] = (time.monotonic() + CACHE_SECONDS, result)
            _cache.move_to_end(key)
            while len(_cache) > 64:
                _cache.popitem(last=False)
        return result, LLM_PROVIDER
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None, 'provider_unavailable'
    finally:
        ratelimit.release(flight)
