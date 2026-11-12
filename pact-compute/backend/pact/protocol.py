"""Executable booking protocol and independent event-trace checker."""

TRANSITIONS = {
    'initial': {'QuoteIssued': 'quoted', 'JobSubmitted': 'submitted'},
    'quoted': {'JobSubmitted': 'submitted'},
    'submitted': {'MarketQuoteAccepted': 'committed', 'CapacityReserved': 'reserved',
                  'AdmissionRejected': 'closed', 'ShadowRecommendation': 'closed'},
    'committed': {'CapacityReserved': 'reserved'},
    'reserved': {'JobDispatched': 'dispatched', 'ReservationExpired': 'terminal', 'DispatchRecheckFailed': 'terminal',
                 'ReservationCancelled': 'terminal'},
    'dispatched': {'JobStarted': 'running', 'ExecutionUncertain': 'uncertain', 'JobFinished': 'terminal'},
    'running': {'JobFinished': 'terminal', 'ExecutionUncertain': 'uncertain'},
    'uncertain': {'JobFinished': 'terminal', 'ExecutionReconciled': 'terminal'},
    'terminal': {'CapacityReleased': 'closed'},
    'closed': {},
}
OBSERVATIONS = {'CancellationRequested', 'FindingReviewed'}
LABELS = {'initial': 'Initial', 'quoted': 'Quote issued', 'submitted': 'Job submitted', 'committed': 'Quote accepted',
          'reserved': 'Capacity reserved', 'dispatched': 'Lease issued', 'running': 'Execution started',
          'uncertain': 'Execution uncertain', 'terminal': 'Terminal outcome', 'closed': 'Capacity released or closed'}


def observe(events, *, market=False):
    """Check ordering, unique execution, pinned terms, and settlement envelope."""
    state = 'initial'
    quote = None
    accepted = None
    dispatch = None
    started = False
    last_time = None
    steps = []
    failures = []
    for item in events:
        kind, at, details = item['kind'], item['at'], item.get('details', {})
        old = state
        errors = []
        if last_time is not None and at < last_time:
            errors.append('event_time_reversed')
        last_time = at
        if kind in OBSERVATIONS:
            allowed = old not in ('initial', 'quoted')
            destination = old if allowed else None
        else:
            destination = TRANSITIONS[old].get(kind)
        if destination is None:
            errors.append('unexpected_transition')
        else:
            state = destination
        if kind == 'QuoteIssued':
            quote = details
        elif kind == 'MarketQuoteAccepted':
            accepted = details
            if not quote or details.get('quote_id') != quote.get('quote_id') or at >= quote.get('expires_at', -1):
                errors.append('quote_invalid_or_expired')
            elif any(details.get(key) != quote.get(key) for key in ('policy_id', 'rate_cents', 'offer_version')):
                errors.append('quote_terms_changed')
            elif details.get('envelope_cents', -1) < 0 or details['envelope_cents'] > quote.get('envelope_cents', -1):
                errors.append('authorization_exceeded')
        elif kind == 'CapacityReserved' and market and not accepted:
            errors.append('quote_required')
        elif kind == 'JobDispatched':
            dispatch = details
            if accepted and details.get('policy_id') != accepted.get('policy_id'):
                errors.append('policy_version_changed')
        elif kind in {'JobStarted', 'JobFinished', 'ExecutionReconciled', 'ExecutionUncertain'}:
            if not dispatch or details.get('attempt_id') != dispatch.get('attempt_id'):
                errors.append('attempt_mismatch')
            if kind == 'JobStarted':
                started = True
            if kind == 'JobFinished':
                if details.get('status') == 'succeeded' and not started:
                    errors.append('missing_execution_start')
                billed = details.get('charged_cents')
                if accepted and billed is not None and not 0 <= billed <= accepted['envelope_cents']:
                    errors.append('charge_exceeded')
        for error in errors:
            failures.append({'code': error, 'event': kind, 'evidence': item.get('seq')})
        steps.append({'event': kind, 'from': old, 'to': state, 'at': at,
                      'status': 'fail' if errors else 'pass', 'errors': errors, 'evidence': item.get('seq')})
    verdict = 'fail' if failures else ('pass' if state == 'closed' else 'incomplete')
    return {'version': 'booking-protocol-1', 'verdict': verdict, 'state': state, 'steps': steps,
            'violations': failures, 'labels': LABELS}
