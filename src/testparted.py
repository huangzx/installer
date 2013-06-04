#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       partmod.py
#       
#       Copyright 2010 wkt <weikting@gmail.com>
#       

import os
import sys

import parted
from _ped import DiskLabelException


def size2str(size):
    k=1024
    m=1024*k
    g=1024*m
    t=1024*g
    s = ""
    if size >= t:
        s = "%.2lf T" % (size*1.0/t)
    elif size >= g:
        s = "%.2lf G" % (size*1.0/g)
    elif size >= m:
        s = "%.2lf M" % (size*1.0/m)
    elif size >= k:
        s = "%.0lf K" % (size*1.0/k)
    else:
        s = "%d B" %(int(size))
    return s

def show_device(device):
    disk = parted.Disk(device)
    part = disk.getFirstPartition()
    print device
    print "%-12s  %8s  %16s  %16s  %16s  %8s" %("Path","Fstype","Start","End","Length","Size")
    while part != None:
        geom = part.geometry
        if part.fileSystem:
            fstype = part.fileSystem.type
            if fstype.startswith("linux-swap"):
                fstype = "swap"
        else:
            fstype = "None"
        print "%-12s  %8s  %16d  %16d  %16d  %8s" %(part.path,fstype,geom.start,geom.end,geom.length,size2str(part.getSize(unit='b')))
        part = part.nextPartition()

devs = parted.getAllDevices()
for d in devs:
    show_device(d)
