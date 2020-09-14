import logging
import logging.config

import settings


def application():

    # Define entrypoint-specific CLI arguments and parse them

    parser.prog, parser.description = "application", "Application description"

    # configure logging subsystem

    logging.config.dictConfig(settings.application.logging)

    logger = logging.getLogger(f"{__package__}.application")

    # run registered validators for configuration parameters

    settings.validate()

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    logger.info("application started successfully")


parser = settings.Parser(
    epilog="command-line options will take precedence over configuration files"
)

group = parser.add_argument_group("logging")

group.add_argument(
    "--log-level", dest="application.logging.level", choices=[
        'CRITICAL', 'FATAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'
    ], metavar="LEVEL", type=str.upper, help="logger verbosity level"
)

parser.parse()
# settings.Parser().parse()
