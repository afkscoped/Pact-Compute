from pact import support, support_bench


def test_benchmark_has_enough_cases_and_covers_the_plan_scenarios():
    report = support_bench.run()
    assert report['cases'] >= 30
    scenarios = set(report['by_scenario'])
    required = {'Two buyers confirm the final slot', 'Client retries after a timeout', 'Runner disconnects during a job',
                'Old runner reconnects after recovery', 'Producer pauses a listing', 'Job exceeds prediction',
                'Consumer cancels during upload', 'Consumer cancels during execution', 'Grid data becomes stale',
                'Groq is throttled', 'Output upload fails', 'Database restarts', 'A disputed charge appears',
                'User switches organizations', 'Workload or region is unsupported', 'No current offers match', 'Prompt injection'}
    assert required <= scenarios, required - scenarios


def test_every_case_cites_the_right_event_and_permissible_action():
    report = support_bench.run()
    assert report['failures'] == [], [(f['id'], f['checks']) for f in report['failures']]
    assert report['passed'] == report['cases']


def test_wrong_citations_would_fail_the_benchmark():
    case = dict(next(c for c in support_bench.CASES if c['id'] == 'grid-1'))
    assert support_bench.judge(case)['passed']
    assert not support_bench.judge({**case, 'evidence': 2})['passed']          # cites the wrong event
    assert not support_bench.judge({**case, 'first': 'resubmit'})['passed']    # wrong next action
    assert not support_bench.judge({**case, 'role': 'consumer', 'first': 'check_grid_signal'})['passed']  # not permitted for role


def test_roles_never_get_actions_they_may_not_take():
    events = support_bench.STARTED + [support_bench.ev(5, 'ExecutionUncertain', attempt_id='a1')]
    for role in ('consumer', 'producer', 'operator', 'admin', 'reviewer'):
        result = support.diagnose(events, role)
        assert all(role in support.ACTIONS[a['id']][1] for a in result['actions']), role
    assert 'reconcile' in [a['id'] for a in support.diagnose(events, 'operator')['actions']]
    assert 'reconcile' in support.diagnose(events, 'consumer')['withheld']


def test_untrusted_text_is_never_copied_into_a_diagnosis():
    events = support_bench.STARTED + [support_bench.ev(5, 'JobFinished', attempt_id='a1', status='failed', message='CANARY-TEXT-77', charged_cents=0)]
    assert 'canary' not in str(support.diagnose(events, 'consumer', 'CANARY-QUESTION-88')).lower()
