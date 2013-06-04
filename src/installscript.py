#!/usr/bin/env python
# installscript.py
# Python module for osinstaller.
#
# Copyright (C) 2010 Ylmf, Inc.
#
#
# Ylmf Author(s): wkt <weikting@gmail.com>
#               
#

import os
import sys
import time

from misc import *

class InstallScript(GOBjectThreadMod):

    __gsignals__ = {"umount-error": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,(gobject.TYPE_STRING,))}

    def __init__(self,insenv=None,mountm=None):
        super(InstallScript,self).__init__()
        self.mountm = mountm
        self.insenv = insenv
        self.boot_device = None
        self.boot_partition = None
        self.__error_block = False
        self.__error_reply = 'ignore'
        self.connect('umount-error',self._on_umount_error)
        self.umount_error_func=None

    def _on_umount_error(self,object,msg):
        if self.umount_error_func:
            self.__error_reply = self.umount_error_func(msg)
        else:
            self.__error_reply = 'ignore'
        self.__error_block = False

    def _run(self):
        pass

    def run(self):
        self._run()

    def set_mplist(self,mplist):
        self.mountm.set_mplist(mplist)

    def umount_all(self):
        retry = True
        self.__error_reply = "ignore"
        while retry:
            error_out = self.mountm.umount_all()
            err_msg = ""
            for (sts,mdir,dev) in error_out:
                err_msg += _('Umount "%s" on "%s" failed,error code:%d\n') % (mdir,dev,sts)
            if len(err_msg)>1:
                self.__error_block = True
                self.emit_signal("umount-error",err_msg)
            while self.__error_block:
                time.sleep(0.1)
            if self.__error_reply == 'ignore':
                retry = False
            elif self.__error_reply == 'retry':
                retry = True
            else:
                raise AbortException(_("Abort Installation !"))
                retry = False

    def swap_off(self):
        retry = True
        self.__error_reply = "ignore"
        while retry:
            error_out = self.mountm.swap_off()
            err_msg = ""
            for (sts,dev) in error_out:
                err_msg += _('Umount "%s" on "%s" failed,error code:%d\n') % (dev,'swap',sts)
            if len(err_msg)>1:
                self.__error_block = True
                self.emit_signal("umount-error",err_msg)
            else:
                break
            while self.__error_block:
                time.sleep(0.1)
            if self.__error_reply == 'ignore':
                retry = False
            elif self.__error_reply == 'retry':
                retry = True
            elif self.__error_reply == 'abort':
                retry = False
                raise AbortException(_("Abort Installation !"))
            else:
                retry = False

    def preinstall(self):
        steps = 2
        self.emit_signal("progress",0.0/steps,_('Mounting targets ...'))
        self.mountm.mount_target()
        self.emit_signal("progress",1.0/steps,_('Targets mounted'))

        self.emit_signal("progress",1.1/steps,_('Running preinstall script ...'))
        prefile=self.insenv.datadir+'/pre_install'
        if os.path.isfile(prefile):
            cmd_output_log(prefile)
        self.emit_signal("progress",2.0/steps,_('Preinstall done'))

    def mount_procfs(self):
        self.emit_signal("progress",0,_('Mounting procfs ...'))
        self.mountm.mount_procfs()
        self.emit_signal("progress",1.0,_('Procfs mounted'))

    def postinstall(self):

        steps = 3.0
        cn = 0.0
        self.emit_signal("progress",cn/steps,_('Writing /etc/fstab ...'))
        self.mountm.write_etc_fstab()
        cn += 0.5
        self.emit_signal("progress",cn/steps,_('/etc/fstab Written'))

        grub_to=[]
        if self.boot_device:
            grub_to.append(self.boot_device)

        if self.boot_partition:
            grub_to.append(self.boot_partition)
        cn += 0.5
        grub_text = _('Bootloader installed')
        if len(grub_to) >0:
            self.emit_signal("progress",cn/steps,_('Installing grub bootloader ...'))
            grub_install(grub_to,self.insenv)
        else:
            grub_text = _('Bootloader is not installed')
        cn += 1.0
        self.emit_signal("progress",cn/steps,grub_text)

        self.emit_signal("progress",cn/steps,_('Running postinstall script ...'))
        postfile = self.insenv.datadir+'/post_install'
        if os.path.isfile(postfile):
            cmd_output_log(postfile)
        cn = 3.0
        self.emit_signal("progress",cn/steps,_('Postinstall done'))


    def setboot(self,dev_file):
        self.boot_device = dev_file

class PreInstall(InstallScript):

    def __init__(self,insenv=None,mountm=None):
        super(PreInstall,self).__init__(insenv,mountm)

    def _run(self):
        res = True
        self.emit_signal("started")
        try:
            self.preinstall()
        except:
            res = False
            self.emit_signal('error',error_msg(),exception_msg())
        self._res_state = res
        self.emit_signal('finished',res)

class MountProcfs(InstallScript):

    def __init__(self,insenv=None,mountm=None):
        super(MountProcfs,self).__init__(insenv,mountm)

    def _run(self):
        res = True
        self.emit_signal("started")
        try:
            self.mount_procfs()
        except:
            res = False
            self.emit_signal('error',error_msg(),exception_msg())
        self._res_state = res
        self.emit_signal('finished',res)


class PostInstall(InstallScript):

    def __init__(self,insenv=None,mountm=None):
        super(PostInstall,self).__init__(insenv,mountm)

    def _run(self):
        res = True
        self.emit_signal("started")
        try:
            self.postinstall()
        except:
            res = False
            self.emit_signal('error',error_msg(),exception_msg())
        self._res_state = res
        self.emit_signal('finished',res)

class UmountInstall(InstallScript):

    def __init__(self,insenv=None,mountm=None):
        super(UmountInstall,self).__init__(insenv,mountm)

    def _run(self):
        res = True
        self.emit_signal("started")
        try:
            self.emit_signal("progress",0.0,_('Umounting filesystems ...'))
            self.emit_signal("progress",0.0,_('Deactive swaps ...'))
            self.swap_off()
            self.emit_signal("progress",0.5,_('swapoff done.'))
            self.emit_signal("progress",0.5,_('Umounting ...'))
            self.umount_all()
            self.emit_signal("progress",1.0,_('Umounting done.'))
        except AbortException:
            res = False
            self.emit_signal("abort",error_msg())
        except:
            res = False
            self.emit_signal('error',error_msg(),exception_msg())
        self._res_state = res
        self.emit_signal('finished',res)

if '__main__' == __name__:
    import glib
    glib.threads_init()
    def test1():
        umi = UmountInstall()
        umi.go()
    
    test1()
    
