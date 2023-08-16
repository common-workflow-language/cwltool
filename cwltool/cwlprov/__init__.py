"""Stores Research Object including provenance."""

import hashlib
import os
import pwd
import re
import uuid
from getpass import getuser
from typing import IO, Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union


def _whoami() -> Tuple[str, str]:
    """Return the current operating system account as (username, fullname)."""
    username = getuser()
    try:
        fullname = pwd.getpwuid(os.getuid())[4].split(",")[0]
    except (KeyError, IndexError):
        fullname = username

    return (username, fullname)


def _check_mod_11_2(numeric_string: str) -> bool:
    """
    Validate numeric_string for its MOD-11-2 checksum.

    Any "-" in the numeric_string are ignored.

    The last digit of numeric_string is assumed to be the checksum, 0-9 or X.

    See ISO/IEC 7064:2003 and
    https://support.orcid.org/knowledgebase/articles/116780-structure-of-the-orcid-identifier
    """
    # Strip -
    nums = numeric_string.replace("-", "")
    total = 0
    # skip last (check)digit
    for num in nums[:-1]:
        digit = int(num)
        total = (total + digit) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    if result == 10:
        checkdigit = "X"
    else:
        checkdigit = str(result)
    # Compare against last digit or X
    return nums[-1].upper() == checkdigit


def _valid_orcid(orcid: Optional[str]) -> str:
    """
    Ensure orcid is a valid ORCID identifier.

    The string must be equivalent to one of these forms:

    0000-0002-1825-0097
    orcid.org/0000-0002-1825-0097
    http://orcid.org/0000-0002-1825-0097
    https://orcid.org/0000-0002-1825-0097

    If the ORCID number or prefix is invalid, a ValueError is raised.

    The returned ORCID string is always in the form of:
    https://orcid.org/0000-0002-1825-0097
    """
    if orcid is None or not orcid:
        raise ValueError("ORCID cannot be unspecified")
    # Liberal in what we consume, e.g. ORCID.org/0000-0002-1825-009x
    orcid = orcid.lower()
    match = re.match(
        # Note: concatenated r"" r"" below so we can add comments to pattern
        # Optional hostname, with or without protocol
        r"(http://orcid\.org/|https://orcid\.org/|orcid\.org/)?"
        # alternative pattern, but probably messier
        # r"^((https?://)?orcid.org/)?"
        # ORCID number is always 4x4 numerical digits,
        # but last digit (modulus 11 checksum)
        # can also be X (but we made it lowercase above).
        # e.g. 0000-0002-1825-0097
        # or   0000-0002-1694-233x
        r"(?P<orcid>(\d{4}-\d{4}-\d{4}-\d{3}[0-9x]))$",
        orcid,
    )

    help_url = (
        "https://support.orcid.org/knowledgebase/articles/"
        "116780-structure-of-the-orcid-identifier"
    )
    if not match:
        raise ValueError(f"Invalid ORCID: {orcid}\n{help_url}")

    # Conservative in what we produce:
    # a) Ensure any checksum digit is uppercase
    orcid_num = match.group("orcid").upper()
    # b) ..and correct
    if not _check_mod_11_2(orcid_num):
        raise ValueError(f"Invalid ORCID checksum: {orcid_num}\n{help_url}")

    # c) Re-add the official prefix https://orcid.org/
    return "https://orcid.org/%s" % orcid_num


Annotation = TypedDict(
    "Annotation",
    {
        "uri": str,
        "about": str,
        "content": Optional[Union[str, List[str]]],
        "oa:motivatedBy": Dict[str, str],
    },
)


class Aggregate(TypedDict, total=False):
    """RO Aggregate class."""

    uri: Optional[str]
    bundledAs: Optional[Dict[str, Any]]
    mediatype: Optional[str]
    conformsTo: Optional[Union[str, List[str]]]
    createdOn: Optional[str]
    createdBy: Optional[Dict[str, str]]


# Aggregate.bundledAs is actually type Aggregate, but cyclic definitions are not supported
class AuthoredBy(TypedDict, total=False):
    """RO AuthoredBy class."""

    orcid: Optional[str]
    name: Optional[str]
    uri: Optional[str]


def checksum_copy(
    src_file: IO[Any],
    dst_file: Optional[IO[Any]] = None,
    hasher: Optional[Callable[[], "hashlib._Hash"]] = None,
    buffersize: int = 1024 * 1024,
) -> str:
    """Compute checksums while copying a file."""
    # TODO: Use hashlib.new(Hasher_str) instead?
    if hasher:
        checksum = hasher()
    else:
        from .provenance_constants import Hasher

        checksum = Hasher()
    contents = src_file.read(buffersize)
    if dst_file and hasattr(dst_file, "name") and hasattr(src_file, "name"):
        temp_location = os.path.join(os.path.dirname(dst_file.name), str(uuid.uuid4()))
        try:
            os.rename(dst_file.name, temp_location)
            os.link(src_file.name, dst_file.name)
            dst_file = None
            os.unlink(temp_location)
        except OSError:
            pass
        if os.path.exists(temp_location):
            os.rename(temp_location, dst_file.name)  # type: ignore
    while contents != b"":
        if dst_file is not None:
            dst_file.write(contents)
        checksum.update(contents)
        contents = src_file.read(buffersize)
    if dst_file is not None:
        dst_file.flush()
    return checksum.hexdigest().lower()
