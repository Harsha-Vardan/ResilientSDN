"""ResilientDecision (Algorithm 1) driven without Ryu."""
import random
from collections import namedtuple

import networkx as nx

from controller.decision import Env, ResilientDecision, move_load
from controller.path_engine import path_links
from tests.conftest import CAPACITY, make_link_stats

Flow = namedtuple('Flow', 'id src dst')


def diamond():
    """s1 -> s4 via s2 (short) or s3 (alternative)."""
    g = nx.Graph()
    for a, b in [('s1', 's2'), ('s2', 's4'), ('s1', 's3'), ('s3', 's4')]:
        g.add_edge(a, b, latency=1.0, bw=100)
    return g


class FakeNet:
    """Minimal host environment: flows with fixed rates on explicit paths."""

    def __init__(self, g, flows):
        self.g, self.paths, self.rates, self.moves = g, {}, {}, []
        self.flows = {}
        for fid, path, rate in flows:
            self.flows[fid] = Flow(fid, path[0], path[-1])
            self.paths[fid], self.rates[fid] = list(path), rate

    def stats(self):
        loads = {}
        for fid, p in self.paths.items():
            for l in path_links(p):
                loads[l] = loads.get(l, 0.0) + self.rates[fid]
        return make_link_stats(self.g, loads)

    def env(self):
        def flows_on(link):
            on = [self.flows[f] for f, p in self.paths.items() if link in path_links(p)]
            return sorted(on, key=lambda f: -self.rates[f.id])

        def set_path(flow, path, why):
            self.moves.append((flow.id, list(path), why))
            self.paths[flow.id] = list(path)
            return True
        return Env(flows_on=flows_on, flow_rate=self.rates.get,
                   switch_path=lambda f: self.paths[f], set_path=set_path,
                   latency=lambda: {})


def run(core, net, polls):
    for _ in range(polls):
        core.on_interval(net.stats(), net.env())


def test_moves_largest_flow_after_n_polls(config, clock):
    g = diamond()
    net = FakeNet(g, [('a', ['s1', 's2', 's4'], 500.0), ('b', ['s1', 's2', 's4'], 400.0)])
    core = ResilientDecision(g, config, rng=random.Random(0), clock=clock)
    run(core, net, config.N_intervals - 1)
    assert net.moves == []                       # trend trigger: not yet
    run(core, net, 1)
    assert net.moves == [('a', ['s1', 's3', 's4'], 'congestion on s1-s2')]
    assert net.paths['b'] == ['s1', 's2', 's4']  # 400/1000 is under the threshold: stop shedding


def test_capacity_filter_blocks_a_full_detour(config, clock):
    g = diamond()
    net = FakeNet(g, [('a', ['s1', 's2', 's4'], 900.0), ('x', ['s1', 's3', 's4'], 500.0)])
    core = ResilientDecision(g, config, rng=random.Random(0), clock=clock)
    run(core, net, config.N_intervals)
    assert net.moves == []                       # 500 + 900 > 0.8 * 1000 on the detour


def _presaturated():
    # target s1-s2 at 1.0; detour already at 0.2. Moving 'a' (0.7) gives 0.9: fails the 0.8 filter.
    return [('a', ['s1', 's2', 's4'], 700.0), ('b', ['s1', 's2', 's4'], 300.0),
            ('x', ['s1', 's3', 's4'], 200.0)]


def test_without_fallback_only_the_flow_that_fits_moves(config, clock):
    g = diamond()
    net = FakeNet(g, _presaturated())
    run(ResilientDecision(g, config, rng=random.Random(0), clock=clock), net, config.N_intervals)
    assert [m[0] for m in net.moves] == ['b']


def test_fallback_moves_the_largest_flow_when_it_still_helps(config, clock):
    config.fallback_least_loaded = True
    g = diamond()
    net = FakeNet(g, _presaturated())
    run(ResilientDecision(g, config, rng=random.Random(0), clock=clock), net, config.N_intervals)
    assert [m[0] for m in net.moves] == ['a'] and net.moves[0][2].endswith('(fallback)')


def test_fallback_never_moves_onto_a_worse_path(config, clock):
    config.fallback_least_loaded = True
    g = diamond()
    net = FakeNet(g, [('a', ['s1', 's2', 's4'], 900.0), ('x', ['s1', 's3', 's4'], 500.0)])
    run(ResilientDecision(g, config, rng=random.Random(0), clock=clock), net, config.N_intervals)
    assert net.moves == []                       # 1.4 on the detour > 0.9 on the target


def two_diamonds():
    g = diamond()
    for a, b in [('s5', 's6'), ('s6', 's8'), ('s5', 's7'), ('s7', 's8')]:
        g.add_edge(a, b, latency=1.0, bw=100)
    return g


TWO_ATTACKS = [('lo1', ['s1', 's2', 's4'], 450.0), ('lo2', ['s1', 's2', 's4'], 400.0),
               ('hi1', ['s5', 's6', 's8'], 500.0), ('hi2', ['s5', 's6', 's8'], 450.0)]


