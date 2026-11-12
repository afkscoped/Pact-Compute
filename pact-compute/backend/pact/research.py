import hashlib
import itertools
import math
import random
from collections import Counter, defaultdict
from statistics import mean, median
from typing import Literal

from ortools.sat.python import cp_model
from pydantic import BaseModel, Field

from .audit import analyze_offers
from .datasets import read_snapshot
from .policy import exceeds, values
from . import pricing_model, runtime_model


ENGINE_VERSION = 'pact-replay-2'
SLOT_SECONDS = 1800
ARMS = ('fcfs', 'edf', 'policy_only', 'carbon_aware', 'unconstrained')
STRATEGY = Literal['cost_plus', 'scarcity', 'scripted_response', 'q_learning']


class Scenario(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    dataset_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    policy_id: str | None = Field(default=None, max_length=32)
    jobs: int = Field(default=150, ge=30, le=1200)
    seeds: int = Field(default=3, ge=1, le=30)
    seed: int = Field(default=2026, ge=0, le=2**31 - 31)
    strategies: list[STRATEGY] = Field(default_factory=lambda: ['cost_plus', 'scarcity', 'scripted_response'], min_length=2, max_length=4)
    carbon_weight: int = Field(default=4, ge=0, le=25)
    scarcity: int = Field(default=1, ge=0, le=2)
    respect_gpu_models: bool = False
    controlled_undercut: bool = True
    carbon_mode: Literal['lagged', 'oracle'] = 'lagged'
    cohort: Literal['modeled', 'successful_proxy'] = 'modeled'
    runtime_model: Literal['median', 'calibrated'] = 'median'


GPU_TYPES = [
    ('T4', 16384, 115, 87),
    ('V100M32', 32768, 240, 124),
    ('A10', 24576, 150, 99),
    ('V100M16', 16384, 210, 105),
]


def sub_rng(seed, purpose):
    tag = f'{seed}/{purpose}'.encode()
    return random.Random(int.from_bytes(hashlib.sha256(tag).digest()[:8], 'big'))


def build_jobs(pods, config, seed):
    source = sorted((row for row in pods if row['gpu_count'] > 0), key=lambda row: (row['arrival_relative_s'], row['source_id']))
    boundary = int(len(source) * .60)
    train = source[:boundary]
    heldout = source[boundary:]
    successful = [row for row in heldout if row['runtime_proxy_s']]
    cohort = successful if config.cohort == 'successful_proxy' else heldout
    size = min(config.jobs, len(cohort))
    if not size:
        raise ValueError('This snapshot has no GPU jobs in the selected test cohort.')
    rng = sub_rng(seed, 'arrivals')
    start = rng.randrange(len(cohort) - size + 1)
    chosen = cohort[start:start + size]
    first = chosen[0]['arrival_relative_s']
    span = max(1, chosen[-1]['arrival_relative_s'] - first)
    # Rescale gaps into a documented bounded stress episode while retaining the trace's order.
    arrivals_slots = max(36, min(112, size // 5))
    outcome_cutoff = heldout[0]['arrival_relative_s']
    observed_train = runtime_model.observed_before(runtime_model.successful(train), outcome_cutoff)
    proxy = [min(10800, max(15, row['runtime_proxy_s'])) for row in observed_train]
    if not proxy:
        raise ValueError('No runtime calibration rows precede the test window.')
    runtime_rng = sub_rng(seed, 'runtimes')
    values_rng = sub_rng(seed, 'economics')
    typical = math.ceil(median(proxy) / SLOT_SECONDS)
    fit_end = max(1, round(len(observed_train) * .75))
    model = None
    if config.runtime_model == 'calibrated':
        if fit_end >= len(observed_train):
            raise ValueError('No observed runtime calibration outcomes precede the test window.')
        eligible = runtime_model.observed_before(observed_train[:fit_end], observed_train[fit_end]['arrival_relative_s'])
        model = runtime_model.fit(eligible, observed_train[fit_end:])
    normalized = []
    for row in chosen:
        actual = row['runtime_proxy_s'] if config.cohort == 'successful_proxy' else runtime_rng.choice(proxy)
        realized = max(1, min(8, math.ceil(actual / SLOT_SECONDS)))
        arrival = (row['arrival_relative_s'] - first) * arrivals_slots // (span + 1)
        urgent = row['qos'] == 'LS' or values_rng.random() < .19
        want = row['gpu_count']
        units = (max(1, row['gpu_milli']) if want == 1 else 1000)
        normalized.append({'id': row['source_id'], 'arrival': arrival, 'priority': 'urgent' if urgent else 'flexible',
                           'count': want, 'units': units, 'models': row['gpu_models'] if config.respect_gpu_models else [],
                           'realized': realized, 'prediction': max(1, min(8, math.ceil(runtime_model.predict(model, row) / SLOT_SECONDS))) if model else max(1, min(6, typical)),
                           'due': arrival + (6 if urgent else 12),
                           'flex': 0 if urgent else 7,
                           'budget': round((500 if urgent else 410) * want * (units / 1000) + values_rng.randrange(50, 130)),
                           'value': round((900 if urgent else 720) * want * (units / 1000) + values_rng.randrange(80, 300))})
    return normalized, {'selected': len(chosen), 'test_window': [first, chosen[-1]['arrival_relative_s']],
                        'cohort': config.cohort, 'training_proxies': len(proxy), 'runtime_predictor': config.runtime_model,
                        'runtime_outcomes_observed_before': outcome_cutoff,
                        'runtime_calibration_rows': model['calibration_rows'] if model else 0,
                        'arrival_mapping': f'relative arrival gaps scaled to {arrivals_slots} half-hour rounds',
                        'runtime_origin': 'held-out successful lifecycle proxy' if config.cohort == 'successful_proxy' else
                        'sampled from earlier successful lifecycle proxies, rounded to half-hour slots'}


def offer_tape(jobs, config, seed, ticks):
    providers = []
    for i, strategy in enumerate(config.strategies):
        model, vram, watts, cost = GPU_TYPES[i]
        capacity = (10, 8, 6)[config.scarcity]
        providers.append({'id': f'pool-{i + 1}', 'strategy': strategy, 'cost': cost,
                          'devices': capacity, 'model': model, 'vram_mib': vram, 'watts': watts})
    learned_tables = pricing_model.train(113)[0] if 'q_learning' in config.strategies else None
    arrivals = Counter()
    for job in jobs:
        arrivals[job['arrival']] += job['count'] * job['units'] / 1000
    history = []
    punish = defaultdict(int)
    for tick in range(ticks):
        offers = []
        online = [p for i, p in enumerate(providers) if not (config.scarcity == 2 and i == 0 and 20 <= tick < 29)]
        total_capacity = sum(p['devices'] for p in online)
        demand = sum(arrivals[t] for t in range(max(0, tick - 3), tick + 1))
        pressure = min(3.0, demand / max(1, total_capacity))
        for p in online:
            prior_rivals = [min((o['price'] for o in f['offers'] if o['provider'] != p['id']), default=9999) for f in history[-2:]]
            deviation = len(prior_rivals) == 2 and prior_rivals[1] < prior_rivals[0] - 15 and prior_rivals[0] < 9999
            cost = p['cost']
            if p['strategy'] == 'scripted_response':
                if deviation and pressure < .9:
                    punish[p['id']] = 2
                margin = 9 if punish[p['id']] else 74
                punish[p['id']] = max(0, punish[p['id']] - 1)
            elif p['strategy'] == 'scarcity':
                margin = 27 + round(50 * max(0, pressure - .45))
            elif p['strategy'] == 'q_learning':
                # Transfer the frozen training policy to normalized replay market observations.
                rival_markup = max(0, prior_rivals[-1] - cost) if prior_rivals else 40
                key = pricing_model.state(round(min(5, pressure * 2.5)), pricing_model.STOCK,
                                          rival_markup, tick * pricing_model.HORIZON // ticks)
                margin = pricing_model.MARGINS[pricing_model.choice(learned_tables[providers.index(p) % 2], key)]
            else:
                margin = 35
            if config.controlled_undercut and p == online[0] and p['strategy'] != 'scripted_response' and tick in (8, 15, 33, 49, 65, 81, 97):
                margin = 5
            offers.append({'provider': p['id'], 'price': cost + margin, 'cost': cost,
                           'devices': p['devices'], 'gpu_model': p['model']})
        history.append({'round': tick, 'pressure': round(pressure, 3), 'demand': round(demand, 3),
                        'capacity': total_capacity, 'offers': offers})
    return providers, history


def limit_policy(job, rules):
    limits = values(rules)
    return min(job['due'], job['arrival'] + math.floor(limits['deadline_seconds'] / SLOT_SECONDS)) if 'deadline_seconds' in limits else job['due']


def predicted_signal(carbon, anchor, tick, future, mode):
    if mode == 'oracle':
        return carbon[anchor + future]['actual_g_per_kwh']
    lag = anchor + tick - 2
    same_hour = anchor + future - 48
    if same_hour <= lag:
        return carbon[same_hour]['actual_g_per_kwh']
    return carbon[lag]['actual_g_per_kwh']


def candidate_slots(job, tick, horizon, occupancy, provider_map, frame, carbon, anchor, config, rules):
    limits = values(rules)
    options = []
    for offer in frame['offers']:
        p = provider_map[offer['provider']]
        if job['count'] > p['devices'] or (job['models'] and p['model'] not in job['models']):
            continue
        if p['vram_mib'] < limits.get('min_vram_mib', 0) or limits.get('gpu_count', job['count']) != job['count']:
            continue
        if limits.get('gpu_model', '').lower() not in p['model'].lower() or limits.get('grid_zone', 'GB') != 'GB':
            continue
        if exceeds(rules, 'max_rate_cents', offer['price']):
            continue
        if 'deadline_utc' in limits:
            absolute_due = (limits['deadline_utc'] - carbon[anchor]['start']) // SLOT_SECONDS
        else:
            absolute_due = horizon + tick + job['due']
        due = min(limit_policy(job, rules), absolute_due)
        if job['priority'] == 'flexible':
            flex = min(job['flex'], limits.get('max_deferral_seconds', job['flex'] * SLOT_SECONDS) // SLOT_SECONDS)
            max_start = min(tick + horizon, job['arrival'] + flex)
        else:
            max_start = tick
        stop = min(max_start, due - job['prediction'])
        for start in range(tick, stop + 1):
            periods = range(start, start + job['prediction'])
            units = job['units']
            available = [n for n in range(p['devices']) if all(occupancy[p['id'], n, t] + units <= 1000 for t in periods)]
            if len(available) < job['count']:
                continue
            energy = p['watts'] * job['count'] * units / 1000 / 1000 * SLOT_SECONDS / 3600
            carbon_g = sum(energy * predicted_signal(carbon, anchor, tick, t, config.carbon_mode) for t in periods)
            charge = math.ceil(offer['price'] * job['prediction'] * .5 * job['count'] * units / 1000)
            if charge > job['budget'] or exceeds(rules, 'max_charge_cents', charge) or exceeds(rules, 'carbon_limit_g', math.ceil(carbon_g)):
                continue
            groups = [tuple(available)] if len(available) == job['count'] else itertools.islice(itertools.combinations(available, job['count']), 8)
            for group in groups:
                options.append({'job': job, 'provider': p, 'start': start, 'slots': list(periods), 'devices': group,
                                'energy_slot': energy, 'quote': charge, 'price': offer['price'], 'forecast_g': carbon_g})
    return options


def greedy(options, tick, sort_mode):
    by_job = defaultdict(list)
    for opt in options:
        if opt['start'] == tick:
            by_job[opt['job']['id']].append(opt)
    if sort_mode == 'fcfs':
        rank = lambda row: (row['arrival'], row['id'])
    else:
        rank = lambda row: (row['due'], row['priority'] != 'urgent', row['arrival'], row['id'])
    used = Counter()
    selected = []
    for items in sorted(by_job.values(), key=lambda variants: rank(variants[0]['job'])):
        for option in sorted(items, key=lambda opt: (opt['quote'], opt['provider']['id'], opt['devices'])):
            pairs = [(option['provider']['id'], n, t) for n in option['devices'] for t in option['slots']]
            if all(used[key] + option['job']['units'] <= 1000 - option['occupied'][key] for key in pairs):
                selected.append(option)
                for key in pairs:
                    used[key] += option['job']['units']
                break
    return selected


def solve(options, tick, carbon_weight, seed):
    if not options:
        return [], 'empty'
    model = cp_model.CpModel()
    variables = [model.new_bool_var(f'x{i}') for i in range(len(options))]
    groups = defaultdict(list)
    intervals = defaultdict(list)
    service = []
    tradeoff = []
    for var, option in zip(variables, options, strict=True):
        job = option['job']
        groups[job['id']].append(var)
        service.append(var * (4 if job['priority'] == 'urgent' else 2))
        penalty = option['quote'] * 3 + round(carbon_weight * option['forecast_g']) + 18 * (option['start'] - job['arrival'])
        tradeoff.append(var * penalty)
        for device in option['devices']:
            for t in option['slots']:
                intervals[option['provider']['id'], device, t].append(var * job['units'])
    for group in groups.values():
        model.add_at_most_one(group)
    occupied = options[0]['occupied']
    for key, intervals_at_slot in intervals.items():
        model.add(sum(intervals_at_slot) <= 1000 - occupied[key])
    primary = sum(service)
    model.maximize(primary)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_deterministic_time = .035
    solver.parameters.random_seed = seed % (2**31 - 1)
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return greedy(options, tick, 'edf'), 'heuristic_fallback'
    fallback = [opt for var, opt in zip(variables, options, strict=True) if solver.value(var) and opt['start'] == tick]
    floor = solver.value(primary)
    model.add(primary >= floor)
    model.minimize(sum(tradeoff))
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return fallback, 'first_pass'
    return [opt for var, opt in zip(variables, options, strict=True) if solver.value(var) and opt['start'] == tick], solver.status_name(status).lower()


def run_arm(jobs, providers, tape, carbon, anchor, config, approved, arm, seed):
    provider_map = {p['id']: p for p in providers}
    arrivals = defaultdict(list)
    for job in jobs:
        arrivals[job['arrival']].append(job)
    pending = []
    occupancy = Counter()
    decisions = []
    timeline = []
    outcomes = Counter()
    hard_rules = approved if arm in {'policy_only', 'carbon_aware'} else []
    for tick, frame in enumerate(tape):
        pending.extend(arrivals[tick])
        retained = []
        for job in pending:
            if tick + job['prediction'] <= job['due']:
                retained.append(job)
            else:
                outcomes['unallocated'] += 1
        pending = retained
        # Keep the solver's candidate space bounded. Queue age and deadline order select the batch.
        rank = (lambda job: (job['arrival'], job['id'])) if arm == 'fcfs' else (lambda job: (job['due'], job['arrival'], job['id']))
        batch = sorted(pending, key=rank)[:40]
        horizon = 0 if arm in ('fcfs', 'edf') else 4
        options = []
        for job in batch:
            for option in candidate_slots(job, tick, horizon, occupancy, provider_map, frame, carbon, anchor, config, hard_rules):
                options.append({**option, 'occupied': occupancy})
        if arm in ('fcfs', 'edf'):
            selected, status = greedy(options, tick, arm), arm
        else:
            selected, status = solve(options, tick, config.carbon_weight if arm == 'carbon_aware' else 0, seed)
        assigned = set()
        for option in selected:
            job, p = option['job'], option['provider']
            if job['id'] in assigned or any(occupancy[p['id'], n, t] + job['units'] > 1000 for n in option['devices'] for t in option['slots']):
                continue
            # Forecast runtime governs admission. A replay overrun is explicitly stopped at the reservation boundary.
            worked = min(job['prediction'], job['realized'])
            finish = tick + worked
            succeeded = job['realized'] <= job['prediction']
            for t in range(tick, finish):
                for device in option['devices']:
                    occupancy[p['id'], device, t] += job['units']
            charge = math.ceil(option['price'] * worked * .5 * job['count'] * job['units'] / 1000)
            real_cost = math.ceil(p['cost'] * worked * .5 * job['count'] * job['units'] / 1000)
            co2 = sum(option['energy_slot'] * carbon[anchor + t]['actual_g_per_kwh'] for t in range(tick, finish))
            observed = {'charge': charge, 'carbon_g': round(co2, 4), 'finish': finish}
            policy = values(approved)
            checks = {
                'deadline_seconds': finish <= limit_policy(job, approved) and succeeded,
                'deadline_utc': carbon[anchor]['start'] + finish * SLOT_SECONDS <= policy.get('deadline_utc', float('inf')) and succeeded,
                'max_charge_cents': not exceeds(approved, 'max_charge_cents', charge),
                'max_rate_cents': not exceeds(approved, 'max_rate_cents', option['price']),
                'min_vram_mib': p['vram_mib'] >= policy.get('min_vram_mib', 0),
                'gpu_count': job['count'] == policy.get('gpu_count', job['count']),
                'gpu_model': policy.get('gpu_model', '').lower() in p['model'].lower(),
                'grid_zone': policy.get('grid_zone', 'GB') == 'GB',
                'max_deferral_seconds': job['priority'] == 'urgent' or (tick - job['arrival']) * SLOT_SECONDS <= policy.get('max_deferral_seconds', 7 * SLOT_SECONDS),
                'carbon_limit_g': not exceeds(approved, 'carbon_limit_g', math.ceil(option['forecast_g'])),
                'report_required': True,
            }
            violations = [rule['kind'] for rule in approved if rule['kind'] in checks and not checks[rule['kind']]]
            decisions.append({'job': job['id'], 'provider': p['id'], 'start': tick, 'due': job['due'],
                              'arrival': job['arrival'], 'finish': finish, 'status': 'succeeded' if succeeded else 'overrun',
                              'priority': job['priority'], 'forecast_g': round(option['forecast_g'], 4), **observed,
                              'energy_kwh': round(worked * option['energy_slot'], 6), 'violations': violations,
                              'profit': charge - real_cost, 'buyer_surplus': (job['value'] if succeeded else 0) - charge - 8 * (tick - job['arrival']),
                              'gpu_slot_units': worked * job['units'] * job['count']})
            assigned.add(job['id'])
        pending = [job for job in pending if job['id'] not in assigned]
        timeline.append({'round': tick, 'queued': len(pending), 'started': len(assigned), 'solver': status,
                         'forecast': predicted_signal(carbon, anchor, tick, tick, config.carbon_mode),
                         'actual': carbon[anchor + tick]['actual_g_per_kwh']})
    completed = [d for d in decisions if d['status'] == 'succeeded']
    waits = sorted((d['start'] - d['arrival']) * 30 for d in decisions)
    service = {}
    for group in ('urgent', 'flexible'):
        n = sum(job['priority'] == group for job in jobs)
        if n:
            service[group] = sum(d['priority'] == group for d in completed) / n
    emissions = sum(d['carbon_g'] for d in decisions)
    profit = sum(d['profit'] for d in decisions)
    buyer = sum(d['buyer_surplus'] for d in decisions)
    gross_slots = sum(frame['capacity'] for frame in tape) * 1000
    metrics = {'submitted': len(jobs), 'admitted': len(decisions), 'completed': len(completed),
               'on_time_rate': sum(d['finish'] <= d['due'] for d in completed) / len(jobs),
               'wait_p95_min': waits[math.ceil(.95 * len(waits)) - 1] if waits else None,
               'gpu_utilization': sum(d['gpu_slot_units'] for d in decisions) / gross_slots,
               'policy_violations': sum(len(d['violations']) for d in decisions),
               'energy_kwh': sum(d['energy_kwh'] for d in decisions), 'carbon_g': emissions,
               'carbon_g_per_completed': emissions / len(completed) if completed else None,
               'profit_credits': profit / 100, 'buyer_surplus_credits': buyer / 100, 'welfare_credits': (profit + buyer) / 100,
               'fairness': sum(service.values()) ** 2 / (len(service) * sum(x*x for x in service.values())) if any(service.values()) else None,
               'service_by_priority': service, 'overruns': len(decisions) - len(completed)}
    return {'metrics': metrics, 'placements': decisions, 'timeline': timeline}


def experiment(config: Scenario, approved, progress):
    card, pods, _nodes, carbon = read_snapshot(config.dataset_id)
    evidence = []
    metrics = defaultdict(list)
    first = None
    for index in range(config.seeds):
        seed = config.seed + index
        jobs, mapping = build_jobs(pods, config, seed)
        ticks = max(job['due'] for job in jobs) + 8
        anchor = sub_rng(seed, 'grid-window').randrange(50, len(carbon) - ticks - 16)
        providers, tape = offer_tape(jobs, config, seed, ticks)
        audits = analyze_offers(tape)
        gold = {p['id']: p['strategy'] == 'scripted_response' and config.controlled_undercut for p in providers}
        arms = {}
        for number, arm in enumerate(ARMS, 1):
            result = run_arm(jobs, providers, tape, carbon, anchor, config, approved, arm, seed)
            metrics[arm].append(result['metrics'])
            arms[arm] = result
            progress(round(100 * (index + number / len(ARMS)) / config.seeds))
        evidence.append({'seed': seed, 'mapping': mapping, 'carbon_anchor': carbon[anchor]['start'],
                         'providers': providers, 'offers': tape, 'audits': audits, 'strategy_labels': gold, 'arms': arms})
        if first is None:
            first = {'seed': seed, 'mapping': mapping, 'carbon_anchor': carbon[anchor]['start'],
                     'offers': tape, 'audits': audits,
                     'timeline': arms['carbon_aware']['timeline'], 'placements': arms['carbon_aware']['placements']}
    numeric = [key for key, value in metrics[ARMS[0]][0].items() if isinstance(value, (int, float)) or value is None]
    summary = {arm: {key: mean(vals) if (vals := [item[key] for item in metrics[arm] if item[key] is not None]) else None
                     for key in numeric} for arm in ARMS}
    paired = {}
    for key in ('completed', 'on_time_rate', 'carbon_g', 'wait_p95_min'):
        samples = [a[key] - b[key] for a, b in zip(metrics['carbon_aware'], metrics['policy_only'], strict=True)
                   if a[key] is not None and b[key] is not None]
        if samples:
            rng = sub_rng(config.seed, key)
            draws = sorted(mean(rng.choices(samples, k=len(samples))) for _ in range(1000)) if len(samples) >= 3 else []
            paired[key] = {'delta': mean(samples), 'interval95': [draws[24], draws[974]] if draws else None,
                           'pairs': len(samples)}
    counts = Counter()
    for episode in evidence:
        for audit in episode['audits']:
            gold = episode['strategy_labels'][audit['provider']]
            if audit['status'] == 'insufficient_evidence':
                counts['abstentions'] += 1
            predicted = audit['status'] == 'review'
            counts[('t' if gold == predicted else 'f') + ('p' if predicted else 'n')] += 1
    tp, fp, fn, tn = (counts[x] for x in ('tp', 'fp', 'fn', 'tn'))
    audit_metrics = {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'abstentions': counts['abstentions'],
                     'precision': tp / (tp + fp) if tp + fp else None, 'recall': tp / (tp + fn) if tp + fn else None,
                     'false_positive_rate': fp / (fp + tn) if fp + tn else None}
    result = {'engine': ENGINE_VERSION, 'dataset': card['id'], 'cohort': config.cohort, 'runtime_model': config.runtime_model, 'summary': summary,
              'paired': paired, 'audit_metrics': audit_metrics, 'first_episode': first,
              'assumptions': ['Arrivals are drawn from a held-out Alibaba pod cohort and time-scaled.',
                              'Provider prices, costs, capacity and scenario behavior are configured.',
                              'NESO actual values score outcomes. The oracle can also use them for planning.',
                              'Energy is estimated with a GPU-only device power model.',
                              'Provider offers are shared across paired scheduler arms.',
                              'Q-learning offers use a frozen policy transferred from independent inventory-market episodes.']}
    return result, {'config': config.model_dump(), 'policy_rules': approved, 'source_card': card,
                    'summary': result, 'episodes': evidence}
