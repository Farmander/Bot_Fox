# -*- coding: utf-8 -*-
"""Restore the entire original project, including credentials and databases.
Install dependency: py -3.11 -m pip install pyzipper==0.3.6
Run: py -3.11 restore_project.py
The archive password is entered privately at the prompt, never saved in Git.
"""
import argparse
import getpass
import hashlib
import io
from pathlib import Path, PurePosixPath
import sys
import zipfile

EXPECTED_SHA256 = 'ae5c26394315bcea7dd3fd2467609c22d198c5c3a8d36e2e95a78eedabfdc1b4'

def main():
    try:
        import pyzipper
    except ImportError:
        raise SystemExit('Install the dependency first: py -3.11 -m pip install pyzipper==0.3.6')
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=root / 'restored')
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination.exists():
        raise SystemExit('Output directory already exists. Choose a NEW path with --output-dir.')
    if sys.stdin.isatty():
        password = getpass.getpass('Archive password from the chat: ')
    else:
        password = sys.stdin.readline().rstrip('\r\n')
    try:
        with pyzipper.AESZipFile(root / 'Bot_Fox_download.zip') as protected:
            protected.setpassword(password.encode('utf-8'))
            data = protected.read('Bot_Fox_updated.zip')
    except RuntimeError:
        raise SystemExit('Incorrect archive password.')
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise SystemExit('Archive integrity check failed.')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() is not None:
            raise SystemExit('Archive is damaged.')
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in member.filename or ':' in member.filename:
                raise SystemExit('Unsafe archive path.')
        destination.mkdir(parents=True, exist_ok=False)
        archive.extractall(destination)
    print('Complete project restored:', destination / 'Bot_Fox_updated')
    print('All original credential files and databases are included.')
    print('Read README_RU.md to install and run the bot.')

if __name__ == '__main__':
    main()
