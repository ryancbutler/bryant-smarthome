import argparse
from datetime import datetime
import getpass
import json
import math
from pathlib import Path
import sys

from . import auth
from .client import AuthenticationError, Client, ClientError
from .config import load_environment
from .help import COMMANDS, CONTROLS, GUIDE, catalog
from .operations import DEVICE, ENTRY_SYSTEM, HOMES, MUTATIONS, SYSTEM, SYSTEMS, USER, mutation

def username_for(args):
    username = args.username or args.environment.get("BRYANT_USERNAME")
    if not username:
        username = prompt(args, "Email / API username: ")
    return username


def credentials(args, *, force_login=False):
    username = username_for(args)
    if not force_login:
        saved = auth.load_saved(username)
        if saved:
            token = auth.usable_access_token(saved)
            if token:
                return {"token": token, "username": saved.get("username") or username,
                        "refresh_token": saved["refresh_token"], "storage_username": username}
            credential = auth.refresh(saved.get("username") or username, saved["refresh_token"], args.timeout)
            auth.save(credential, username)
            credential["storage_username"] = username
            return credential
    password = args.environment.get("BRYANT_PASSWORD")
    if not password:
        password = prompt(args, "Password (hidden): ", hidden=True)
    credential = auth.login(username, password, args.timeout)
    auth.save(credential, username)
    credential["storage_username"] = username
    return credential


