from galaxy.util import smart_str as smart_str, unicodify as unicodify
from galaxy.util.hash_util import hmac_new as hmac_new

encoding_sep: str
encoding_sep2: str

def tool_shed_decode(value): ...
def tool_shed_encode(val): ...
