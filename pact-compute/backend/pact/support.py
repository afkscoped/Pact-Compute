"""Deterministic support diagnosis: map a job's recorded events to one situation, the evidence event that proves it
and the next actions the viewer's role may take.

Rules read only structured event fields (kind, seq, status, boolean flags). Free text recorded by runners or users is never
copied into a diagnosis, so it cannot steer the answer. When no recorded event proves a situation the answer says so
instead of guessing."""

VERSION = 'support-rules-1'

ACTIONS = {
    'wait': ('Wait for the next update', ('consumer', 'producer', 'operator', 'admin', 'reviewer', 'submitter')),
    'no_action': ('No action is needed', ('consumer', 'producer', 'operator', 'admin', 'reviewer', 'submitter')),
    'new_quote': ('Request a new quote', ('consumer', 'admin', 'submitter')),
    'revise_agreement': ('Review or revise the agreement', ('consumer', 'admin', 'reviewer', 'submitter', 'operator')),
    'resubmit': ('Resubmit with a later deadline or a larger window', ('consumer', 'admin', 'operator', 'submitter')),
    'view_receipt': ('Open the usage receipt and compare it with the accepted maximum', ('consumer', 'producer', 'operator', 'admin', 'submitter')),
    'reconcile': ('Reconcile only after confirming the original process stopped', ('operator', 'admin')),
    'check_grid_signal': ('Check forecast freshness and the missing-signal policy', ('operator', 'admin', 'producer')),
    'ask_operator': ('Ask an operator to review the evidence', ('consumer', 'producer', 'submitter', 'reviewer')),
    'inspect_failure': ('Inspect the failed attempt before resubmitting', ('consumer', 'producer', 'operator', 'admin', 'submitter')),
}

# situation: (title, ordered action ids, uncertainty note)
SITUATIONS = {
    'admission_rejected': ('The request was rejected at admission', ['revise_agreement', 'resubmit'],
                           'The rejection lists the failing requirement. No capacity was reserved.'),
    'quote_invalid': ('The quote was expired or invalid when accepted', ['new_quote'],
                      'A quote is only valid until its expiry time.'),
    'quote_terms_changed': ('The accepted terms differ from the quote', ['new_quote', 'ask_operator'],
                            'Compare the changed terms before confirming again.'),
    'dispatch_grid_unknown': ('Dispatch was refused because the grid signal was missing', ['check_grid_signal', 'revise_agreement'],
                              'The agreement requires an emissions estimate that could not be computed.'),
    'dispatch_carbon_limit': ('Dispatch was refused because the emissions estimate exceeded the cap', ['revise_agreement', 'resubmit'],
                              'The cap in the pinned agreement was not met at dispatch time.'),
    'dispatch_deferral_expired': ('Dispatch was refused because the allowed deferral elapsed', ['resubmit', 'revise_agreement'],
                                  'The job waited longer than the agreement permits.'),
    'dispatch_recheck_failed': ('Dispatch was refused when the constraints were rechecked', ['revise_agreement', 'resubmit'],
                                'Constraints are checked again at the moment of dispatch.'),
    'reservation_expired': ('The reservation expired before dispatch', ['resubmit'],
                            'The job deadline elapsed before a runner claimed it.'),
    'cancelled_before_start': ('The job was cancelled before it started', ['no_action'],
                               'The reserved capacity was released.'),
    'cancel_pending': ('A cancellation was requested and the runner has not confirmed a stop', ['wait'],
                       'Executed usage is accounted after the runner reports.'),
    'cancelled_running': ('The job was cancelled while running', ['view_receipt'],
                          'Usage up to the stop is accounted.'),
    'execution_uncertain': ('The runner stopped reporting and the job is on hold', ['wait', 'reconcile'],
                            'The original process may still be running. Capacity stays held until it is confirmed stopped.'),
    'reconciled': ('An operator confirmed the original process stopped', ['inspect_failure'],
                   'The reconciled attempt produced no billable output.'),
    'job_overran': ('The job exceeded its time allowance', ['resubmit', 'view_receipt'],
                    'Only an authorized extension can raise the allowance. It cannot be extended after the fact.'),
    'job_failed': ('The attempt failed', ['inspect_failure', 'resubmit'],
                   'The failure message comes from the runner and is untrusted.'),
    'charge_review': ('Review the charge against the accepted maximum', ['view_receipt', 'ask_operator'],
                      'Settlement adjustments are decided by an operator and are not automatic.'),
    'charge_exceeded': ('The recorded charge is outside the accepted maximum', ['view_receipt', 'ask_operator'],
                        'The protocol monitor flags a charge above the authorized envelope.'),
    'in_progress': ('The job is progressing normally', ['wait'], 'No fault is recorded.'),
    'completed': ('The job completed', ['view_receipt', 'no_action'], 'No fault is recorded.'),
    'insufficient_evidence': ('No recorded event proves what happened', ['ask_operator'],
                              'This platform did not record an event for that situation. No evidence is cited.'),
}

