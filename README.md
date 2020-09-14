### Project structure template

Flexible project template with simple setuptools, docker and docker-compose integration.


#### Installation

Installation in virtualenv:

```bash
pip install [--editable] application/
```

Build docker image:

```bash
docker build -f application/dockerfile application/
```

Build docker-compose service:

```bash
docker-compose build
```


#### Entrypoints definition

Without custom arguments:

```python
# <package>/<module>.py

import settings

def application():   # name it at your taste
    """Do what you want. `settings` already usable here."""
    print(settings.CONFIG_PATH)

settings.Parser().parse()   # can be called inside function (ASAP)
```

With custom arguments:

```python
# entrypoints/__init__.py

import logging
import logging.config

import settings


def application():

    # Define entrypoint-specific CLI arguments and parse them

    parser.prog, parser.description = "some-name", "Utility description"

    # `dest` for positional arguments goes from their names
    parser.add_argument(
        "input", type=pathlib.Path, metavar="SOURCE", help="what to process")
    parser.add_argument(
        "output", type=pathlib.Path, metavar="DESTINATION",
        help="where to save result of processing"
    )

    # `dest` defines position in nested configuration tree
    group.add_argument(
        "-z", "--compress", dest="application.compress.on",
        action="store_true", help="toggle output compression"
    )

    group.add_argument(
        "-Z", "--compress-rate", dest="application.compress.rate",
        type=int, help="output compression rate"
    )

    parser.parse()

    # configure logging subsystem

    logging.config.dictConfig(settings.application.logging)

    logger = logging.getLogger(f"{__package__}.application")

    # run registered validators for configuration parameters

    settings.validate()

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    # Do what you want. `settings` already usable here.

    logger.debug(f"INPUT: {settings.arguments.input}")
    logger.debug(f"OUTPUT: {settings.arguments.output}")

    logger.debug(settings.application.compress)     # {'on': <>, 'rate': <>}


# Following code may also reside in `application`.

parser = settings.Parser(   # `argparse.ArgumentParser` subclass
    epilog="command-line options will take precedence over configuration files"
)

# NOTE: do not set `default` values for arguments: they will have higher
# priority than configuration files; use *settings/defaults* folder.

# `argparse` features preserved
group = parser.add_argument_group("logging")    # for pretty help message

group.add_argument(
    "--log-level", dest="application.logging.level", choices=[
        'CRITICAL', 'FATAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'
    ], metavar="LEVEL", type=str.upper, help="logger verbosity level"
)
```

Do not forget to add entrypoint methods to `console_scripts` in *setup.cfg*.


#### Configuration

Resolving priority (lower -> higher):

* package defaults from *settings/defaults*
* user-provided configuration from *--config* folder
* command-line arguments added through `settings.Parser` instance


##### Docker Compose service

You can set environment variables in your shell or in *.env* or use *docker-compose.override.yaml* to alter service configuration (including variables). For example, you can add bind-mount for *configuration* folder (please point it to out-of-VCS location in this case). Both files are excluded from VCS, so you can safely use them to provide sensitive information to service (use them if you are contributor).


##### Details

Configuration parsing starts from `settings.Parser.parse` method call. Command-line arguments will be stored in *settings.arguments* attribute and submodules from *settings* package will be imported.

Configuration files parsing will be triggered next by the following code:

```python
configuration = settings.load("<filename>.yaml")
```

Lookup starts from files in *settings/defaults*. For each file following will be done:

* default configuration tree will be updated with the same file from user-provided configuration directory (*--config* argument) if it exists
* resulting tree will be updated with *\<filename\>* subtree from *settings.arguments* if it exists

As you can see, only files in *settings/defaults* ("precompiled" settings) MUST exist. Previous sample will fail with `FileNotFoundError` if it doesn't.


##### Environment variables

Environment variable references in all parameters acquired at each stage will be resolved. Default values may be provided using Bash syntax for [parameters expansion](https://wiki.bash-hackers.org/syntax/pe), e.g. `${VARIABLE:-default}`. Error messages are also supported: `${VARIABLE:?error message}`.

If you prefer to organize configuration subtrees as *settings* submodules, you can use the following template for them:

```python
import pathlib

import settings


# load configuration; already expanded with user config and arguments
configuration = settings.load(f"{pathlib.Path(__file__).stem}.yaml")


# prepare configuration entries


# set entries as module variables in order to make them
# importable and accessible using dotted-path notation

globals().update(globals().pop("configuration"))
```

You can prepare arguments if necessary:

```python
import aiohttp

# original timeout tree will be lost
configuration.timeout = aiohttp.ClientTimeout(
    total=configuration.timeout.total, connect=configuration.timeout.connect)
```


##### Usage

In any module or method after *settings.Parser.parse* is invoked:

```python
from aiohttp import ClientSession

from settings import application


session = ClientSession(timeout=application.timeout)
```
