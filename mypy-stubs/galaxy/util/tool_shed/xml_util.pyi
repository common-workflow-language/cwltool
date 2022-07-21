from _typeshed import Incomplete
from galaxy.util import (
    etree as etree,
    unicodify as unicodify,
    xml_to_string as xml_to_string,
)

log: Incomplete

def create_and_write_tmp_file(elem): ...
def create_element(
    tag, attributes: Incomplete | None = ..., sub_elements: Incomplete | None = ...
): ...
def parse_xml(file_name, check_exists: bool = ...): ...
