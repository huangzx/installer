#!/usr/bin/env python
# -*- coding: utf-8 -*-
# copyfilemod.py
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
import gobject
import time
try:
    import glib
except ImportError:
    import gobject as glib
import syslog
from hashlib import md5
import stat

from misc import *

import threading

class CopyFile(GOBjectThreadMod):

    __gsignals__ = {
                    "copy-error": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,(gobject.TYPE_STRING,)),
                    }

    def __init__(self,insenv=None):
        GOBjectThreadMod.__init__(self)
        self.blacklist = []
        self.cdrom_dir = None
        self.total_size = self.get_total_size()
        self.copy_size = 0
        self.can_copy = True
        self.is_copying = False
        self.is_blocking = False
        self.error_back = ""
        self._black_files = []
        self._black_dirs = []
        self._loop = None
        self._wait = True
        self._thread_exited = False
        self._can_cancel = True
        self._use_extract = False 
        self._extract_pid = 0

        self.copy_error_func = None
        self._can_set_proc_opts = True
        self.proc_opts= {'/proc/sys/vm/dirty_writeback_centisecs':{'new':"3000\n"},
                         '/proc/sys/vm/dirty_expire_centisec':{'new':'6000\n'}
                        }

        if insenv:
            self.target = insenv.target
            self.source= insenv.source
            self._blacklist  = insenv.datadir+'/blacklist'
        else:
            self.source = '/tmp/installer_test/tmproot'
            self.target = '/tmp/installer_test/tmptarget'
            self._blacklist = '/tmp/blacklist'

        if MountMod.installing_source:
            self.source = MountMod.installing_source

        self.connect("copy-error",self._on_copy_error)
        self.load_black_list()

    def _on_copy_error(self,object,msg):
        self.error_back = 'ignore'
        if self.copy_error_func:
            self.error_back = self.copy_error_func(object,msg)
        self.is_blocking = False

    def set_source(self,src_root):
        if self.is_copying:
            return
        self.source = src_root

    def set_target(self,target):
        if self.is_copying:
            return
        self.target = target

    def set_use_extract(self,extract):
        self._use_extract = extract

    ###modify from ubiquity
    def copy_file(self, sourcepath, targetpath, md5_check=True):
        sourcefh = None
        targetfh = None
        try:
            while self.can_copy:
                try:
                    os.unlink(targetpath)
                except:
                    pass
                sourcefh = open(sourcepath, 'rb')
                targetfh = open(targetpath, 'wb')
                if md5_check:
                    sourcehash = md5()
                while self.can_copy:
                    buf = sourcefh.read(16 * 1024)
                    if not buf:
                        break
                    targetfh.write(buf)
                    if md5_check:
                        sourcehash.update(buf)

                if not md5_check:
                    break
                targetfh.close()
                targetfh = open(targetpath, 'rb')
                if md5_check:
                    targethash = md5()
                while self.can_copy:
                    buf = targetfh.read(16 * 1024)
                    if not buf:
                        break
                    targethash.update(buf)
                if not self.can_copy:
                    break
                if targethash.digest() != sourcehash.digest():
                    if targetfh:
                        targetfh.close()
                    if sourcefh:
                        sourcefh.close()
                    self.is_blocking = True
                    self.emit_signal("copy-error",_('Failed to copy "%s"') % sourcepath)
                    while self.is_blocking:
                        time.sleep(0.5)
                    if self.error_back == 'abort':
                        raise CopyAbortException("Copying process aborted.")
                        break
                    elif self.error_back == 'ignore':
                        break
                    elif self.error_back == 'retry':
                        pass
                    else:
                        pass
                else:
                    break
        except CopyAbortException:
            try:
                os.unlink(targetpath)
            except:pass
            raise
        finally:
            if targetfh:
                targetfh.close()
            if sourcefh:
                sourcefh.close()

    def get_total_size(self,foreach=False):
        total_size = 0

        total_size = get_filesystem_size()
        if total_size > 1:
            return total_size;

        fs_dirs = MountMod.get_mounts(with_device=False)

        for fs_d in fs_dirs:
            fs_size = fs_d+'/casper/filesystem.size'
            self.cdrom_dir = fs_d
            if os.path.exists(fs_size):
                foreach=False
                break

        if foreach :
            for dirpath, dirnames, filenames in os.walk(self.source):
                if not self.can_copy :
                    break
                sp = dirpath[len(self.source) + 1:]
                for name in dirnames + filenames:
                    if not self.can_copy :
                        break
                    relpath = os.path.join(sp, name)
                    sourcepath = os.path.join(self.source, relpath)
                    st = os.lstat(sourcepath)
                    total_size += st.st_size
        else:
            try:
                r=open(fs_size)
                str=r.readline().strip()
                r.close()
            except:
                str='1'
            total_size = long(str)
        return total_size

    ###modify from ubiquity
    def do_copy(self):
        directory_times=[]
        if self.total_size < 2:
            self.total_size = self.get_total_size(foreach=True)
        for dirpath, dirnames, filenames in os.walk(self.source):
            if not self.can_copy :
                break
            sp = dirpath[len(self.source) + 1:]
            for name in dirnames + filenames:
                if not self.can_copy :
                    break
                relpath = os.path.join(sp, name)
                sourcepath = os.path.join(self.source, relpath)
                targetpath = os.path.join(self.target, relpath)
                st = os.lstat(sourcepath)
                mode = stat.S_IMODE(st.st_mode)
                try:
                    os.unlink(targetpath)
                except:
                    pass
                relpath = '/' + relpath
                if self.is_black(sourcepath):
                    log_msg('Not copying blacklist "%s"' % relpath)
                    continue
                text = _("Copying %s ...") % relpath
                self.emit_signal("progress",self.copy_size*1.0/self.total_size,text)
                if stat.S_ISLNK(st.st_mode):
                    linkto = os.readlink(sourcepath)
                    try:
                        os.symlink(linkto, targetpath)
                    except:
                        raise Exception(targetpath + '->' +linkto+':' + error_msg())
                elif stat.S_ISDIR(st.st_mode):
                    if not os.path.isdir(targetpath):
                        os.mkdir(targetpath, mode)
                elif stat.S_ISCHR(st.st_mode):
                    os.mknod(targetpath, stat.S_IFCHR | mode, st.st_rdev)
                elif stat.S_ISBLK(st.st_mode):
                    os.mknod(targetpath, stat.S_IFBLK | mode, st.st_rdev)
                elif stat.S_ISFIFO(st.st_mode):
                    os.mknod(targetpath, stat.S_IFIFO | mode)
                elif stat.S_ISSOCK(st.st_mode):
                    os.mknod(targetpath, stat.S_IFSOCK | mode)
                elif stat.S_ISREG(st.st_mode):
                    if relpath in self.blacklist:
                        log_msg('Not copying %s' % relpath)
                        continue
                    try:
                        os.unlink(targetpath)
                    except:
                        pass
                    self.copy_file(sourcepath, targetpath, True)

                os.lchown(targetpath, st.st_uid, st.st_gid)
                if not stat.S_ISLNK(st.st_mode):
                    os.chmod(targetpath, mode)
                if stat.S_ISDIR(st.st_mode):
                    directory_times.append((targetpath, st.st_atime, st.st_mtime))
                # os.utime() sets timestamp of target, not link
                elif not stat.S_ISLNK(st.st_mode):
                    os.utime(targetpath, (st.st_atime, st.st_mtime))

                self.copy_size += st.st_size
                text = _("Copying %s ...") % relpath
                text = text + "done"
                self.emit_signal("progress",self.copy_size*1.0/self.total_size,text)
        # Apply timestamps to all directories now that the items within them
        # have been copied.
        for dirtime in directory_times:
            (directory, atime, mtime) = dirtime
            try:
                os.utime(directory, (atime, mtime))
            except OSError:
                # I have no idea why I've been getting lots of bug reports
                # about this failing, but I really don't care. Ignore it.
                pass
        del directory_times

        if self._cancel:
            raise CancelException("Cancel")

    def _do_extract_deal_blacklist(self,steps,percent):
        i = 0.0
        prg = 1.0-percent
        pid=[]
        self.emit_signal("progress",prg,_('Cleaning files ...'))
        for f in self._black_files:
            i += 1
            if self._cancel:
                return
            if os.path.isfile(f):
                os.remove(self.target+f)
            prg = (1.0-percent)+(i/steps)*percent

        for f in self._black_dirs:
            i += 1
            if self._cancel:
                return
            if os.path.isdir(f):
                pn = Popen('rm -rf '+self.target+f, shell=True)
                self._extract_pid = pn.pid
                sts = os.waitpid(pn.pid, 0)[1]
            prg = (1.0-percent)+(i/steps)*percent
        self.emit_signal("progress",prg,_('Cleaning done'))

    def _do_extract(self):
        fs_dirs = MountMod.get_mounts(with_device=False)
        fs_sq = None

        for fs_d in fs_dirs:
            fs_sq = fs_d+'/casper/filesystem.squashfs'
            #print fs_sq
            if os.path.exists(fs_sq):
                break
            fs_sq = None
        if fs_sq == None:
            raise Exception("Can not find \"filesystem.squashfs\".")
        argv=['nice','-n','19','unsquashfs',
###                '-da','128','-fr','128',
                '-f','-d',self.target,fs_sq]
        (pid,StdIn,StdOut,StdErr) = glib.spawn_async(argv,
                                                    flags=glib.SPAWN_SEARCH_PATH|glib.SPAWN_DO_NOT_REAP_CHILD,
                                                    standard_input=True,
                                                    standard_output=True,
                                                    standard_error=True)
        self._extract_pid = pid
        out = os.fdopen(StdOut,'rU')
        err = os.fdopen(StdErr,'rU')
        steps = 0
        steps += len(self._black_files)
        steps += len(self._black_dirs)
        cmd_percent = 0.95
        if steps < 1:
            cmd_percent = 1.0

        def read_out(fd):
            prg = 0.0
            while True:
                l = fd.readline()
                if not bool(l):
                    break
                if l[0] == '[':
                    i = l.find(']')+1
                    if i > 0 and i< len(l):
                        s = l[i:].strip()
                        exp = s.split()[0]+'.0'
                        d = eval(exp) *cmd_percent
                        if abs(d - prg) > 0.001 or prg < 0.001:
                            prg=d
                            self.emit_signal("progress",prg,_('Installing files'))

        read_out(out)
        err_str = None
        try:
            err_str = err.read()
        except:
            pass

        (w_pid,status) = os.waitpid(pid,0)
        self._extract_pid  = 0
        if self._cancel:
            raise CancelException("Cancel")

        if os.WIFEXITED(status):
            if os.WEXITSTATUS(status) != 0 and err_str:
                raise Exception(err_str) 
        elif os.WIFSIGNALED(status):
            raise Exception(_("Process \"unsquashfs\" terminated by signal %d") % os.WTERMSIG(status))
        if steps > 0:
            try:
                self._do_extract_deal_blacklist(steps,1.0-cmd_percent)
            except:pass
            self._extract_pid  = 0
        if self._cancel:
            raise CancelException("Cancel")

    def load_black_list(self):
        """载入黑名单，凡是在黑名单中的文件或文件夹，都不会被复制"""
        """And directory must end with '/'  """
        self._black_files = []
        self._black_dirs = []
        try:
            r = open(self._blacklist)
            for l in r:
                l = l.strip()
                if l and len(l) > 0 and l[0] == '/':
                    if l[-1] == '/':
                        self._black_dirs.append(l)
                    else:
                        self._black_files.append(l)
            r.close()
        except:
            pass

    def is_black(self,filename):
        is_dir = (os.path.isdir(filename) and not os.path.islink(filename))
        if filename.startswith(self.source):
            filename=filename[len(self.source):]
        if is_dir:
            for d in self._black_dirs:
                if filename.startswith(d):
                    return True
        elif filename in self._black_files:
            return True
        return False

    def cancel(self):
        self._cancel = True
        self.can_copy  = not self._cancel
        if self._use_extract and self._extract_pid > 0:
            try:
                os.kill(self._extract_pid,15)
            except:pass

    def _do_before_copy(self):
        try:
            os.makedirs(self.target,0700)
        except:pass

        if MountMod.installing_source:
            self.source = MountMod.installing_source

        self.target = self.target.rstrip('/')
        self.source = self.source.rstrip('/')
        self.can_copy = True
        self.copy_size = 0
        self.total_size = 0

        if self._can_set_proc_opts:
            try:
                for (f,opts) in self.proc_opts.items():
                    if os.path.exists(f):
                        r = open(f)
                        self.proc_opts[f]['old']=r.readline()
                        r.close()
                        w = open(f,'w')
                        w.write(self.proc_opts[f]['new'])
                        w.close()
            except:
                raise

    def _do_after_copy(self):
        if self._can_set_proc_opts:
            try:
                for (f,opts) in self.proc_opts.items():
                    if os.path.exists(f) and self.proc_opts[f].has_key('old'):
                        w = open(f,'w')
                        w.write(self.proc_opts[f]['old'])
                        w.close()
            except:
                raise

    def _run(self):
        self.can_copy  = not self._cancel

        self.emit_signal('started')
        if is_force_copy_mode():
            self._use_extract = False
        res = True
        try:
            self.emit_signal("progress",0.0,_('Preparing for copying ...'))
            self._do_before_copy()
            if self._use_extract:
                self._do_extract()
            else:
                self.do_copy()
        except CopyAbortException:
            res = False
            self.emit_signal("abort",error_msg())
        except CancelException,e:
            self._cancel_exception = e
            res = False
        except:
            self.can_copy  = not self._cancel
            if not self.can_copy:
                self._cancel_exception = CancelException('cancel')
            else:
                self.emit_signal("error",error_msg(),exception_msg())
            res = False
        finally:
            self._do_after_copy()

        self.emit_signal("finished",res)
        self._res_state = res

    def run(self):
        self._run()


def test1():
    def err_msg(obj,msg,detail):
        dialog = gtk.Dialog(title="test",buttons=(gtk.STOCK_OK,gtk.RESPONSE_OK))
        label = gtk.Label(msg)
        dialog.vbox.pack_start(label)
        dialog.show_all()
        label.set_selectable(True)
        dialog.run()
        dialog.destroy()

    glib.threads_init()
    def finish_quit(obj,res,loop):
        print 'res:',res
        loop.quit()
        return False
    def timeout(obj):
        obj.go()
    obj = CopyFile()
    obj._use_extract = True
    obj.set_source('/home/wkt/test')
    obj.set_target('/home/wkt/test_tmp')
    loop = glib.MainLoop()
    obj.connect("finished",finish_quit,loop)
    obj.connect('error',err_msg)
    obj.go()
    loop = glib.MainLoop()
    #loop.run()

def test2():
    obj = CopyFile()
    obj._do_extract()

if __name__ == "__main__":
    test1()
