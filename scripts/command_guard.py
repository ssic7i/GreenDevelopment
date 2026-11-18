# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Recognize a small read-only shell subset before the conservative guard.

This is not a shell interpreter or a security sandbox. Unknown syntax and
execution-capable options receive no exemption from the existing guard.
"""
from pathlib import PurePosixPath
import re
import shlex


def _read_segments(text):
    """Split reader chains while preserving quoted and escaped data."""
    segments = []
    start = index = 0
    quote = None
    while index < len(text):
        char = text[index]
        if char == '\\' and quote != "'":
            index += 2
            continue
        if quote:
            if char == quote:
                quote = None
            elif quote == '"' and char in '$`':
                return None
        elif char in "'\"":
            quote = char
        elif char in '$`()<>#{}*?[]':
            return None
        elif char in ';&|\n':
            separator = char
            if char in '&|' and text[index:index + 2] == char * 2:
                separator *= 2
            if separator == '&':
                return None
            segment = text[start:index].strip()
            if segment:
                segments.append(segment)
            elif char != '\n':
                return None
            index += len(separator)
            start = index
            if separator in ('&&', '||', '|') and not text[index:].strip():
                return None
            continue
        index += 1
    if quote:
        return None
    if text[start:].strip():
        segments.append(text[start:].strip())
    return segments


def _reader(argv):
    if not argv:
        return False
    name = PurePosixPath(argv[0]).name
    args = argv[1:]
    if name in ('cat', 'head', 'tail', 'wc', 'ls', 'stat', 'grep'):
        return True
    if name == 'rg':
        options = iter(args)
        for arg in options:
            if arg == '--':
                break
            if arg in ('-e', '--regexp', '-f', '--file', '-g', '--glob', '--iglob'):
                next(options, None)  # Pattern/file values are data, not options.
            elif arg.split('=', 1)[0] in ('--pre', '--hostname-bin'):
                return False
            elif arg.startswith('-'):
                known_flag = arg in ('--files', '--hidden', '--no-ignore', '--no-config',
                                     '--line-number', '--ignore-case', '--fixed-strings')
                short_flags = bool(re.fullmatch(r'-[nilLvwxFUusSqcoHh0zaINbPp]+', arg))
                if not known_flag and not short_flags:
                    # Unknown options may consume later flags as values and
                    # change their meaning. Do not guess an argument grammar.
                    return False
        return True
    if name == 'git':
        if args[:1] == ['--no-pager']:
            args = args[1:]
        return bool(args and args[0] in ('diff', 'show', 'log', 'status', 'ls-files', 'grep')
                    and not any(arg.split('=', 1)[0] in ('-c', '--config-env', '--ext-diff', '--textconv', '--output', '--open-files-in-pager')
                                or (args[0] == 'grep' and arg.startswith('-O'))
                                for arg in args[1:]))
    if name == 'find':
        return not any(arg in ('-exec', '-execdir', '-ok', '-okdir', '-delete', '-fprint', '-fprint0', '-fprintf', '-fls') for arg in args)
    if name == 'sed' and args[:1] == ['-n']:
        args = args[1:]
        if args[:1] == ['-e']:
            args = args[1:]
        if not args or not all(re.fullmatch(r'(?:(?:\d+|\$)(?:,(?:\d+|\$))?)?p', part.strip())
                               for part in args[0].split(';')):
            return False
        files = args[1:]
        if files[:1] == ['--']:
            files = files[1:]
        return all(not value.startswith('-') or value == '-' for value in files)
    return False


def is_read_only_shell(text):
    segments = _read_segments(text)
    if not segments:
        return False
    try:
        return all(_reader(shlex.split(segment)) for segment in segments)
    except ValueError:
        return False
