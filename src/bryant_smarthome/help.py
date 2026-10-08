"""Offline command descriptions."""

COMMANDS = {"login": ("Verify username/password credentials.", ["bryant login"])}
CONTROLS = {"mode", "temperature", "fan", "resume", "vacation", "vacation-cancel", "mutate"}
GUIDE = "Use 'bryant COMMAND --help' for command details."


def catalog(root, commands):
    return {"version": 1, "commands": [{"name": name, "help": command.description or command.format_help()}
            for name, command in sorted(commands.items())]}
