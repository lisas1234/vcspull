# -*- coding: utf8 - *-
"""CLI utilities for pullv.

pullv.cli
~~~~~~~~~
:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from __future__ import absolute_import, division, print_function, with_statement

import logging
import os
import sys
import kaptan
import argparse
import argcomplete
from . import log
from . import util
from .repo import Repo
logger = logging.getLogger(__name__)

config_dir = os.path.expanduser('~/.pullv/')
cwd_dir = os.getcwd() + '/'



def setup_logger(logger=None, level='INFO'):
    """Setup logging for CLI use.

    :param logger: instance of logger
    :type logger: :py:class:`Logger`

    """
    if not logger:
        logger = logging.getLogger()
    if not logger.handlers:
        channel = logging.StreamHandler()
        channel.setFormatter(log.DebugLogFormatter())

        # channel.setFormatter(log.LogFormatter())
        logger.setLevel(level)
        logger.addHandler(channel)


def get_parser():
    """Return :py:class:`argparse.ArgumentParser` instance for CLI."""

    main_parser = argparse.ArgumentParser(add_help=False)

    main_parser.add_argument(
        dest='config',
        type=str,
        nargs='+',
        help='List config available in working directory and config folder.'
    ).completer = ConfigFileCompleter(
        allowednames=('.yaml', '.json'), directories=False
    )
    main_parser.set_defaults(callback=command_load)

    return main_parser

def main():
    """Main CLI application."""

    parser = get_parser()

    argcomplete.autocomplete(parser, always_complete_options=False)

    args = parser.parse_args()

    setup_logger(level=args.log_level.upper() if 'log_level' in args else 'INFO')

    if args.callback is command_load:
        command_load(args)
    else:
        parser.print_help()

def command_load(args):

    if args.config:
        yaml_config = os.path.expanduser('~/.pullv.yaml')
        has_yaml_config = os.path.exists(yaml_config)
        json_config = os.path.expanduser('~/.pullv.json')
        has_json_config = os.path.exists(json_config)
        if not has_yaml_config and not has_json_config:
            logger.fatal('No config file found. Create a .pullv.{yaml,conf}'
                        ' in your $HOME directory. http://pullv.rtfd.org for a'
                        ' quickstart.')
        else:
            if sum(filter(None, [has_json_config, has_yaml_config])) > int(1):
                sys.exit(
                    'multiple configs found in home directory use only one.'
                    ' .yaml, .json.'
                )
            elif has_yaml_config:
                config_file = yaml_config
            elif has_json_config:
                config_file = json_config

            config = kaptan.Kaptan()
            config.import_config(config_file)

            logging.debug('%r' % config.get())
            logging.debug('%r' % util.expand_config(config.get()))
            logging.debug('%r' % util.get_repos(util.expand_config(config.get())))

            for repo_dict in util.get_repos(util.expand_config(config.get())):
                r = Repo(repo_dict)
                logger.debug('%s' % r)
                r.update_repo()


class ConfigFileCompleter(argcomplete.completers.FilesCompleter):

    """argcomplete completer for tmuxp files."""

    def __call__(self, prefix, **kwargs):

        completion = argcomplete.completers.FilesCompleter.__call__(
            self, prefix, **kwargs
        )

        completion += [os.path.join(config_dir, c)
                       for c in in_dir(config_dir)]

        return completion


def in_dir(
    config_dir=os.path.expanduser('~/.pullv'),
    extensions=['.yml', '.yaml', '.json']
):
    """Return a list of configs in ``config_dir``.

    :param config_dir: directory to search
    :type config_dir: string
    :param extensions: filetypes to check (e.g. ``['.yaml', '.json']``).
    :type extensions: list
    :rtype: list

    """
    configs = []

    for filename in os.listdir(config_dir):
        if is_config_file(filename, extensions) and \
           not filename.startswith('.'):
            configs.append(filename)

    return configs

def is_config_file(filename, extensions=['.yml', '.yaml', '.json']):
    """Return True if file has a valid config file type.

    :param filename: filename to check (e.g. ``mysession.json``).
    :type filename: string
    :param extensions: filetypes to check (e.g. ``['.yaml', '.json']``).
    :type extensions: list or string
    :rtype: bool

    """

    extensions = [extensions] if isinstance(
        extensions, basestring) else extensions
    return any(filename.endswith(e) for e in extensions)
