# Stubs for cachecontrol.wrapper (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Union
from .adapter import CacheControlAdapter as CacheControlAdapter
from .cache import DictCache, BaseCache
import requests

def CacheControl(sess: requests.sessions.Session,
                 cache: Union[DictCache, BaseCache] = None,
                 cache_etags: bool = True,
                 serializer=None,
                 heuristic=None) -> requests.sessions.Session: ...
