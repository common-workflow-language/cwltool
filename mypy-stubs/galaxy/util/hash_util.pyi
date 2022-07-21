import hashlib as hashlib

sha1 = hashlib.sha1
sha256 = hashlib.sha256
sha512 = hashlib.sha512
sha = sha1
md5 = hashlib.md5

def new_secure_hash(text_type): ...
def hmac_new(key, value): ...
def is_hashable(value): ...
