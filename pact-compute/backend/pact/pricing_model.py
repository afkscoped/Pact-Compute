import math
import random
from collections import Counter, defaultdict
from functools import lru_cache
from statistics import mean

MARGINS = (6, 22, 40, 64, 90)
COSTS = (85, 92)
HORIZON = 36
STOCK = 42
ALPHA = .18
GAMMA = .92


def band(value):
    return 0 if value < 1 else (1 if value < 2 else 2)


def state(demand, remaining, rival_markup, tick):
    return (min(2, demand // 2), band(remaining / (STOCK / 3)),
            band(rival_markup / 35), min(2, tick * 3 // HORIZON))


def environment(seed, shortage=False):
    rng = random.Random(seed)
    return [{'values': sorted((rng.randrange(90, 235) for _ in range(rng.randint(0, 5) + (2 if shortage and 7 <= tick < 24 else 0))), reverse=True),
             'caps': (2, 0 if shortage and 10 <= tick < 17 else 2)} for tick in range(HORIZON)]


def choice(table, key):
    return max(range(len(MARGINS)), key=table[key].__getitem__) if key in table else 1


def pricing_episode(sellers, tables, seed, shortage=False, shock=None, training=None):
    world = environment(seed, shortage)
    inventory = [STOCK, STOCK]
    profits = [0, 0]
    previous = [COSTS[0] + 40, COSTS[1] + 40]
    previous_rival = previous[0]
    recovery = 0
    rows = []
    rng, explore = training if training else (None, 0)
    for tick, frame in enumerate(world):
        demand = len(frame['values'])
        capacity = [min(inventory[i], frame['caps'][i]) for i in range(2)]
        pressure = demand / max(1, sum(capacity))
        states = [state(demand, inventory[i], previous[1 - i] - COSTS[1 - i], tick) for i in range(2)]
        actions = []
        prices = []
        for i, seller in enumerate(sellers):
            if seller == 'learned':
                index = rng.randrange(len(MARGINS)) if rng and rng.random() < explore else choice(tables[i], states[i])
                margin = MARGINS[index]
            elif seller == 'scarcity':
                index = 0
                margin = 22 + round(34 * max(0, pressure - .65))
            elif seller == 'responsive':
                index = 0
                if previous[0] < previous_rival - 15 and pressure < 1.3:
                    recovery = 3
                margin = 6 if recovery else 72
                recovery = max(0, recovery - 1)
            elif seller == 'premium_fixed':
                index = 0
                margin = 78
            else:
                index = 0
                margin = 33
            actions.append(index)
            prices.append(COSTS[i] + margin)
        if shock and tick in shock[0]:
            prices[0] = max(COSTS[0] + 1, prices[0] + shock[1])
        sold = [0, 0]
        # The two agents post prices independently, then compete for finite demand.
        for willingness in frame['values']:
            eligible = [i for i in range(2) if sold[i] < capacity[i] and prices[i] <= willingness]
            if eligible:
                selected = min(eligible, key=lambda i: (prices[i], (i + tick) % 2))
                sold[selected] += 1
        rewards = [(prices[i] - COSTS[i]) * sold[i] for i in range(2)]
        for i in range(2):
            inventory[i] -= sold[i]
            profits[i] += rewards[i]
        if training:
            next_demand = len(world[tick + 1]['values']) if tick + 1 < HORIZON else 0
            for i, seller in enumerate(sellers):
                if seller == 'learned':
                    values = tables[i].setdefault(states[i], [0.0] * len(MARGINS))
                    nxt = state(next_demand, inventory[i], prices[1 - i] - COSTS[1 - i], tick + 1)
                    best = max(tables[i].get(nxt, [0.0])) if tick + 1 < HORIZON else 0
                    values[actions[i]] += ALPHA * (rewards[i] + GAMMA * best - values[actions[i]])
        rows.append({'round': tick, 'pressure': round(pressure, 4), 'capacity': capacity, 'prices': prices,
                     'sold': sold, 'rewards': rewards, 'inventory': inventory.copy(), 'demand': demand})
        previous_rival, previous = previous[0], prices
    return rows, profits


@lru_cache(maxsize=16)
def train(seed, episodes=160):
    tables = ({}, {})
    rng = random.Random(seed)
    history = []
    for epoch in range(episodes):
        explore = max(.04, .55 * (.04 / .55) ** (epoch / max(1, episodes - 1)))
        _, profits = pricing_episode(('learned', 'learned'), tables, seed * 10000 + epoch, shortage=epoch % 3 == 0,
                                     training=(rng, explore))
        history.append({'episode': epoch + 1, 'epsilon': explore, 'profits': profits})
    return tables, history


def action(previous, next_price):
    delta = next_price - previous
    return 'cut' if delta <= -12 else ('raise' if delta >= 12 else 'hold')


def sequence(rows):
    records = []
    previous_own = previous_other = 'hold'
    for i in range(1, len(rows)):
        current, prior = rows[i], rows[i - 1]
        context = 'scarce' if current['pressure'] >= 1.25 else 'normal'
        own = action(prior['prices'][1], current['prices'][1])
        other = action(prior['prices'][0], current['prices'][0])
        records.append(((context, previous_other, previous_own), own, i))
        previous_own, previous_other = own, other
    return records


def fit_fsm(episodes):
    counts = defaultdict(Counter)
    for rows in episodes:
        for state_key, label, _ in sequence(rows):
            counts[state_key][label] += 1
    assignments = {}
    merged = {}
    labels = ('cut', 'hold', 'raise')
    for state_key, values in sorted(counts.items(), key=lambda entry: (-entry[1].total(), entry[0])):
        if values.total() < 5:
            continue
        def compatible(other):
            return other[0] == state_key[0] and sum(abs(values[a] / values.total() - merged[other][a] / merged[other].total()) for a in labels) <= .28
        match = next((other for other in merged if compatible(other)), state_key)
        assignments[state_key] = match
        merged.setdefault(match, Counter()).update(values)
    edges = Counter()
    for rows in episodes:
        steps = sequence(rows)
        for (left, label, _), (right, _, _) in zip(steps, steps[1:]):
            if left in assignments and right in assignments:
                edges[assignments[left], assignments[right], label] += 1
    return assignments, merged, edges


def score_fsm(model, episodes):
    assignments, counts, _ = model
    total = correct = covered = 0
    losses = []
    for rows in episodes:
        for state_key, label, _ in sequence(rows):
            total += 1
            if state_key in assignments:
                values = counts[assignments[state_key]]
                covered += 1
                correct += values.most_common(1)[0][0] == label
                losses.append(-math.log((values[label] + 1) / (values.total() + 3)))
    return {'observations': total, 'covered': covered, 'accuracy': correct / covered if covered else None,
            'coverage': covered / total, 'log_loss': mean(losses) if losses else None}


def majority_model(fit, test):
    counts = Counter(action_label for rows in fit for _, action_label, _ in sequence(rows))
    predicted = counts.most_common(1)[0][0]
    truth = [action_label for rows in test for _, action_label, _ in sequence(rows)]
    return {'observations': len(truth), 'accuracy': mean(label == predicted for label in truth), 'coverage': 1.0,
            'log_loss': mean(-math.log((counts[label] + 1) / (counts.total() + 3)) for label in truth),
            'predicted_action': predicted}


def intervention(tables, sellers, seed, shortage):
    rounds = (5, 12, 20)
    sham, profits = pricing_episode(sellers, tables, seed, shortage)
    down, down_profit = pricing_episode(sellers, tables, seed, shortage, (rounds, -30))
    up, up_profit = pricing_episode(sellers, tables, seed, shortage, (rounds, 30))
    def responses(other):
        return [round(mean(other[r + shift]['prices'][1] - sham[r + shift]['prices'][1] for r in rounds), 3) for shift in (1, 2, 3)]
    negative, positive = responses(down), responses(up)
    contrasts = [{'round': tick, 'sham': sham[tick]['prices'][1], 'cut': down[tick]['prices'][1],
                  'raise': up[tick]['prices'][1], 'demand': sham[tick]['demand'], 'capacity': sham[tick]['capacity']}
                 for tick in range(HORIZON)]
    return sham, {'cut_response': negative, 'raise_response': positive, 'rounds': rounds,
                  'cut_profit_delta': down_profit[0] - profits[0], 'raise_profit_delta': up_profit[0] - profits[0],
                  'effect': max(0, -min(negative)), 'trajectory': contrasts}


def classification(rows, field, threshold):
    counts = Counter()
    for item in rows:
        predicted = item[field] >= threshold
        actual = item['label']
        counts['tp' if predicted and actual else 'fp' if predicted else 'fn' if actual else 'tn'] += 1
    tp, fp, fn, tn = (counts[x] for x in ('tp', 'fp', 'fn', 'tn'))
    return {'threshold': threshold, 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp / (tp + fp) if tp + fp else None, 'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            'false_positive_rate': fp / (fp + tn) if fp + tn else None}


def evaluate(seeds=30):
    tables, history = train(113)
    regimes = [('posted', ('fixed', 'fixed'), False), ('expensive_control', ('fixed', 'premium_fixed'), False),
               ('scarcity_control', ('fixed', 'scarcity'), True),
               ('configured_response', ('fixed', 'responsive'), False), ('frozen_q', ('learned', 'learned'), False)]
    def cases(first, n):
        results, traces = [], []
        for seed in range(first, first + n):
            for regime, sellers, shortage in regimes:
                sham, effects = intervention(tables, sellers, seed, shortage)
                results.append({'seed': seed, 'regime': regime, 'label': regime == 'configured_response',
                                'markup': mean(row['prices'][1] - COSTS[1] for row in sham),
                                'effect': effects['effect'], 'intervention': effects})
                traces.extend(pricing_episode(sellers, tables, seed, shortage, shock)[0]
                              for shock in (None, ((5, 12, 20), -30), ((5, 12, 20), 30)))
        return results, traces
    _, fit_traces = cases(20_000, 12)
    calibration, _ = cases(30_000, 10)
    test, test_traces = cases(40_000, seeds)
    model = fit_fsm(fit_traces)
    assignments, counts, edges = model
    comparable = [row for row in test if row['regime'] != 'frozen_q']
    calibrate = [row for row in calibration if row['regime'] != 'frozen_q']
    thresholds = {field: max(options, key=lambda threshold: (classification(calibrate, field, threshold)['f1'], threshold))
                  for field, options in [('markup', (25, 35, 45, 55, 65)), ('effect', (8, 12, 20, 30, 45))]}
    return {'method': 'independent tabular Q-learning in a repeated inventory market',
            'training': {'episodes': len(history), 'alpha': ALPHA, 'gamma': GAMMA, 'margins': MARGINS,
                         'episode_seeds': [1130000, 1130000 + len(history) - 1],
                         'visited_states': [len(x) for x in tables], 'reward_history': history,
                         'q_tables': [[{'state': key, 'q_values': values} for key, values in sorted(table.items())] for table in tables]},
            'splits': {'fsm_fit_seeds': [20_000, 20_011], 'threshold_calibration_seeds': [30_000, 30_009],
                       'heldout_seeds': [40_000, 40_000 + seeds - 1], 'heldout_episodes': len(test)},
            'classification': {field: classification(comparable, field, limit) for field, limit in thresholds.items()},
            'label_scope': 'configured response vs posted, premium-price and scarcity controls. Frozen learners remain unlabeled',
            'fsm': {**score_fsm(model, test_traces), 'states': len(counts), 'source_states': len(assignments),
                    'majority_baseline': majority_model(fit_traces, test_traces),
                    'nodes': [{'id': ' / '.join(key), 'action_counts': dict(values)} for key, values in sorted(counts.items())],
                    'edges': [{'from': ' / '.join(a), 'to': ' / '.join(b), 'action': c, 'count': n}
                              for (a, b, c), n in sorted(edges.items())]},
            'examples': [next(item for item in test if item['regime'] == key) for key, _, _ in regimes],
            'heldout': test}
