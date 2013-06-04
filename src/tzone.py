# -*- coding: utf-8; Mode: Python; indent-tabs-mode: nil; tab-width: 4 -*-
# tzone.py
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
import osenv

import osdata

class TZone:
    def __init__(self):
        self.tzone = "GMT"
        self.loadmap()

    def loadmap(self):
        self.tzmap = osdata.TZone
        #print self.tzmap

    def get_default_area(self):
        try:
            lg = os.environ['LANG'].split('.')[0]
        except:
            lg = "C"
        spv = lg.split('_')
        if len(spv) >1:
            cy=spv[1]
        else:
            cy=spv[0]
        return cy

    def get_tzone(self,country):
        ret = "GMT"
        if self.tzmap != None and self.tzmap != {}:
            try:
                ret = self.tzmap[country]
            except:
                pass
        return ret

    def set_tzone(self,tzone):
        self.tzone = tzone

    def install(self):
        try:
            w=open(osenv.target+'/etc/timezone','w')
            w.write(self.tzone)
            w.close()
        except:
            (e1,e2,e3)=sys.exc_info()
            print e2

        try:
            print 'set time zone to :'+self.tzone
            r = open(osenv.target+'/usr/share/zoneinfo/'+self.tzone)
            ss = r.read()
            r.close()
            w = open(osenv.target+'/etc/localtime','w')
            w.write(ss)
            w.close()
        except:
            (e1,e2,e3)=sys.exc_info()
            print e2

        try:
            s='TMPTIME=0\nSULOGIN=no\nDELAYLOGIN=no\nUTC=no\nVERBOSE=no\nFSCKFIX=no\n'
            w = open(osenv.target+'/etc/default/rcS','w')
            w.write(s)
            w.close()
        except:
            (e1,e2,e3)=sys.exc_info()
            print e2

