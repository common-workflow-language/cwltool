In order to contribute to the development of ``cwltool``, you need to install cwltool from source (preferably in a virtual environment):
Here's a rough 
- Install virtualenv via pip: ``pip install virtualenv``
- Clone the cwltool: ``git clone https://github.com/common-workflow-language/cwltool.git``
- Switch to cwltool directory: ``cd cwltool``
- Create a virtual environment: ``virtualenv cwltool``
- To begin using the virtual environment, it needs to be activated: ``source bin/activate``
- To check if you have the virtual environment set up: ``which python`` and it should point to python executable in your virtual env
- Install cwltool in the virtual environment: ``pip install .``
- Check the version which might be different from the version installed in general on any system: ``cwltool --version``
- After you've made the changes, you can the complete test suite via tox: ``tox``
	- If you want to run specific tests, say ``unit tests`` in Python 3.5, then: ``tox -e py35-unit``.
	- Look at ``tox.ini`` for all available tests and runtimes
- If tests are passing, you can simply commit and create a PR on ``cwltool`` repo:
- After you're done working on the ``cwltool``, you can deactivate the virtual environment: ``deactivate``