"""Static analysis of the research DSL. No generated Python is executed."""
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import json
import math

from parsing import parseScript
from engine import configToArgs

SIGNATURES = {
    "SimpleMovingAverage": (1, 1),
    "ExponentialMovingAverage": (1, 1),
    "RateOfChange": (1, 1),
    "ConstantSeries": (1, 1),
    "CrossAbove": (0, 2),
}

@dataclass(frozen=True)
class Node:
    operator: str
    configs: tuple = ()
    children: tuple = ()

    def canonical(self):
        return [self.operator, list(self.configs), [n.canonical() for n in self.children]]

def analyze(script, max_commands=16, max_nodes=128, max_depth=8):
    """Build expression trees and count expanded nodes, including reused subtrees."""
    if not isinstance(script, str) or not script.strip() or len(script) > 10000:
        raise ValueError("Script must have 1..10000 characters")
    commands = parseScript(script)
    if len(commands) > max_commands:
        raise ValueError("Strategy exceeds command limit")
    variables = {"price": (Node("price"), 1, 1)}
    for command in commands:
        name, op = command["variable"], command["function"]
        if not name.isidentifier() or name in variables:
            raise ValueError("Variables must be unique valid identifiers")
        if op not in SIGNATURES:
            raise ValueError("Unsupported research operation: " + op)
        nc, ni = SIGNATURES[op]
        if len(command["configs"]) != nc or len(command["inputs"]) != ni:
            raise ValueError("Incorrect argument count for " + op)
        configs = tuple(configToArgs(x) for x in command["configs"])
        for v in configs:
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError("Strategy configs must be finite numbers")
        if op in ("SimpleMovingAverage", "RateOfChange"):
            if type(configs[0]) is not int or configs[0] < 1:
                raise ValueError("Window/period must be a positive integer")
        if op == "ExponentialMovingAverage" and not 0 < configs[0] <= 1:
            raise ValueError("EMA alpha must be in (0,1]")
        if any(x not in variables for x in command["inputs"]):
            raise ValueError("Strategy contains an undefined input")
        children = [variables[x] for x in command["inputs"]]
        nodes = 1 + sum(x[1] for x in children)
        depth = 1 + max((x[2] for x in children), default=0)
        if nodes > max_nodes or depth > max_depth:
            raise ValueError("Strategy exceeds expression complexity limits")
        variables[name] = (Node(op, configs, tuple(x[0] for x in children)), nodes, depth)
    if not all(k in variables for k in ("entry", "exit")):
        raise ValueError("Strategy must define entry and exit")
    nodes = sum(variables[k][1] for k in ("entry", "exit"))
    depth = max(variables[k][2] for k in ("entry", "exit"))
    if nodes > max_nodes:
        raise ValueError("Strategy exceeds total node limit")
    canonical = [variables[k][0].canonical() for k in ("entry", "exit")]
    encoded = json.dumps(canonical, separators=(",", ":"), allow_nan=False)
    return {"commands":len(commands), "nodes":nodes, "depth":depth,
            "fingerprint":hashlib.sha256(encoded.encode()).hexdigest(),
            "ast":canonical}

def _tokens(ast):
    shape, numbers = [], []
    def visit(node):
        op, configs, children = node
        shape.extend([op, str(len(configs)), "("])
        numbers.extend(configs)
        for child in children:
            visit(child)
        shape.append(")")
    for tree in ast:
        visit(tree)
    return shape, numbers

def similarity(left, right):
    """Heuristic [0,1] score; detects syntax/parameter similarity, not semantic equivalence."""
    ls, ln = _tokens(left["ast"])
    rs, rn = _tokens(right["ast"])
    structural = SequenceMatcher(None, ls, rs, autojunk=False).ratio()
    if len(ln) != len(rn):
        numeric = 0.0
    elif not ln:
        numeric = 1.0
    else:
        numeric = sum(max(0, 1-abs(a-b)/max(abs(a),abs(b),1))
                      for a,b in zip(ln,rn))/len(ln)
    return .6*structural + .4*numeric

def check_strategy(script, previous=(), similarity_threshold=.995, **limits):
    if not 0 <= similarity_threshold <= 1:
        raise ValueError("Similarity threshold must be in [0,1]")
    current = analyze(script, **limits)
    scores = [similarity(current, analyze(other, **limits)) for other in previous]
    current["max_similarity"] = max(scores, default=0.0)
    if scores and current["max_similarity"] >= similarity_threshold:
        raise ValueError("Strategy is too similar to a previous experiment")
    return current
