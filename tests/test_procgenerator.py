import os

from cwltool.main import main

from .util import get_data, windows_needs_docker


@windows_needs_docker
def test_missing_enable_ext() -> None:
    # Requires --enable-ext and --enable-dev
    try:
        opt = os.environ.get("CWLTOOL_OPTIONS")

        if "CWLTOOL_OPTIONS" in os.environ:
            del os.environ["CWLTOOL_OPTIONS"]
        assert main([get_data("tests/wf/generator/zing.cwl"), "--zing", "zipper"]) == 1

        assert (
            main(
                [
                    "--enable-ext",
                    "--enable-dev",
                    get_data("tests/wf/generator/zing.cwl"),
                    "--zing",
                    "zipper",
                ]
            )
            == 0
        )

        os.environ["CWLTOOL_OPTIONS"] = "--enable-ext --enable-dev"
        assert main([get_data("tests/wf/generator/zing.cwl"), "--zing", "zipper"]) == 0
    finally:
        if opt is not None:
            os.environ["CWLTOOL_OPTIONS"] = opt
        elif "CWLTOOL_OPTIONS" in os.environ:
            del os.environ["CWLTOOL_OPTIONS"]
