"""Profile tools: read / update the single-user profile."""
import json

READ_SPEC = {
    "type": "function",
    "function": {
        "name": "read_profile",
        "description": "Read the current user profile (role, skills, years, goal).",
        "parameters": {"type": "object", "properties": {}},
    },
}

UPDATE_SPEC = {
    "type": "function",
    "function": {
        "name": "update_profile",
        "description": "Update the user profile with new fields (e.g. role, skills, years, goal).",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {"type": "object", "description": "Profile fields to set/overwrite."}
            },
            "required": ["fields"],
        },
    },
}


def make_read_tool(conn):
    def run() -> str:
        from agent_radar.store.profile import load_profile
        return json.dumps(load_profile(conn), ensure_ascii=False)
    return run


def make_update_tool(conn):
    def run(fields: dict) -> str:
        from agent_radar.store.profile import patch_profile
        updated = patch_profile(conn, fields)
        return "Profile updated: " + json.dumps(updated, ensure_ascii=False)
    return run
