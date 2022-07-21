import json

from _typeshed import Incomplete

to_json_string = json.dumps
from_json_string = json.loads

def safe_dumps(*args, **kwargs): ...
def validate_jsonrpc_request(request, regular_methods, notification_methods): ...
def validate_jsonrpc_response(response, id: Incomplete | None = ...): ...
def jsonrpc_request(
    method,
    params: Incomplete | None = ...,
    id: Incomplete | None = ...,
    jsonrpc: str = ...,
): ...
def jsonrpc_response(
    request: Incomplete | None = ...,
    id: Incomplete | None = ...,
    result: Incomplete | None = ...,
    error: Incomplete | None = ...,
    jsonrpc: str = ...,
): ...
