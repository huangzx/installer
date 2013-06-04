# installerenv.py
# Python module for osinstaller.
#
# Copyright (C) 2010 Ylmf, Inc.
#
#
# Ylmf Author(s): wkt <weikting@gmail.com>
#               
#

import sys
import os
import gettext


class InstallerEnv:
    _source='/rofs'

    _target='/target'

    _datadir='/usr/share/osinstaller'

    _confdir='/usr/etc/osinstaller'

    _installer_version='0.9'

    _pkgname="osinstaller"

    _localedir='/usr/share/locale'

    _optical_dirs = []

    def __init__(self):
        self._use_wubi = False

    @property
    def installer_version(self):
        return self._installer_version

    @property
    def version(self):
        return self.installer_version

    @property
    def pkgname(self):
        return self._pkgname

    @property
    def localedir(self):
        return self._localedir

    @property
    def datadir(self):
        return self._datadir

    @property
    def confdir(self):
        return self._confdir

    @property
    def target(self):
        return self._target

    @property
    def source(self):
        return self._source

    def set_usewubi(self,use_wubi):
        self._use_wubi = use_wubi

    @property
    def use_wubi(self):
        return self._use_wubi

    def _get_is_desktop(self):
        if self.use_wubi:
            return False
        if hasattr(self,'_is_desktop'):
            return self._is_desktop
        s = os.getenv('IS_DESKTOP')
        if s != None and len(s) > 0:
            if s == '1':
                return True
            else:
                return False
        ret = True
        r = None
        try:
            r = open('/proc/cmdline')
            for l in r:
                if ('install-automatic' in l) or ('install-nodesktop' in l):
                    ret = False
                    break
        except:
            pass
        finally:
            if r:
                r.close()
        self.is_desktop = ret
        return ret

    def _set_is_desktop(self,is_desktop):
        self._is_desktop = is_desktop

    is_desktop = property(_get_is_desktop,_set_is_desktop)

    def is_yinst(self):
        ret = False
        r = None
        try:
            r = open('/proc/cmdline')
            for l in r:
                if ("iso-scan/filename=" in l.lower()):
                    ret = True
                    break
        except:
            pass
        finally:
            if r:
                r.close()
        return ret;
