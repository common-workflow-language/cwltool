Style guide:
- PEP-8
- Python 3.7+ compatible code
- PEP-484 type hints
- Vertically align the type hints in function definitions

The development is done using ``git``, we encourage you to get familiar with it.
Here's a rough guide (improvements are welcome!) 
To get the code and start working on the changes you can start a console and:
- Clone the cwltool: ``git clone https://github.com/common-workflow-language/cwltool.git``
- Switch to cwltool directory: ``cd cwltool``

In order to contribute to the development of ``cwltool``, the source code needs to pass the test before your changes are accepted.
There are a couple ways to test the code with your changes: let `tox` manage installation and test running in virtual environments, or do it manually (preferably in a virtual environment):
- Install ``tox`` preferably using the OS' package manager, otherwise it can be installed with ``pip install --user -U tox``
- Make your changes to the code and add tests for new cool things you're adding!
- Run the tests with the command ``tox``, it's recommended to use some parameters as tox will try to run all the checks in all available python interpreters.
- The important tests to run are ``unit tests`` and  ``type tests``.
  To run these two in Python 3.7, we can tell tox to run only those tests by running: ``tox -e py37-unit,py37-mypy2,py37-mypy3``.
- Run ``tox -l`` to see all available tests and runtimes

For the more traditional workflow:
- Create a virtual environment: ``python3 -m venv cwltool``
- To begin using the virtual environment, it needs to be activated: ``source bin/activate``
- To check if you have the virtual environment set up: ``which python`` and it should point to python executable in your virtualenv
- Install cwltool: ``pip install -e .``
- Check the version which might be different from the version installed in general on any system: ``cwltool --version``
- Make your changes to the code and add tests for new cool things you're adding!
- Run the unit-tests to see : ``python setup.py test``
- After you're done working on ``cwltool``, you can deactivate the virtual environment: ``deactivate``

When tests are passing, you can simply commit and create a PR on ``cwltool`` repo