CHARGE_WORDS = ('charge', 'bill', 'invoice', 'receipt', 'refund', 'dispute', 'overcharged')


def find(events, kind, last=False, **match):
    rows = [e for e in events if e['kind'] == kind and all(e.get('details', {}).get(k) == v for k, v in match.items())]
    return (rows[-1] if last else rows[0]) if rows else None


def pick(events, question):
    """Return (situation, evidence event) from structured events only."""
    kinds = {e['kind'] for e in events}
    if not events:
        return 'insufficient_evidence', None
    for event in events:
        if event['kind'] == 'MarketQuoteAccepted' and event.get('details', {}).get('quote_id'):
            quote = find(events, 'QuoteIssued')
            if quote:
                q, d = quote['details'], event['details']
                if d.get('quote_id') != q.get('quote_id') or event['at'] >= q.get('expires_at', -1):
                    return 'quote_invalid', event
                if any(d.get(key) != q.get(key) for key in ('policy_id', 'rate_cents', 'offer_version')):
                    return 'quote_terms_changed', event
    if 'AdmissionRejected' in kinds:
        return 'admission_rejected', find(events, 'AdmissionRejected')
    if 'DispatchRecheckFailed' in kinds:
        event = find(events, 'DispatchRecheckFailed')
        d = event['details']
        if d.get('carbon_unknown'):
            return 'dispatch_grid_unknown', event
        if d.get('carbon_rejected'):
            return 'dispatch_carbon_limit', event
        if d.get('deferral_expired'):
            return 'dispatch_deferral_expired', event
        return 'dispatch_recheck_failed', event
    if 'ReservationExpired' in kinds:
        return 'reservation_expired', find(events, 'ReservationExpired')
    if 'ReservationCancelled' in kinds:
        return 'cancelled_before_start', find(events, 'ReservationCancelled')
    finished = find(events, 'JobFinished', last=True)
    if 'ExecutionReconciled' in kinds:
        return 'reconciled', find(events, 'ExecutionReconciled')
    if finished:
        status = finished['details'].get('status')
        charged, accepted = finished['details'].get('charged_cents'), find(events, 'MarketQuoteAccepted')
        if accepted and charged is not None and not 0 <= charged <= accepted['details'].get('envelope_cents', -1):
            return 'charge_exceeded', finished
        if status == 'cancelled':
            return 'cancelled_running', finished
        if status == 'expired':
            return 'job_overran', finished
        if status == 'failed':
            return 'job_failed', finished
        if any(word in question.lower() for word in CHARGE_WORDS):
            return 'charge_review', finished
        return 'completed', finished
    if 'ExecutionUncertain' in kinds:
        return 'execution_uncertain', find(events, 'ExecutionUncertain', last=True)
    if 'CancellationRequested' in kinds:
        return 'cancel_pending', find(events, 'CancellationRequested')
    if kinds & {'JobDispatched', 'JobStarted', 'CapacityReserved', 'ShadowRecommendation', 'JobSubmitted'}:
        return 'in_progress', events[-1]
    return 'insufficient_evidence', None


def diagnose(events, role, question=''):
    situation, evidence = pick(events, question or '')
    title, action_ids, uncertainty = SITUATIONS[situation]
    allowed = [a for a in action_ids if role in ACTIONS[a][1]]
    withheld = [a for a in action_ids if a not in allowed]
    if not allowed:  # never leave the viewer without a permissible next step
        allowed = ['ask_operator'] if role in ACTIONS['ask_operator'][1] else ['wait']
    return {'version': VERSION, 'situation': situation, 'title': title, 'uncertainty': uncertainty,
            'evidence': {'seq': evidence['seq'], 'kind': evidence['kind']} if evidence else None,
            'actions': [{'id': a, 'label': ACTIONS[a][0]} for a in allowed], 'withheld': withheld}
