"""
Each settings' submodule contains configuration from corresponding file.
Configuration loading priority (from lower to higher; in `dict.update` order):

- files from defaults folder (shipped with PIP package; always exists)
- files from configuration folder provided by user (missing files ignored)
- configuration provided from CLI arguments (through `Parser` object)

This way only files in *settings/defaults* MUST exist. This makes possible
to configure application's runtime settings in more flexible way.

How to add parameter (may be nested) into existing configuration group:
- add it to corresponding file in *settings/defaults* folder
- prepare it in it's submodule if it makes sense/required
- add corresponding CLI argument if needed

Create YAML file in *settings/defaults* folder and submodule with following
base content to add new root settings category:

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

Example
-------

For example, you need to provide API authentication key as runtime setting.
You can add following structure to *defaults/application.yaml*:

```yaml
security:
  secret: ${API_SECRET:?API secret must be set}
```

In this way your parameter will be taken from environment variable at the time
of `settings` module import (or `SystemExit` raised with error message if it is
unset or empty in this case). Or hardcode your value (not for authentication
parameters, of course), but note that this directory will be under VCS
and will reside in *site-packages/settings* after package install.

This particular parameter does not require special preparations and pretended
to be used as-is, but for more complex/specific ones you can add some code
to corresponding submodule, `application` in this case, for initialization:

```python
# prepare configuration entries

configuration.security.secret = f"Bearer {configuration.security.secret}"
```

You can also add some `argparse` code to your entrypoint if you want to
provide this parameter as argument:

```python
import settings

parser = settings.Parser()  # `argparse.ArgumentParser` subclass


# security arguments

group = parser.add_argument_group("security")

group.add_argument(
    "--secret", dest="application.security.secret",
    help="API key for <some service>", type=lambda key: key.upper()
)

parser.parse()  # it's result will also reside in `settings.arguments`

# or call this if you don't want to set own arguments
# settings.Parser().parse()     # you MUST parse CLI arguments anyway
```
"""

import os
import re
import inspect
import logging
import pathlib
import pkgutil
import argparse
import functools

import ruamel.yaml

import utilities


class Namespace(utilities.Namespace):
    """
    Restores (almost) proper `hasattr` functionality for `argparse`.
    """

    def __getattr__(self, name):
        if super().__getattr__(name) == type(self)():
            raise AttributeError


class Parser(argparse.ArgumentParser):
    """
    Arguments parser with nested dotted-path namespace support.

    Also adds an argument for configuration root path unconditionally.

    Parameters
    ----------
    *args : list
        `argparse.ArgumentParser` positional arguments.
    **kwargs : dict
        `argparse.ArgumentParser` keyword arguments.
    """

    @functools.wraps(argparse.ArgumentParser.__init__)
    def __init__(self, *args, **kwargs):
        kwargs.update(argument_default=kwargs.get(
            "argument_default", Namespace()))
        super().__init__(*args, **kwargs)

        self.add_argument(
            "-c", "--config", dest="CONFIG_PATH", metavar="PATH", help=(
                "path to configuration directory (default: ./configuration)"
            ), default="./configuration", type=pathlib.Path
        )

    def parse(self):
        """
        Triggers arguments parsing and submodules import.

        Returns
        -------
        utilities.Namespace
            Parsed nested attributes tree. Also stored in *arguments*.
        """
        # parse arguments and save them into namespace
        arguments.update(utilities.Namespace(
            self.parse_args(namespace=Namespace())))
        # trigger submodules execution to parse configuration files
        __import__(__package__, globals(), locals(), [
            module for _, module, _ in pkgutil.walk_packages(__path__)]) # noqa
        # clean argparse stuff that must not exist in `parse_args` result
        arguments.unknown = arguments.pop("_unrecognized_args", dict())
        arguments.pop("help", None); return arguments   # noqa


class Configuration(utilities.Namespace):

    # matches environment variable reference with or without default value
    pattern = re.compile(r"(?<!\$)\$({)?(\w*)(?(1)([:?+-]+)?([^}]*))(?(1)})")

    def __morph__(self, object: object):
        if not isinstance(object, str):
            return super().__morph__(object)

        def resolve(match: re.Match) -> str:
            """
            https://wiki.bash-hackers.org/syntax/pe
            """
            if not match.group(3):  # name only or basic syntax
                return os.getenv(match.group(2), str())

            # use value only if unset
            elif match.group(3) == "-":
                return os.getenv(match.group(2), match.group(4))
            # use value if unset or empty
            elif match.group(3) == ":-":
                return os.getenv(match.group(2)) or match.group(4)

            # exit with error message only if unset
            elif match.group(3) == "?" and match.group(2) not in os.environ:
                raise SystemExit(f"{match.group(2)}: {match.group(4)}")
            # exit with error message if unset or empty
            elif match.group(3) == ":?" and not os.getenv(match.group(2)):
                raise SystemExit(f"{match.group(2)}: {match.group(4)}")

            # use alternate value only if set
            elif match.group(3) == "+":
                return match.group(4) if match.group(2) in os.environ else None
            # use alternate value if set and not empty
            elif match.group(3) == ":+":
                return match.group(4) if os.getenv(match.group(2)) else None

            else:
                raise SystemExit(f"invalid interpolation: {match.group(0)}")

        return re.sub(self.pattern, resolve, object)


