This is a collection CLI tools for working Azure landing zones, billing profiles and workspaces.

## Getting Started

* Install [poetry](https://python-poetry.org)
* Install dependencies: `poetry install`
* Get a shell in the created venv to run the scripts: `poetry shell`
* Run the scripts:
  * `python lz.py <args>`
  * `python mrg.py <args>`
  * `python billing_profile.py <args>`
* The "e2e" target in the `lz.py` script builds an MRG, billing profile and landing zone in one command.

