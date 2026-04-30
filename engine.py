from parsing import parseScript as prs
import transformations 
#dictionary to map function names to actual transformation functions.
TRANSFORMATIONS = {
    "Fetch": transformations.Fetch,
    "SimpleMovingAverage": transformations.simpleMovingAverage,
    "ExponentialMovingAverage": transformations.ExponentialMovingAverage,
    "RateOfChange": transformations.RateOfChange,
    "CrossAbove": transformations.CrossAbove,
    "ConstantSeries": transformations.ConstantSeries,
    "PortfolioSimulation": transformations.PortfolioSimulation
}
def configToArgs(configs):
    """Convert config value to int, float, or string."""
    try:
       if "." in configs:
            return float(configs)
       return int(configs)
    except ValueError:
        return configs


def executeCommand(command, memory):
    """Execute a single command using the memory for variable storage."""
    variable = command["variable"]
    function_name = command["function"]

    configs = command["configs"]
    inputs = command["inputs"]

    if function_name not in TRANSFORMATIONS:
        raise ValueError(f"Unknown function: {function_name}")

    func = TRANSFORMATIONS[function_name]

    args = [configToArgs(config) for config in configs]

    input_series = []
    for input_name in inputs:
        if input_name not in memory:
            raise ValueError(f"Variable '{input_name}' was used before being created.")
        input_series.append(memory[input_name])

    if function_name == "SimpleMovingAverage":
        result = func(input_series[0], args[0])

    elif function_name == "RateOfChange":
        result = func(input_series[0], args[0])

    elif function_name == "ConstantSeries":
        result = func(input_series[0], args[0])
    
    # PortfolioSimulation{balance}{entry, exit, price}
    elif function_name == "PortfolioSimulation":
        balance = args[0]
        entry = input_series[0]
        exit = input_series[1]
        price = input_series[2]
     # PortfolioSimulation(balance, price, entry, exit)
        result = func(balance, price, entry, exit)

    else:
        result = func(*args, *input_series)#execute the function with args and inputs

    memory[variable] = result

    return memory
    
def executeScript(script):
    """Execute a full script and return the final memory state."""
    commands = prs(script) #parse the script into commands
    memory = {} #initialize empty memory

    for command in commands:
        memory = executeCommand(command, memory) #execute each command and update memory

    return memory
