from _typeshed import Incomplete
from galaxy.util import galaxy_directory as galaxy_directory, unicodify as unicodify
from galaxy.util.object_wrapper import (
    sanitize_lists_to_string as sanitize_lists_to_string,
)

log: Incomplete

def read_dbnames(filename): ...

class GenomeBuilds:
    default_value: str
    default_name: str
    def __init__(
        self, app, data_table_name: str = ..., load_old_style: bool = ...
    ) -> None: ...
    def get_genome_build_names(self, trans: Incomplete | None = ...): ...
    def get_chrom_info(
        self,
        dbkey,
        trans: Incomplete | None = ...,
        custom_build_hack_get_len_from_fasta_conversion: bool = ...,
    ): ...
