#!/usr/bin/env python3
"""
Layer Management CLI for HiveBot.

This script communicates with the HiveBot backend API using the internal API key.
It should be run on the host machine (not inside a container) with the internal key
available in the environment variable INTERNAL_API_KEY.
"""

import os
import sys
import json
import argparse
import requests
from typing import Optional, Dict, Any

# Default configuration
DEFAULT_BACKEND_URL = "http://localhost:8000"
API_BASE = "/api/v1"

def get_backend_url() -> str:
    return os.getenv("HIVEBOT_BACKEND_URL", DEFAULT_BACKEND_URL)

def get_internal_key() -> str:
    key = os.getenv("INTERNAL_API_KEY")
    if not key:
        # Try to read from .env file
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("INTERNAL_API_KEY="):
                        key = line.strip().split("=", 1)[1]
                        break
    if not key:
        print("ERROR: INTERNAL_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return key

def api_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    url = f"{get_backend_url()}{API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {get_internal_key()}",
        "Content-Type": "application/json",
    }
    if method == "GET":
        resp = requests.get(url, headers=headers)
    elif method == "POST":
        resp = requests.post(url, headers=headers, json=data)
    elif method == "PATCH":
        resp = requests.patch(url, headers=headers, json=data)
    elif method == "PUT":
        resp = requests.put(url, headers=headers, json=data)
    else:
        raise ValueError(f"Unsupported method: {method}")

    try:
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_install(args):
    result = api_request("POST", "/layers/install", {"git_url": args.git_url, "version": args.version})
    print(f"Layer installed with ID: {result['layer_id']}")

def cmd_enable(args):
    api_request("PATCH", f"/layers/{args.layer_id}/enable")
    print(f"Layer {args.layer_id} enabled.")

def cmd_disable(args):
    api_request("PATCH", f"/layers/{args.layer_id}/disable")
    print(f"Layer {args.layer_id} disabled.")

def cmd_configure(args):
    config = json.loads(args.config) if args.config else {}
    api_request("PUT", f"/layers/{args.layer_id}/config?hive_id={args.hive_id}", {"config": config})
    print(f"Configuration for layer {args.layer_id} saved.")

def cmd_list(args):
    layers = api_request("GET", "/layers")
    if not layers:
        print("No layers installed.")
        return
    for l in layers:
        status = "enabled" if l["enabled"] else "disabled"
        print(f"{l['id']} - {l['name']} ({l['version']}) [{status}]")

def cmd_roles(args):
    roles = api_request("GET", f"/layers/{args.layer_id}/roles")
    if not roles:
        print("No roles found.")
        return
    for r in roles:
        print(f"{r['role_name']} (type: {r['role_type']})")

def cmd_skills(args):
    skills = api_request("GET", f"/layers/{args.layer_id}/skills")
    if not skills:
        print("No skills found.")
        return
    for s in skills:
        print(f"{s['skill_name']} ({s['skill_type']})")

def cmd_config_schema(args):
    schema = api_request("GET", f"/layers/{args.layer_id}/config-schema")
    print(json.dumps(schema, indent=2))

def cmd_loop_handlers(args):
    handlers = api_request("GET", f"/layers/{args.layer_id}/loop-handlers")
    if not handlers:
        print("No loop handlers found.")
        return
    for h in handlers:
        print(f"{h['name']} -> {h['class_path']}")

def main():
    parser = argparse.ArgumentParser(description="HiveBot Layer Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # install
    p_install = subparsers.add_parser("install", help="Install a layer from Git")
    p_install.add_argument("git_url", help="Git repository URL")
    p_install.add_argument("--version", help="Tag or branch to clone")
    p_install.set_defaults(func=cmd_install)

    # enable
    p_enable = subparsers.add_parser("enable", help="Enable a layer")
    p_enable.add_argument("layer_id", help="Layer ID (or name? use ID for now)")
    p_enable.set_defaults(func=cmd_enable)

    # disable
    p_disable = subparsers.add_parser("disable", help="Disable a layer")
    p_disable.add_argument("layer_id", help="Layer ID")
    p_disable.set_defaults(func=cmd_disable)

    # configure
    p_configure = subparsers.add_parser("configure", help="Set layer configuration for a hive")
    p_configure.add_argument("layer_id", help="Layer ID")
    p_configure.add_argument("hive_id", help="Hive ID")
    p_configure.add_argument("--config", help="JSON configuration string (default: {})")
    p_configure.set_defaults(func=cmd_configure)

    # list
    p_list = subparsers.add_parser("list", help="List installed layers")
    p_list.set_defaults(func=cmd_list)

    # roles
    p_roles = subparsers.add_parser("roles", help="List roles of a layer")
    p_roles.add_argument("layer_id", help="Layer ID")
    p_roles.set_defaults(func=cmd_roles)

    # skills
    p_skills = subparsers.add_parser("skills", help="List skills of a layer")
    p_skills.add_argument("layer_id", help="Layer ID")
    p_skills.set_defaults(func=cmd_skills)

    # config-schema
    p_schema = subparsers.add_parser("config-schema", help="Show configuration schema for a layer")
    p_schema.add_argument("layer_id", help="Layer ID")
    p_schema.set_defaults(func=cmd_config_schema)

    # loop-handlers
    p_loop = subparsers.add_parser("loop-handlers", help="List loop handlers of a layer")
    p_loop.add_argument("layer_id", help="Layer ID")
    p_loop.set_defaults(func=cmd_loop_handlers)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
