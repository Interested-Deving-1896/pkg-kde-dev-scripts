from __future__ import annotations
import glob
import logging
import os
import tempfile
import json

log = logging.getLogger(__name__)

class atomic_writer(object):
    """
    Atomically write to a file
    """
    def __init__(self, fname, mode="w+b", chmod=0o664, sync=True, **kw):
        self.fname = fname
        self.chmod = chmod
        self.sync = sync
        dirname = os.path.dirname(self.fname)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        self.fd, self.abspath = tempfile.mkstemp(dir=dirname, text="b" not in mode)
        self.outfd = open(self.fd, mode, closefd=True, **kw)

    def __enter__(self):
        return self.outfd

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.outfd.flush()
            if self.sync:
                os.fdatasync(self.fd)
            os.fchmod(self.fd, self.chmod)
            os.rename(self.abspath, self.fname)
        else:
            os.unlink(self.abspath)
        self.outfd.close()
        return False


class Workdir:
    """
    Quick access to loading and saving json files in a directory.

    In trendy words, this is an efficient transactional and structured
    key-value store implemented in 10 lines of python.
    """
    def __init__(self, path: str, cache=False):
        self.root = path
        self.enable_cache = cache
        self._cache = {}
        os.makedirs(self.root, exist_ok=True)

    def has(self, name):
        """
        Return True if we have a value for the given name
        """
        if self.enable_cache and name in self._cache:
            return True
        else:
            return os.path.exists(os.path.join(self.root, name + ".json"))

    def set(self, name, data):
        """
        Save json data with the given name
        """
        with atomic_writer(os.path.join(self.root, name + ".json"), mode="wt") as fd:
            json.dump(data, fd)
        if self.enable_cache:
            self._cache[name] = data

    def get(self, name, default=None) -> Any:
        """
        Load json data with the given name
        """
        try:
            if self.enable_cache and name in self._cache:
                return self._cache[name]
            with open(os.path.join(self.root, name + ".json"), mode="rt") as fd:
                data = json.load(fd)
            if self.enable_cache:
                self._cache[name] = data
            return data
        except FileNotFoundError:
            return default

    def elements(self):
        """
        Returns a generator of all elements in the workdir.
        """
        for i in glob.iglob(os.path.join(self.root,"*.json")):
                name = os.path.splitext(os.path.basename(i))[0]
                yield name, self.get(name)