def temperature(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("temperature must be numeric") from None
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError("temperature must be finite")
    return value  # preserve device-native representation; no inferred conversion


def validate_vacation(fields):
    try:
        start = datetime.fromisoformat(fields["vacstart"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(fields["vacend"].replace("Z", "+00:00"))
        if start.utcoffset() is None or end.utcoffset() is None or end <= start:
            raise ValueError
        heat, cool = float(fields["vacmint"]), float(fields["vacmaxt"])
        if not math.isfinite(heat) or not math.isfinite(cool) or heat > cool:
            raise ValueError
        if not isinstance(fields["vacfan"], str) or not fields["vacfan"]:
            raise ValueError
        humidity = fields["humidityVacation"]
        if not isinstance(humidity, dict) or not {"humidifier", "rclg", "rclgovercool", "rhtg"}.issubset(humidity):
            raise ValueError
    except (ValueError, TypeError, AttributeError, KeyError):
        raise ClientError("Vacation requires ordered timezone-aware ISO dates, finite ordered setpoints, fan, and humidityVacation fields humidifier/rclg/rclgovercool/rhtg.") from None


def parser():
    p = argparse.ArgumentParser(
        prog="bryant", description="Bryant SmartHome: JSON reads and offline control previews.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Use 'bryant docs' for the agent guide, 'bryant docs --format json' for\n"
               "machine-readable discovery, or 'bryant COMMAND --help' for examples.\n"
               "Global options go before COMMAND. Controls require --execute to send.")
    p.add_argument("--non-interactive", action="store_true", help="fail instead of prompting for login input (recommended for agents)")
    p.add_argument("--username", help="username (overrides BRYANT_USERNAME)")
    p.add_argument("--env-file", type=Path, help="dotenv file (default: .env in the current directory)")
    p.add_argument("--timeout", type=float, default=30, help="network timeout in seconds")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="verify username/password and save a secure session")
    sub.add_parser("logout", help="remove the saved secure session for a username")
    sub.add_parser("operations", help="list supported mutations and their GraphQL input types")
    docs = sub.add_parser("docs", help="offline usage guide and machine-readable command catalog")
    docs.add_argument("topic", nargs="?", choices=sorted(COMMANDS), help="optional command to document")
    docs.add_argument("--format", choices=("text", "json"), default="text", help="guide/help text or versioned JSON catalog")
    sub.add_parser("homes", help="list homes, systems, and devices")
    sub.add_parser("user", help="read user profile, home members and temperature units")
    sub.add_parser("systems", help="list Infinity systems and diagnostic capability/status")
    d = sub.add_parser("device", help="read device points and desired configuration")
    d.add_argument("location_id")
    d.add_argument("device_id")
    for name in ("system", "zones", "entry-system"):
        q = sub.add_parser(name, help="read system or zone state")
        q.add_argument("serial")
    m = sub.add_parser("mode", help="preview/set Infinity mode")
    m.add_argument("serial")
    m.add_argument("value", help="device-supported mode, passed unchanged")
    t = sub.add_parser("temperature", help="preview/set Infinity manual activity heat/cool setpoints")
    t.add_argument("serial")
    t.add_argument("zone")
    t.add_argument("--heat", required=True, type=temperature)
    t.add_argument("--cool", required=True, type=temperature)
    t.add_argument("--fan", required=True, help="existing/supported manual fan value")
    t.add_argument("--previous-fan", help="optional existing previousFan value")
    f = sub.add_parser("fan", help="preview/set an Infinity zone activity fan")
    f.add_argument("serial")
    f.add_argument("zone")
    f.add_argument("value")
    f.add_argument("--activity", required=True, help="current zone activity type")
    resume = sub.add_parser("resume", help="resume an Infinity zone schedule by removing its hold")
    resume.add_argument("serial")
    resume.add_argument("zone")
    cancel = sub.add_parser("vacation-cancel", help="cancel Infinity vacation settings")
    cancel.add_argument("serial")
    vacation = sub.add_parser("vacation", help="set Infinity vacation using explicit input fields")
    vacation.add_argument("serial")
    vacation.add_argument("--input-file", type=Path, required=True)
    raw = sub.add_parser("mutate", help="preview/execute a supported mutation with explicit JSON input")
    raw.add_argument("operation", choices=sorted(MUTATIONS))
    raw.add_argument("--input-file", type=Path, required=True, help="file containing the input object, not variables wrapper")
    for action in (m, t, f, raw, resume, cancel, vacation):
        action.add_argument("--execute", action="store_true", help="send the mutation; otherwise only print a preview")
    for name, command in sub.choices.items():
        description, examples = COMMANDS.get(name, (getattr(command, "description", ""), []))
        command.description = description
        command.formatter_class = argparse.RawDescriptionHelpFormatter
        command.epilog = "Examples (replace uppercase placeholders):\n  " + "\n  ".join(examples)
        if name in CONTROLS:
            command.epilog += "\n\nOffline preview by default. Append --execute only after authorization and\n"
            command.epilog += "a current-state check; verify system/zone state afterward."
        for action in command._actions:
            if action.help is None:
                action.help = {"serial": "system serial from homes/systems",
                               "zone": "zone identifier from zones SERIAL",
                               "location_id": "locationId from homes",
                               "device_id": "deviceId from homes",
                               "value": "device-supported value, passed unchanged",
                               "operation": "supported mutation name; see operations",
                               "input_file": "UTF-8 JSON input object; see command description",
                               "heat": "heat setpoint in device-native units; must be finite and <= cool",
                               "cool": "cool setpoint in device-native units; must be finite and >= heat"}.get(action.dest)
    return p


def prompt(args, label, *, hidden=False):
    if args.non_interactive:
        raise ClientError("Configure BRYANT_USERNAME and BRYANT_PASSWORD for non-interactive use.")
    return (getpass.getpass(label) if hidden else input(label)).strip()


def run(args):
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ClientError("Timeout must be positive and finite.")
    if args.command == "login":
        credential = credentials(args, force_login=True)
        return {"username": credential["username"], "authenticated": True}
    if args.command == "logout":
        auth.clear(username_for(args))
        return {"logged_out": True}
    if args.command == "operations":
        return {name: fields[0] for name, fields in sorted(MUTATIONS.items())}
    is_mutation = args.command in ("mode", "temperature", "fan", "mutate", "resume", "vacation", "vacation-cancel")
    if is_mutation:
        if args.command == "mode":
            payload = mutation("updateInfinityConfig", {"serial": args.serial, "mode": args.value})
        elif args.command == "temperature":
            fields = {"serial": args.serial, "zoneId": args.zone, "activityType": "manual",
                      "htsp": args.heat, "clsp": args.cool, "fan": args.fan}
            if float(args.heat) > float(args.cool):
                raise ClientError("Heat setpoint cannot exceed cool setpoint.")
            if args.previous_fan is not None:
                fields["previousFan"] = args.previous_fan
            payload = mutation("updateInfinityZoneActivity", fields)
        elif args.command == "fan":
            payload = mutation("updateInfinityZoneActivity", {"serial": args.serial, "zoneId": args.zone,
                               "activityType": args.activity, "fan": args.value})
        elif args.command == "resume":
            payload = mutation("updateInfinityZoneConfig", {"serial": args.serial, "zoneId": args.zone,
                               "hold": "off", "holdActivity": None, "otmr": None})
        elif args.command == "vacation-cancel":
            payload = mutation("updateInfinityConfig", {"serial": args.serial, "vacat": "off", "vacstart": None, "vacend": None})
        else:
            try:
                fields = json.loads(args.input_file.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                raise ClientError("Cannot read input file as JSON.") from None
            if not isinstance(fields, dict) or not fields:
                raise ClientError("Mutation input must be a nonempty JSON object.")
            if args.command == "vacation":
                required = {"vacstart", "vacend", "vacfan", "vacmint", "vacmaxt", "humidityVacation"}
                if not required.issubset(fields):
                    raise ClientError("Vacation input requires vacstart, vacend, vacfan, vacmint, vacmaxt, humidityVacation.")
                if fields.get("serial", args.serial) != args.serial:
                    raise ClientError("Vacation input serial does not match the command.")
                validate_vacation(fields)
                fields = {**fields, "serial": args.serial, "vacat": "on"}
                payload = mutation("updateInfinityConfig", fields)
            else:
                payload = mutation(args.operation, fields)
        if not args.execute:
            return {"preview": True, "endpoint": "https://dataservice.infinity.iot.carrier.com/graphql", "body": payload}
    else:
        cred = credentials(args)
        username = cred["username"]
        if args.command in ("homes", "device", "user", "systems") and not username:
            raise ClientError("Supply --username or BRYANT_USERNAME.")
        if args.command == "homes":
            payload = {"query": HOMES, "variables": {"username": username}}
        elif args.command in ("user", "systems"):
            payload = {"query": USER if args.command == "user" else SYSTEMS, "variables": {"userName": username}}
        elif args.command == "device":
            payload = {"query": DEVICE, "variables": {"username": username, "locationId": args.location_id, "deviceId": args.device_id}}
        else:
            payload = {"query": ENTRY_SYSTEM if args.command == "entry-system" else SYSTEM,
                       "variables": {"serial": args.serial}}
    if is_mutation:
        cred = credentials(args)
    try:
        result = Client(cred["token"], args.timeout).execute(payload)
    except AuthenticationError:
        if is_mutation or not cred.get("refresh_token"):
            raise
        # A read may be retried once after a fresh token; controls are never replayed.
        credential = auth.refresh(cred["username"], cred["refresh_token"], args.timeout)
        auth.save(credential, cred["storage_username"])
        result = Client(credential["token"], args.timeout).execute(payload)
    if is_mutation and (not isinstance(result, dict) or not isinstance(result.get(payload["operationName"]), dict)):
        raise ClientError("Mutation returned no result; success cannot be confirmed.")
    if args.command == "zones" and isinstance(result, dict):
        return {"status": (result.get("status") or {}).get("zones"),
                "config": (result.get("config") or {}).get("zones")}
    return result


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    try:
        if args.command == "docs":
            commands = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction)).choices
            if args.format == "json":
                result = catalog(root, commands)
                if args.topic:
                    result["commands"] = [c for c in result["commands"] if c["name"] == args.topic]
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(commands[args.topic].format_help() if args.topic else GUIDE, end="")
            return 0
        if args.command == "operations":
            print(json.dumps({name: fields[0] for name, fields in sorted(MUTATIONS.items())}, indent=2))
            return 0
        args.environment = ({} if args.command in CONTROLS and not args.execute
                            else load_environment(args.env_file))
        print(json.dumps(run(args), indent=2, ensure_ascii=False))
        return 0
    except (ClientError, EOFError) as exc:
        print(f"bryant: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
