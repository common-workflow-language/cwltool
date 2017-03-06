from pkg_resources import Requirement, resource_filename, ResolutionError  # type: ignore
import os

def get_data(filename):
    filepath = None
    try:
        filepath = resource_filename(
            Requirement.parse("cwltool"), filename)
    except ResolutionError:
        pass
    if not filepath or not os.path.isfile(filepath):
        filepath = os.path.join(os.path.dirname(__file__), os.pardir, filename)
    return filepath
