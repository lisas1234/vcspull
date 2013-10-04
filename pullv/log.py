#!/usr/bin/env python
#
# Copyright 2012 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Logging support for Tornado.

Tornado uses three logger streams:

* ``tornado.access``: Per-request logging for Tornado's HTTP servers (and
  potentially other servers in the future)
* ``tornado.application``: Logging of errors from application code (i.e.
  uncaught exceptions from callbacks)
* ``tornado.general``: General-purpose logging, including any errors
  or warnings from Tornado itself.

These streams may be configured independently using the standard library's
`logging` module.  For example, you may wish to send ``tornado.access`` logs
to a separate file for analysis.
"""
from __future__ import absolute_import, division, print_function, with_statement

import logging
import logging.handlers
import sys
import time

#from tornado.escape import _unicode
#from tornado.util import unicode_type, basestring_type

try:
    import curses
except ImportError:
    curses = None


# From tornado/util.py:
# Fake unicode literal support:  Python 3.2 doesn't have the u'' marker for
# literal strings, and alternative solutions like "from __future__ import
# unicode_literals" have other problems (see PEP 414).  u() can be applied
# to ascii strings that include \u escapes (but they must not contain
# literal non-ascii characters).
if type('') is not type(b''):
    def u(s):
        return s
    bytes_type = bytes
    unicode_type = str
    basestring_type = str
else:
    def u(s):
        return s.decode('unicode_escape')
    bytes_type = str
    unicode_type = unicode
    basestring_type = basestring


_UTF8_TYPES = (bytes_type, type(None))
_TO_UNICODE_TYPES = (unicode_type, type(None))


def utf8(value):
    """Converts a string argument to a byte string.

    If the argument is already a byte string or None, it is returned unchanged.
    Otherwise it must be a unicode string and is encoded as utf8.
    """
    if isinstance(value, _UTF8_TYPES):
        return value
    assert isinstance(value, unicode_type), \
        "Expected bytes, unicode, or None; got %r" % type(value)
    return value.encode("utf-8")


def to_unicode(value):
    """Converts a string argument to a unicode string.

    If the argument is already a unicode string or None, it is returned
    unchanged.  Otherwise it must be a byte string and is decoded as utf8.
    """
    if isinstance(value, _TO_UNICODE_TYPES):
        return value
    assert isinstance(value, bytes_type), \
        "Expected bytes, unicode, or None; got %r" % type(value)
    return value.decode("utf-8")

# to_unicode was previously named _unicode not because it was private,
# but to avoid conflicts with the built-in unicode() function/type
_unicode = to_unicode

# When dealing with the standard library across python 2 and 3 it is
# sometimes useful to have a direct conversion to the native string type
if str is unicode_type:
    native_str = to_unicode
else:
    native_str = utf8

# Logger objects for internal tornado use
access_log = logging.getLogger("tornado.access")
app_log = logging.getLogger("tornado.application")
gen_log = logging.getLogger("tornado.general")


def _stderr_supports_color():
    color = False
    if curses and sys.stderr.isatty():
        try:
            curses.setupterm()
            if curses.tigetnum("colors") > 0:
                color = True
        except Exception:
            pass
    return color


class LogFormatter(logging.Formatter):
    """Log formatter used in Tornado.

    Key features of this formatter are:

    * Color support when logging to a terminal that supports it.
    * Timestamps on every log line.
    * Robust against str/bytes encoding problems.

    This formatter is enabled automatically by
    `tornado.options.parse_command_line` (unless ``--logging=none`` is
    used).
    """
    def __init__(self, color=True, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)
        self._color = color and _stderr_supports_color()
        if self._color:
            # The curses module has some str/bytes confusion in
            # python3.  Until version 3.2.3, most methods return
            # bytes, but only accept strings.  In addition, we want to
            # output these strings with the logging module, which
            # works with unicode strings.  The explicit calls to
            # unicode() below are harmless in python2 but will do the
            # right conversion in python 3.
            fg_color = (curses.tigetstr("setaf") or
                        curses.tigetstr("setf") or "")
            if (3, 0) < sys.version_info < (3, 2, 3):
                fg_color = unicode_type(fg_color, "ascii")
            self._colors = {
                logging.DEBUG: unicode_type(curses.tparm(fg_color, 4),  # Blue
                                            "ascii"),
                logging.INFO: unicode_type(curses.tparm(fg_color, 2),  # Green
                                           "ascii"),
                logging.WARNING: unicode_type(curses.tparm(fg_color, 3),  # Yellow
                                              "ascii"),
                logging.ERROR: unicode_type(curses.tparm(fg_color, 1),  # Red
                                            "ascii"),
            }
            self._normal = unicode_type(curses.tigetstr("sgr0"), "ascii")

    def format(self, record):
        try:
            record.message = record.getMessage()
        except Exception as e:
            record.message = "Bad message (%r): %r" % (e, record.__dict__)
        assert isinstance(record.message, basestring_type)  # guaranteed by logging
        record.asctime = time.strftime(
            "%y%m%d %H:%M:%S", self.converter(record.created))
        prefix = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]' % \
            record.__dict__

        # temporary, look up howto logging channels
        if 'repo_vcs' in record.__dict__:
            prefix = '[{0}]({1})'.format(record.repo_name, record.repo_vcs)

        if self._color:
            prefix = (self._colors.get(record.levelno, self._normal) +
                      prefix + self._normal)

        # Encoding notes:  The logging module prefers to work with character
        # strings, but only enforces that log messages are instances of
        # basestring.  In python 2, non-ascii bytestrings will make
        # their way through the logging framework until they blow up with
        # an unhelpful decoding error (with this formatter it happens
        # when we attach the prefix, but there are other opportunities for
        # exceptions further along in the framework).
        #
        # If a byte string makes it this far, convert it to unicode to
        # ensure it will make it out to the logs.  Use repr() as a fallback
        # to ensure that all byte strings can be converted successfully,
        # but don't do it by default so we don't add extra quotes to ascii
        # bytestrings.  This is a bit of a hacky place to do this, but
        # it's worth it since the encoding errors that would otherwise
        # result are so useless (and tornado is fond of using utf8-encoded
        # byte strings whereever possible).
        def safe_unicode(s):
            try:
                return _unicode(s)
            except UnicodeDecodeError:
                return repr(s)

        formatted = prefix + " " + safe_unicode(record.message)
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            # exc_text contains multiple lines.  We need to safe_unicode
            # each line separately so that non-utf8 bytes don't cause
            # all the newlines to turn into '\n'.
            lines = [formatted.rstrip()]
            lines.extend(safe_unicode(ln) for ln in record.exc_text.split('\n'))
            formatted = '\n'.join(lines)
        return formatted.replace("\n", "\n    ")


def enable_pretty_logging(options=None, logger=None):
    """Turns on formatted logging output as configured.

    This is called automaticaly by `tornado.options.parse_command_line`
    and `tornado.options.parse_config_file`.
    """
    if logger is None:
        logger = logging.getLogger()
    logger.setLevel('INFO')

    channel = logging.StreamHandler()
    channel.setFormatter(LogFormatter())
    logger.addHandler(channel)


def define_logging_options(options=None):
    options.define("logging", default="info",
                   help=("Set the Python log level. If 'none', tornado won't touch the "
                         "logging configuration."),
                   metavar="debug|info|warning|error|none")
    options.define("log_to_stderr", type=bool, default=None,
                   help=("Send log output to stderr (colorized if possible). "
                         "By default use stderr if --log_file_prefix is not set and "
                         "no other logging is configured."))
    options.define("log_file_prefix", type=str, default=None, metavar="PATH",
                   help=("Path prefix for log files. "
                         "Note that if you are running multiple tornado processes, "
                         "log_file_prefix must be different for each of them (e.g. "
                         "include the port number)"))
    options.define("log_file_max_size", type=int, default=100 * 1000 * 1000,
                   help="max size of log files before rollover")
    options.define("log_file_num_backups", type=int, default=10,
                   help="number of log files to keep")

    options.add_parse_callback(enable_pretty_logging)