def test_two_attacked_links_are_both_relieved_in_detection_order(config, clock):
    g = two_diamonds()
    net = FakeNet(g, TWO_ATTACKS)
    run(ResilientDecision(g, config, rng=random.Random(0), clock=clock), net, config.N_intervals)
    assert [m[0] for m in net.moves] == ['lo1', 'hi1']


def test_severity_order_handles_worst_link_first(config, clock):
    config.order_by_severity = True
    g = two_diamonds()
    net = FakeNet(g, TWO_ATTACKS)
    run(ResilientDecision(g, config, rng=random.Random(0), clock=clock), net, config.N_intervals)
    assert [m[0] for m in net.moves] == ['hi1', 'lo1']


def test_deadband_holds_a_longer_detour(config, clock):
    """Sum-of-utilisation drift: a 3-hop detour scores worse than a 1-hop congested link."""
    g = nx.Graph()
    for a, b in [('s1', 's2'), ('s1', 's3'), ('s3', 's4'), ('s4', 's2')]:
        g.add_edge(a, b, latency=1.0, bw=100)
    net = FakeNet(g, [('a', ['s1', 's2'], 500.0), ('b', ['s1', 's2'], 450.0)])
    run(ResilientDecision(g, config, rng=random.Random(0), clock=clock), net, config.N_intervals)
    assert net.moves == []
    config.dpp_bottleneck, config.dpp_weight_V0 = True, 0.1   # revision-3 bottleneck drift
    net2 = FakeNet(g, [('a', ['s1', 's2'], 500.0), ('b', ['s1', 's2'], 450.0)])
    run(ResilientDecision(g, config, rng=random.Random(0), clock=clock), net2, config.N_intervals)
    assert [m[0] for m in net2.moves] == ['a']


def test_move_load_never_negative():
    stats = make_link_stats(diamond(), {('s1', 's2'): 100.0})
    move_load(stats, ['s1', 's2'], -500.0)
    assert stats[('s1', 's2')]['bytes_per_sec'] == 0.0
    assert stats[('s1', 's2')]['utilisation'] == 0.0
    assert CAPACITY == stats[('s1', 's2')]['capacity']


# --- pursuit hold (revision 4): stop moving flows that an attacker follows ------------------------

def _pursuit_core(config, clock, **opts):
    for k, v in opts.items():
        setattr(config, k, v)
    return ResilientDecision(diamond(), config, rng=random.Random(0), clock=clock)


def _logging_env(net, events):
    env = net.env()
    env.log = lambda kind, **data: events.append((kind, data))
    return env


def test_pursuit_pins_a_flow_whose_new_path_is_attacked(config, clock):
    g = diamond()
    net = FakeNet(g, [('a', ['s1', 's2', 's4'], 500.0), ('b', ['s1', 's2', 's4'], 400.0)])
    core = _pursuit_core(config, clock, pursuit_window=8, pursuit_limit=1, pursuit_hold=30)
    events = []
    for _ in range(config.N_intervals):
        core.on_interval(net.stats(), _logging_env(net, events))
    assert net.paths['a'] == ['s1', 's3', 's4'] and not core.pinned('a')
    # the attacker follows: new traffic on the detour pushes s3-s4 above theta
    net.flows['z'] = Flow('z', 's3', 's4')
    net.paths['z'], net.rates['z'] = ['s3', 's4'], 400.0
    core.on_interval(net.stats(), _logging_env(net, events))
    assert core.pinned('a')
    assert [k for k, _ in events].count('pinned') == 1
    # a pinned flow is not moved, whatever the congestion
    assert core._try_reroute(net.flows['a'], ('s3', 's4'), 500.0, net.stats(), _logging_env(net, events)) is False
    assert events[-1][0] == 'held_pursuit'


def test_no_pursuit_when_the_detour_stays_below_theta(config, clock):
    g = diamond()
    net = FakeNet(g, [('a', ['s1', 's2', 's4'], 500.0), ('b', ['s1', 's2', 's4'], 400.0)])
    core = _pursuit_core(config, clock, pursuit_window=8, pursuit_limit=1, pursuit_hold=30)
    events = []
    for _ in range(config.N_intervals + 10):
        core.on_interval(net.stats(), _logging_env(net, events))
    assert not core.pinned('a')
    assert not any(k in ('pursuit', 'pinned') for k, _ in events)


def test_pursuit_off_by_default(config, clock):
    g = diamond()
    net = FakeNet(g, [('a', ['s1', 's2', 's4'], 500.0), ('b', ['s1', 's2', 's4'], 400.0)])
    core = ResilientDecision(g, config, rng=random.Random(0), clock=clock)
    events = []
    for _ in range(config.N_intervals):
        core.on_interval(net.stats(), _logging_env(net, events))
    net.flows['z'] = Flow('z', 's3', 's4')
    net.paths['z'], net.rates['z'] = ['s3', 's4'], 400.0
    core.on_interval(net.stats(), _logging_env(net, events))
    assert core.pursuit_window == 0 and core._recent == {} and not core.pinned('a')
