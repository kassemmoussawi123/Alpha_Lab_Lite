"""Validated execution of registered DSL operations only."""
import math
from parsing import parseScript
import transformations as t

REGISTRY = {
 "Fetch": (1,0,lambda c,i:t.Fetch(c[0])),
 "SimpleMovingAverage": (1,1,lambda c,i:t.simpleMovingAverage(i[0],c[0])),
 "ExponentialMovingAverage": (1,1,lambda c,i:t.ExponentialMovingAverage(c[0],i[0])),
 "RateOfChange": (1,1,lambda c,i:t.RateOfChange(i[0],c[0])),
 "CrossAbove": (0,2,lambda c,i:t.CrossAbove(*i)),
 "ConstantSeries": (1,1,lambda c,i:t.ConstantSeries(i[0],c[0])),
 "PortfolioSimulation": (1,3,lambda c,i:t.PortfolioSimulation(c[0],i[2],i[0],i[1]))
}
def configToArgs(value):
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return value

def executeCommand(command,memory):
    name = command["function"]
    if name not in REGISTRY:
        raise ValueError("Unknown function: "+name)
    nc, ni, fn = REGISTRY[name]
    if len(command["configs"]) != nc or len(command["inputs"]) != ni:
        raise ValueError(f"{name} expects {nc} configs and {ni} inputs")
    configs = [configToArgs(x) for x in command["configs"]]
    inputs = []
    for key in command["inputs"]:
        if key not in memory:
            raise ValueError(f"Variable '{key}' was used before being created")
        inputs.append(memory[key])
    if inputs and (any(not isinstance(x,list) or not x for x in inputs)
                   or len({len(x) for x in inputs}) != 1):
        raise ValueError("Input series must be nonempty lists with equal lengths")
    if nc and name != "Fetch":
        value = configs[0]
        if not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError("Config must be a finite number")
        if name in ("SimpleMovingAverage","RateOfChange") and (type(value) is not int or value < 1):
            raise ValueError("Window/period must be a positive integer")
        if name == "ExponentialMovingAverage" and not 0 < value <= 1:
            raise ValueError("EMA alpha must be in (0,1]")
    result = fn(configs,inputs)
    if result is None:
        raise ValueError("Dataset not found")
    memory[command["variable"]] = result
    return memory

def executeScript(script,initial_memory=None):
    if len(script) > 50000:
        raise ValueError("Script exceeds 50000 characters")
    memory = dict(initial_memory or {})
    commands = parseScript(script)
    if len(commands) > 100:
        raise ValueError("Script exceeds 100 commands")
    for index, command in enumerate(commands,1):
        try:
            executeCommand(command,memory)
        except (ValueError,TypeError,IndexError) as error:
            raise ValueError(f"Command {index}: {error}") from error
    return memory
