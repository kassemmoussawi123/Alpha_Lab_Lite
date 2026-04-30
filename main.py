import argparse
import sys
from engine import executeScript
from storage import save_result, load_result


def run_execute(script):
    """Execute script and save result."""
    memory = executeScript(script)
    script_id = save_result(memory)
    print(f"Script successfully executed: {script_id}")

def run_view(script_id, variables):
    """Load and display saved variables."""
    data = load_result(script_id, variables)

    for name, values in data.items():
        print(f"{name}: {values}")

def main():
    """Main function to handle CLI commands."""
    parser = argparse.ArgumentParser(description="AlphaLabLite CLI")
    subparsers = parser.add_subparsers(dest="command")

    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("file", nargs="?", help="Path to script file")

    view_parser = subparsers.add_parser("view")
    view_parser.add_argument("--id", required=True, help="ID of the script to view")
    view_parser.add_argument("variables", nargs="+", help="Variables to view")
    
    args = parser.parse_args()

    if args.command == "execute":
        if args.file:
            with open(args.file, "r") as file:
                script = file.read()
        else:
            script = sys.stdin.read()

        run_execute(script)

    elif args.command == "view":
        run_view(args.id, args.variables)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
