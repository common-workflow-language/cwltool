import shutil
import tempfile
from io import StringIO
from typing import Callable, Dict, List, Tuple, Union

import pytest

from cwltool.main import main
from cwltool.secrets import SecretStore
from cwltool.utils import CWLObjectType

from .util import get_data, needs_docker, needs_singularity


@pytest.fixture
def secrets() -> Tuple[SecretStore, CWLObjectType]:
    """Fixture to return a secret store."""
    sec_store = SecretStore()
    job: CWLObjectType = {"foo": "bar", "baz": "quux"}

    sec_store.store(["foo"], job)
    return sec_store, job


def test_obscuring(secrets: Tuple[SecretStore, CWLObjectType]) -> None:
    """Basic test of secret store."""
    storage, obscured = secrets
    assert obscured["foo"] != "bar"
    assert obscured["baz"] == "quux"
    result = storage.retrieve(obscured)
    assert isinstance(result, dict) and result["foo"] == "bar"


obscured_factories_expected = [
    ((lambda x: "hello %s" % x), "hello bar"),
    ((lambda x: ["echo", "hello %s" % x]), ["echo", "hello bar"]),
    ((lambda x: {"foo": x}), {"foo": "bar"}),
]


@pytest.mark.parametrize("factory,expected", obscured_factories_expected)
def test_secrets(
    factory: Callable[[str], CWLObjectType],
    expected: Union[str, List[str], Dict[str, str]],
    secrets: Tuple[SecretStore, CWLObjectType],
) -> None:
    storage, obscured = secrets
    obs = obscured["foo"]
    assert isinstance(obs, str)
    pattern = factory(obs)
    assert pattern != expected

    assert storage.has_secret(pattern)
    assert storage.retrieve(pattern) == expected

    assert obscured["foo"] != "bar"
    assert obscured["baz"] == "quux"


@needs_docker
def test_secret_workflow_log() -> None:
    stream = StringIO()
    tmpdir = tempfile.mkdtemp()
    main(
        [
            "--debug",
            "--enable-ext",
            "--outdir",
            tmpdir,
            get_data("tests/wf/secret_wf.cwl"),
            "--pw",
            "Hoopla!",
        ],
        stderr=stream,
    )

    shutil.rmtree(tmpdir)
    assert "Hoopla!" not in stream.getvalue()


@needs_singularity
def test_secret_workflow_log_singularity() -> None:
    stream = StringIO()
    tmpdir = tempfile.mkdtemp()
    main(
        [
            "--debug",
            "--outdir",
            tmpdir,
            "--singularity",
            get_data("tests/wf/secret_wf.cwl"),
            "--pw",
            "Hoopla!",
        ],
        stderr=stream,
    )

    shutil.rmtree(tmpdir)
    assert "Hoopla!" not in stream.getvalue()


@needs_docker
def test_secret_workflow_log_override() -> None:
    stream = StringIO()
    tmpdir = tempfile.mkdtemp()
    main(
        [
            "--debug",
            "--outdir",
            tmpdir,
            "--enable-ext",
            "--overrides",
            get_data("tests/wf/override-no-secrets.yml"),
            get_data("tests/wf/secret_wf.cwl"),
            "--pw",
            "Hoopla!",
        ],
        stderr=stream,
    )
    shutil.rmtree(tmpdir)

    assert "Hoopla!" in stream.getvalue()
