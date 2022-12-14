Style guide:
- PEP-8 (as implemented by the `black` code formatting tool)
- Python 3.6+ compatible code
- PEP-484 type hints

The development is done using `git`, we encourage you to get familiar with it.
Here's a rough guide (improvements are welcome!) 
To get the code and start working on the changes you can start a console and:
- Clone the cwltool: `git clone https://github.com/common-workflow-language/cwltool.git`
- Switch to cwltool directory: `cd cwltool`

In order to contribute to the development of `cwltool`, the source code needs to
pass the test before your changes are accepted. There are a couple ways to test
the code with your changes: let `tox` manage installation and test running in
virtual environments, or do it manually (preferably in a virtual environment):
- Install `tox` preferably using the OS' package manager, otherwise it can be
  installed with `pip install --user -U tox`
- Make your changes to the code and add tests for new cool things you're adding!
- Run the tests with the command `tox`, it's recommended to use some parameters
  as tox will try to run all the checks in all available python interpreters.
- The important tests to run are "unit tests" and "type tests". 
  To run these two in Python 3.7 (for example), we can tell tox to run only those
  tests by running: `tox -e py37-mypy`. (the `mypy` tox target also runs the
  unit tests; to just run the type checker use `make mypy` as shown below)
- Run `tox -l` to see all available tests and runtimes

For the more traditional workflow:
- Create a virtual environment: `python3 -m venv cwltool`
  (if you have multiple version of Python installed, then you can replace `python3`
  in this command with the version you want to use, `python3.10` for example)
- To begin using the virtual environment, it needs to be activated: `source venv/bin/activate`
- To check if you have the virtual environment set up: `which python`
  and it should point to python executable in your virtualenv
- Install the latest versions of `pip` and `wheel` with `pip install --upgrade pip wheel`
- Install cwltool in development mode, along with development tools:
  `make install-dep dev`
- Check the `cwltool` version which might be different from the version installed in
  general on your system: `cwltool --version`
- Make your changes to the code and add tests for new cool things you're adding!
- Run the unit-tests to see : `make test`
- After you're done working on `cwltool`, you can deactivate the virtual
  environment: `deactivate`

Before you commit your code (or at least before you push to GitHub) it is
recommended to run `make cleanup`
(which is a shortcut for `make sort_imports format flake8 diff_pydocstyle_report`)
to fix common issues and point out any remaining code formatting issues
that cannot be fixed automatically.

When tests are passing, you can create git commits in a new branch and push to
GitHub to make a pull request on `cwltool` repo

Useful `make` commands:
The `make` commands below can help you to install the dependencies, format and test your code

- `make help` to show the list of commands that can be used with the make function
- `make install-dep` will install the dependencies needed by `cwltool`
- `make format` will clean up your code according to the accepted python standard
- `make test` will perform the tests of `cwltool` (can take a while to run all tests)
- `make sort_imports` will clean up and sort your import statements
- `make remove_unused_imports` will remove any unneeded `import` statements
- `make flake8` will catch format issues that `make format` cannot fix automatically
- `make diff_pydocstyle_report` check Python docstring style for changed files only
- `make diff-cover` to run the tests and point out which lines of code that have been
   changed as compared to the `main` branch are missing test coverage. This is also calculated
   automatically after all the automatic tests run when you open a Pull Request on GitHub;
   running it locally can help you confirm that any changes or additions
   to the tests are sufficient before pushing to GitHub.
- `make cleanup` is a shortcut for `make sort_imports format flake8 diff_pydocstyle_report`
