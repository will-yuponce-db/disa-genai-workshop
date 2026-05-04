"""
Workaround for: dbacademy creates per-user Vector Search endpoints with
names derived from the Vocareum user email. For long org prefixes (e.g.
'vc_2_0_c4a2c694org550_234_<user>') the generated name exceeds the
Databricks 50-character limit and the create call fails with
InvalidParameterValue.

This module monkey-patches the databricks-sdk so any name passed to
VectorSearchEndpointsAPI.{create,get,delete}_endpoint is sanitized to a
form Databricks will accept. Sanitization is deterministic (same input
always yields same output), so subsequent get/delete calls inside
dbacademy resolve to the same endpoint.

Import this module BEFORE `from dbacademy import voc_init`.
"""
import hashlib
import re

_VS_NAME_MAX = 50  # Databricks: must be < 50 chars (we keep <=49 to be safe)


def sanitize_vs_name(name):
    if not isinstance(name, str):
        return name
    s = re.sub(r"[^a-z0-9._-]", "_", name.lower())
    s = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", s)
    if not s:
        s = "vs_" + hashlib.sha1(name.encode()).hexdigest()[:8]
    if len(s) >= _VS_NAME_MAX:
        h = hashlib.sha1(name.encode()).hexdigest()[:8]
        prefix = re.sub(r"[^a-z0-9]+$", "", s[: _VS_NAME_MAX - 10]) or "vs"
        s = f"{prefix}_{h}"
    return s


def apply():
    try:
        from databricks.sdk.service import vectorsearch as _vs
    except Exception as e:
        print(f"[vs_patch] databricks-sdk not importable yet: {e}")
        return

    api = _vs.VectorSearchEndpointsAPI

    def wrap(method_name):
        if not hasattr(api, method_name):
            return
        orig = getattr(api, method_name)

        def wrapper(self, *args, **kwargs):
            if args:
                args = (sanitize_vs_name(args[0]),) + args[1:]
            elif "name" in kwargs:
                kwargs["name"] = sanitize_vs_name(kwargs["name"])
            return orig(self, *args, **kwargs)

        wrapper.__wrapped__ = orig
        setattr(api, method_name, wrapper)

    for m in (
        "create_endpoint",
        "create_endpoint_and_wait",
        "get_endpoint",
        "delete_endpoint",
        "update_endpoint_budget_policy",
        "update_endpoint_custom_tags",
        "wait_get_endpoint_vector_search_endpoint_online",
    ):
        wrap(m)

    print("[vs_patch] VectorSearchEndpointsAPI name sanitization applied")


apply()