def load(filename: str):

    # read default configuration first
    configuration = Configuration(YAML.load(DEFAULTS_PATH/filename) or dict())

    # update it with user-provided config if any
    if arguments.CONFIG_PATH and (arguments.CONFIG_PATH/filename).exists():
        configuration.update(**utilities.Namespace(
            YAML.load(arguments.CONFIG_PATH/filename) or dict()))

    # finally update it with command-line arguments if any
    if hasattr(arguments, filename.split(".")[0]):
        configuration.update(**getattr(arguments, filename.split(".")[0]))

    return configuration


def validate(*patterns: set, logger: bool = True) -> None:
    """
    Run all validators registered by `validator`-decorated functions calls.

    Parameters
    ----------
    *patterns : set
        Run only validators which fully qualified names ends with any pattern.
    logger : bool
        Should validators failures be logged (the default is True).
        You can set custom logger here, and it will be used instead of new
        one created, but note that  `name` and `lineno` properties will be
        replaced in validator's log records with module and line where
        validator was applied.

    Raises
    -------
    SystemExit
        One of the failed validators have positive exit code.
        Exit code will be maximum across all failed validators.
    """

    def extrarecord(
        self, name, level, fn, lno, msg, args,
        exc_info, func=None, extra=None, sinfo=None
    ) -> logging.LogRecord:
        rv = logging.LogRecord(
            name, level, fn, lno, msg, args, exc_info, func, sinfo)
        if extra is not None:
            rv.__dict__.update(extra)
        return rv

    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(__name__) if logger else None

    validate.validators = getattr(validate, "validators", set())

    validators = validate.validators if not patterns else {
        validator for validator in validate.validators if any(
            validator.name.endswith(pattern) for pattern in patterns
        )
    }

    errors = dict()

    for validator in validators:
        try:
            errors[validator] = validator()
        except Exception as ಠ_ಠ:
            errors[validator] = ಠ_ಠ
        if errors[validator] is None:
            errors.pop(validator)

    if logger is not None:

        logger.makeRecord, makeRecord = functools.partial(
            extrarecord, logger), logger.makeRecord

        try:
            for validator, ಠ_ಠ in errors.items():
                logger.log(validator.level, ಠ_ಠ, extra=validator.extra)
        except Exception:
            logger.exception("unhandled logging exception")
        finally:
            logger.makeRecord = makeRecord

    if any(validator.exit for validator in errors.keys()):
        raise SystemExit(max(validator.exit for validator in errors.keys()))


def validator(function=None, /, *, level: str = "ERROR", exit: int = 1):
    """
    Decorator that turns wrapped function into deferred validator.

    Calling that function later will return it's first argument as is, without
    wrapped function execution, and adds this invocation with all arguments to
    set of registered validators using `functools.partial`. Actual validation
    will occur at `validate` method invocation. Validation is threated as
    failed if validator raises or returns anything besides None. Return value
    or message of raised exception will be logged with chosen severity level.

    Parameters
    ----------
    level : str
        Validator failure logging severity (the default is "ERROR").
        Any value will be implicitly converted to uppercase string.
        Falling back to default if is not a valid logging level.
    exit : int
        Code to exit with at validator failure (the default is 1).
        Set it to non-positive value to prevent `SystemExit`.
        Exit with zero code (success) is not allowed.

    Examples
    -------
    >>> import pathlib
    >>> @validator(level="WARNING", exit=0)
    ... def mustexist(path: pathlib.Path, regular: bool = False):
    ...     assert path.exists(), f"{path} does not exist"
    ...     if regular:
    ...         assert path.is_file(), f"{path} is not a regular file"
    >>> path = mustexist(pathlib.Path("somepath"), regular=True)
    """

    def decorator(function):

        @functools.wraps(function)
        def wrapper(parameter, *args, **kwargs):
            validate.validators = getattr(validate, "validators", set())

            validator = functools.partial(function, parameter, *args, **kwargs)

            validator.exit, validator.level = \
                exit, getattr(logging, str(level).upper(), 40)
            validator.name = function.__name__

            validator.extra = dict(
                funcName=function.__name__,
                name=inspect.getmodule(inspect.stack()[1][0]).__name__,
                lineno=inspect.getframeinfo(inspect.stack()[1][0]).lineno,
                pathname=inspect.getmodule(inspect.stack()[1][0]).__file__
            )   # <== log record attrbutes taken from where validator applied

            validate.validators.add(validator)

            return parameter

        return wrapper

    return decorator if function is None else decorator(function)


# CLI arguments holder
arguments = utilities.Namespace()

YAML = ruamel.yaml.YAML(typ="safe")

# default/fallback configuration path
DEFAULTS_PATH = pathlib.Path(__file__).parent/"defaults"
