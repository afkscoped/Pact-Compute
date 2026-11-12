import hashlib
import json
import threading
import time
from collections import OrderedDict, deque

import httpx

from .config import LLM_KEY, LLM_MODEL, LLM_PROVIDER, LLM_URL

_lock = threading.Lock()
_requests = deque()
_cache = OrderedDict()
_in_flight = False
_retry_at = 0.0
MAX_PER_MINUTE = 4
CACHE_SECONDS = 900


def available():
    return bool(LLM_KEY and LLM_MODEL)


def ask_json(purpose, instruction, text, validate):
    """Return a validated draft or an explicit local fallback reason."""
    global _in_flight, _retry_at
    if not available():
        return None, 'provider_disabled'
    key = hashlib.sha256(json.dumps([purpose, LLM_MODEL, instruction, text], ensure_ascii=False).encode()).hexdigest()
    now = time.monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and now < cached[0]:
            _cache.move_to_end(key)
            return cached[1], 'cached_' + LLM_PROVIDER
        while _requests and now - _requests[0] >= 60:
            _requests.popleft()
        if now < _retry_at or _in_flight or len(_requests) >= MAX_PER_MINUTE:
            return None, 'provider_budget'
        _in_flight = True
        _requests.append(now)
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
            with _lock:
                _retry_at = time.monotonic() + wait
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
        with _lock:
            _in_flight = False
