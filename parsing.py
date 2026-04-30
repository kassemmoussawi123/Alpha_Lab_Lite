import re

def splitArguments(arguments):
    """Split arguments by comma into a clean list."""
    arguments = arguments.strip()

    if arguments == "":
        return []

    argument = [s.strip() for s in arguments.split(",")]
    return argument


def parseCommand(command):
    """Parse one command line into variable, function, configs, and inputs."""
    command = command.strip()

    if command == "":
        return None

    if "=" not in command:
        raise ValueError(
            f"Invalid command: {command}. Expected format: variable = Function{{configs}}{{inputs}}"
        )

    parts = command.split("=", 1)   # split only by  first "=" safer 

    variable = parts[0].strip()
    function = parts[1].strip()

    if variable == "":
        raise ValueError(
            f"Missing variable name in command: {command}"
        )

    pattern = r"^([A-Za-z0-9_]+)\{(.*?)\}\{(.*?)\}$" # match function name and configs and inputs
    match = re.match(pattern, function)

    if not match:
        raise ValueError(
            f"Invalid function format: {function}. Use Function{{configs}}{{inputs}}"
        )
    # match.group(1) ,match.group(2) , match.group(3) are function name,configs and inputs. 
    function_name = match.group(1)
    configs_text = match.group(2)
    inputs_text = match.group(3)

    configs = splitArguments(configs_text)
    inputs = splitArguments(inputs_text)

    return {
        "variable": variable,
        "function": function_name,
        "configs": configs,
        "inputs": inputs
    }


def parseScript(script):
    """Parse a full script into a list of structured commands."""
    lines = script.strip().split("\n")
    commands = []

    for line in lines:
        line = line.strip()

        if line == "":
            continue

        command = parseCommand(line)
        commands.append(command)

    return commands