# Coding agents
For copyright and licensing reasons we can't accept any contributions made with
Claude or other LLM based coding agents. You can use whatever tools you want for
code exploration, but we can only accept human written code for the CWL project.

# Style guide
- Python 3.10+ compatible code
- PEP-484 type hints
- Prefer new style format strings https://pyformat.info/
- Use ``make format`` to format your code

It is suggested that you run `git config blame.ignoreRevsFile .git-blame-ignore-revs`
to filter out mass-formatting commits from `git blame`.

# Installing from source

- Clone the code repository locally: `git clone https://github.com/common-workflow-language/cwltool.git`
- Switch to repository directory:`cd cwltool`
- Create a virtual environment: `python3 -m venv env`
- To begin using the virtual environment, it needs to be activated: `source env/bin/activate`
- To check if you have the virtual environment set up: `which python` and it should point to python executable in your virtual env
- Install the project in editable mode along with the development dependencies: `make dev`
- After you've made the changes, you can the complete test suite via tox: ``tox``
	- If you want to run specific tests, say ``unit tests`` in Python 3.13, then: ``tox run -e py313-unit``.
	- Look at ``tox -l`` for all available tests and runtimes
- If tests are passing, you can create a PR on the GitHub repository.
- After you're done working you can deactivate the virtual environment: ``deactivate``

# Useful `make` commands:
The `make` commands below can help you to install the dependencies, format and test your code

- `make help` to show the list of commands that can be used with the make function
- `make install-dep` will install the dependencies needed by `cwltool`
- `make test` will perform the tests of `cwltool` (can take a while to run all tests)
- `make cleanup` is a shortcut for `make sort_imports format flake8 diff_pydocstyle_report`
- `make diff_pydocstyle_report` check Python docstring style for changed files only
- `make diff-cover` to run the tests and point out which lines of code that have been
   changed as compared to the `main` branch are missing test coverage. This is also calculated
   automatically after all the automatic tests run when you open a Pull Request on GitHub;
   running it locally can help you confirm that any changes or additions
   to the tests are sufficient before pushing to GitHub.
- `make format` will clean up your code according to the accepted python standard
- `make sort_imports` will clean up and sort your import statements
- `make remove_unused_imports` will remove any unneeded `import` statements
- `make flake8` will catch format issues that `make format` cannot fix automatically

