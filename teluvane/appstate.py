# teluvane/teluvane/appstate.py
"""Shared singletons the route modules need without importing teluvane.ingest
(which imports the route modules to mount them). Importing this module has no
side effect beyond building the Store and loading policy packs; it must never
import teluvane.ingest or any teluvane.routes.* module."""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from .orgs import get_policy_framework
from .policy import PolicyPack, load_policy_pack
from .store import Store

store = Store()

POLICY_PATH = os.environ.get("TELUVANE_POLICY", "policies/eu_ai_act.yaml")
_pack = load_policy_pack(POLICY_PATH)

# Other built-in packs an org can pick instead of the default EU AI Act one. Filenames double
# as the framework's identifier in the org_policy_framework column and the /orgs/framework API.
FRAMEWORK_PACKS = {
    "eu_ai_act": _pack,
    "soc2": load_policy_pack("policies/soc2.yaml"),
    "nist_ai_rmf": load_policy_pack("policies/nist_ai_rmf.yaml"),
    "iso42001": load_policy_pack("policies/iso42001.yaml"),
}


def base_pack_for_org(org_id: str) -> PolicyPack:
    return FRAMEWORK_PACKS.get(get_policy_framework(org_id), _pack)


limiter = Limiter(key_func=get_remote_address)
