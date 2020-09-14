import pathlib

import settings


# load configuration; already expanded with user config and arguments
configuration = settings.load(f"{pathlib.Path(__file__).stem}.yaml")


# prepare configuration entries

configuration.logging.level = configuration.logging.level or "NOTSET"

configuration.logging.update({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "message": {
            "style": configuration.logging.style or "{", "format": bytes(
                configuration.logging.format.message or (
                    "\033[1;94m{asctime:s}.{msecs:0<3.0f}\033[0m "
                    "\033[1;91m{levelname}\033[0m "
                    "\033[95m{name}:{lineno}\033[0m {message}"
                ), "utf-8").decode("unicode_escape"), "datefmt": (
                    configuration.logging.format.date or "%Y-%m-%d %H:%M:%S"
            )
        }
    }, "handlers": {
        "CRITICAL": {
            "level": "CRITICAL",
            "formatter": "message",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }, "FATAL": {
            "level": "FATAL",
            "formatter": "message",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }, "ERROR": {
            "level": "ERROR",
            "formatter": "message",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }, "WARNING": {
            "level": "WARNING",
            "formatter": "message",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }, "INFO": {
            "level": "INFO",
            "formatter": "message",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }, "DEBUG": {
            "level": "DEBUG",
            "formatter": "message",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }, "NOTSET": {
            "level": "NOTSET",
            "formatter": "message",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        },
    }, "loggers": {
        "": {   # root logger
            "propagate": False,
            "level": configuration.logging.level,
            "handlers": [configuration.logging.level]
        }
    }
})


# set entries as module variables in order to make them
# importable and accessible using dotted-path notation

globals().update(globals().pop("configuration"))
