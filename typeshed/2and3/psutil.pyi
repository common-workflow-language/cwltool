from collections import namedtuple

svmem = namedtuple(
    'svmem', ['total', 'available', 'percent', 'used', 'free',
              'active', 'inactive', 'buffers', 'cached', 'shared', 'slab'])

def virtual_memory() -> svmem: ...

def cpu_count() -> int: ...