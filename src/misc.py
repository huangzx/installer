#!/usr/bin/env python
# -*- coding: utf-8; Mode: Python; indent-tabs-mode: nil; tab-width: 4 -*-
# misc.py
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
import traceback

import socket

import glib
import gtk
import gobject
import stat

from subprocess import *

import threading

import installerenv
import locale
import gettext

insenv = installerenv.InstallerEnv()
gettext.install(insenv.pkgname, insenv.localedir, unicode=True)

(LOGIN_AUTOMATICALLY,
 LOGIN_USE_PASS_WORD,
 LOGIN_USE_ENCRYPT_HOME
) = range(3)

LogFile="/var/log/osinstaller/log"

def N_(s):
    return s

def errorbox(toplevel,msg,use_markup=True):
    dialog = gtk.MessageDialog(parent=toplevel,type=gtk.MESSAGE_ERROR,buttons=gtk.BUTTONS_OK)
    dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
    dialog.set_markup(_('<b>Error</b>'))
    if use_markup:
        dialog.format_secondary_markup(msg)
    else:
        dialog.format_secondary_text(msg)
    #dialog.set_size_request(350,-1)
    dialog.set_default_size(350,1)
    dialog.set_resizable(True)
    dialog.run()
    dialog.destroy()

def warningbox(toplevel,one,two,cancel=True):
    if cancel:
        buttons_flag=gtk.BUTTONS_OK_CANCEL
    else:
        buttons_flag=gtk.BUTTONS_OK
    dialog = gtk.MessageDialog(parent=toplevel,type=gtk.MESSAGE_WARNING,buttons=buttons_flag)
    #dialog.set_size_request(350,-1)
    dialog.set_default_size(350,1)
    dialog.set_resizable(True)
    dialog.set_markup("<b>"+one+"</b>")
    dialog.format_secondary_markup(two)
    dialog.set_deletable(False)
    ret = dialog.run()
    dialog.destroy()
    return (gtk.RESPONSE_OK == ret)

def error_except(msg=""):
    (e1,e2,e3)=sys.exc_info()
    sys.stderr.write('%s(%s,%s,%s)\n\r' % (msg,str(e1),str(e2),str(e3)))
    sys.stderr.flush()
    return (e1,e2,e3)

def exception_msg():
    try:
        d = traceback.format_exc()
    except:
        (e1,e2,e3) = sys.exc_info()
        d = str(e2)
    return d

def _log_msg(msg):
    import syslog
    syslog.openlog('osinstaller',syslog.LOG_PID,syslog.LOG_NEWS)
    syslog.syslog(syslog.LOG_DEBUG,msg)
    syslog.closelog()

def log_msg(msg):
    import time
    t_str = time.strftime('%Y/%m/%d %T')
    fpl= None
    d=os.path.dirname(LogFile)
    try:
        os.makedirs(d,0755);
    except:pass
    msglog='[%s]%s\n' %(t_str,msg)
    try:
        fpl = open(LogFile,'a+')
        fpl.write(msglog)
    except:
        sys.stderr.write("log->" + msglog)
        sys.stderr.write(error_msg()+'\n');
    finally:
        if fpl:fpl.close()


def error_msg():
    (e1,e2,e3) = sys.exc_info()
    return str(e2)

def get_cmd_output(cmd,insenv=None,out_err=1,output=None):
    class WorkThread(threading.Thread):
        def __init__(self,args):
            super(WorkThread,self).__init__()
            self.args = args
            self.results=[""]
            self._open_logfile()

        def run(self):
            out=""
            try:
                for l in self.args[0].stdout:
                    self.write(l)
                    if self.args[2] == 1:
                        out = out+l
            except:
                (e1,e2,e3)=error_except()
            err = self.args[0].stderr.read()
            self.write(err)
            if self.args[2] == 2:
                out = err
            self.results[0] = out

            if self._fd:
                self._fd.close()

        def _get_cmd(self):
            vv=self.args[1].strip().split()
            c=vv[0]
            if c == 'chroot':
                c = c+':'+vv[2]
            return os.path.basename(c).strip()
        
        def _get_logfile(self):
            if self.args[3] == None:
                return None
            logfile=self.args[3]+'.'+self._get_cmd()

            d=os.path.dirname(logfile)
            try:
                os.makedirs(d,0755);
            except:pass

            return logfile

        def _open_logfile(self):
            fd = None
            f=self._get_logfile()
            if f:
                try:
                    fd = open(f,"a+")
                except TypeError :
                    pass
                except:
                    raise
                finally:
                    self._fd = fd
            else:
                self._fd = None

        def write(self,line):
            import time
            s = time.strftime('%Y/%m/%d %T')
            if not line.endswith('\n'):
                line = line+'\n'
            ss= s+' from('+self.args[1]+'):'+line
            ##print ss,
            if self._fd:
                self._fd.write(ss)

    s=""
    sts = -1
    try:
        if insenv:
            cmd='chroot '+insenv.target+' '+cmd
        _env = os.environ.copy() ###changed _env will not change os.environ
        ####纯洁一下环境变量
        _env['LANG']='C'
        _env['LANGUAGE']='C'
        _env['LC_ALL']='C'
        _env['PATH']='/usr/sbin:/usr/bin:/sbin:/bin:/usr/bin/X11:/usr/local/sbin:/usr/local/bin'
        _env['LS_COLORS']=''

        os.umask(0022)
        pn = Popen(cmd, shell=True, stdout=PIPE,stderr=PIPE,env=_env)
        args=[pn,cmd,out_err,output]
        wt = WorkThread(args)
        wt.start()
        wt.join()
        s = wt.results[0]
        _pid,sts = os.waitpid(pn.pid, 0)
    except:
        (e1,e2,e3)=error_except()
        s=str(e2)
        if out_err == 1:
            raise
    return (s.strip(),sts)

def cmd_output_lines(cmd):
    os.umask(0022)
    _env = os.environ.copy() ###changed _env will not change os.environ
    ####纯洁一下环境变量
    _env['LANG']='C'
    _env['LANGUAGE']='C'
    _env['LC_ALL']='C'
    _env['PATH']='/usr/sbin:/usr/bin:/sbin:/bin:/usr/bin/X11:/usr/local/sbin:/usr/local/bin'
    _env['LS_COLORS']=''
    p = Popen(cmd,stdout=PIPE,shell=True,env=_env)
    lines=p.stdout.readlines()
    p.wait()
    if p.returncode == 0:
        return lines;
    return []

def cmd_output_log(cmd):
    return get_cmd_output(cmd,insenv=None,out_err=0,output=LogFile)[1]

def cmd_output_log1(cmd,out_err=0):
    return get_cmd_output(cmd,insenv=None,out_err=out_err,output=LogFile)

def get_loop_devices():
    s,sts = get_cmd_output("losetup -a|sed -e 's/:.*(/,/g; s/)//g'")
    lps = []
    for o in s.split('\n',-1):
        o1,o2 = o.split(',',2)
        lps.append((o1,o2))
    return lps

def get_loop_devices():
    s,sts = get_cmd_output("losetup -a|sed -e 's/:.*(/,/g; s/)//g'")
    lps = []
    for o in s.split('\n',-1):
        o1,o2 = o.split(',',2)
        lps.append((o1,o2))
    return lps

def is_block_file(path):
    ret = False
    try:
        st = os.stat(path)
        ret = stat.S_ISBLK(st.st_mode)
    except:
        error_except('is_block_file:')
    return ret

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
        s = "%d " %(int(size))
    return s

def grub_install(dev_file=[],insenv=None):
    for dfile in dev_file:
        (err_out,sts) = get_cmd_output('grub-install --no-floppy --force '+dfile,insenv,out_err=2,output=LogFile)
        if sts != 0:
            return (sts,err_out)
#    (err_out,sts) = get_cmd_output('update-grub',insenv,out_err=2)
#    if sts != 0:
#        return (sts,err_out)
    return (0,"")

def get_memory_size():
    meminfo='/proc/meminfo'
    size = 0
    danwei='B'
    try:
        r=open(meminfo)
        for line in r:
            if 'MemTotal:' in line:
                strv=line.split()
                size=int(float(strv[1])/1024.0)
                danwei='mB'
                break
        r.close()
    except:
        error_except()
    return (size,danwei)

def get_cpu_processors():
    cpuinfo="/proc/cpuinfo"
    r = None
    res = 0
    try:
        r = open(cpuinfo)
        for l in r:
            if l.startswith('processor'):
                res = res+1
    except:
        pass
    finally:
        if r:r.close()
    return res

def is_force_copy_mode():
    if is_virtual_machine():
        return False
    (s,dm) = get_memory_size()
    if s < 768 and get_cpu_processors() < 2:
        return True
    return False

def is_kvm():
    s,sts = get_cmd_output('lscpu')
    if 'KVM' in s:
        return True
    return False

def is_virtual_machine():
    s,sts = get_cmd_output('udevadm info --query=property --name=/dev/input/mouse0')
    s=s.lower()
    if 'vmware' in s:
        return True
    if 'virtualbox' in s:
        return True
    return is_kvm()

def strcompress(str):
    nstr=""
    i=0
    length = len(str)
    while i < length:
        n=str[i]
        if n == '\\':
            if length-i> 3 and str[i+1].isdigit():
                c='%c' % int(str[i+1:i+4],8)
                if length-i>3:
                    i=i+3
                else:
                    i=length
                n=c
            else:
                i=i+1
                n=n+str[i]
        nstr=nstr+n
        i=i+1
    return nstr

def gethome(user,chroot=None):
    r = None
    homedir=None
    pw='/etc/passwd'
    if chroot:
        pw=chroot+pw
    try:
        r = open(pw)
        for l in r:
            vv = l.split(':')
            if vv[0] == user:
                homedir = vv[-2]
                break
    except:
        pass
    finally:
        if r:
            r.close()
    return homedir

def is_live_os():
    proc='/proc/self/mounts'
    r=None
    has_rofs=False
    has_aufs=False
    try:
        r=open(proc,'r')
        for l in r:
            vv=l.split(None,4)
            if vv[1] == '/' and vv[2] == 'aufs':
                has_aufs=True
            elif vv[1] == '/rofs' and vv[0].startswith('/dev/loop'):
                has_rofs=True
            if has_aufs and has_rofs:
                break;
    except:raise
    finally:
        if r:r.close()
    return (has_aufs and has_rofs)

def get_filesystem_size():
    sf = '/etc/filesystem.size'
    r = None
    rs = 0
    try:
        r = open(sf,'r')
        rs = int(r.read().strip())
    except:pass
    finally:
        if r:r.close()
    return rs

def tostring(s):
    r=[]
    i = 0;
    j = 0;
    length = len(s)
    while i < length:
        r.append(s[i])
        #if i+1 <length:print s[i],s[i+1]
        if s[i] == '\\':
            base = 0
            if s[i+1] == '0':
                i+=1
                base=8
            if base != 0:
                d=s[i:i+3]
                #print 'd:'+d
                if d.isdigit():
                    c=int(d,base)
                    r[j] = '%c' % c
                    i= i +2
                    #print r
        j+=1
        i+=1
    rs=""
    for n in r:
        rs+=n
    return rs

def get_cmd_path(cmd):
    for f in os.environ['PATH'].split(':'):
        fn = os.path.join(f,cmd)
        if os.path.exists(fn):
            return fn
    return None

def run_as_root_and_inhibit():
    uid = os.getuid()
    argv = []
    if uid == 0:
        try:
            call(['/etc/init.d/cupsys', 'stop'])
            call(['/etc/init.d/hplip', 'stop'])
        except:pass
        if get_cmd_path('udisks'):
            argv=['udisks', '--inhibit', '--']
        argv.append('/usr/share/osinstaller/OSInstaller')
        argv.extend(sys.argv[1:])
    else:
        if is_live_os():
            argv=['sudo','-E']
        else:
            argv = ['gksudo', '--preserve-env','--sudo-mode','--']
        argv.extend(sys.argv)

    log_msg(str(argv))
    os.execvp(argv[0], argv)
    sys.exit(127)

def pdb_trace():
    import pdb
    pdb.set_trace()

class SingleApp:
    sock_path = '\0/tmp/.osinstaller_single'
    def __init__(self,hook=None,hook_data=None):
        self.hook = hook
        self.hook_data = hook_data
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.has_conn = self.connect()
        if self.has_conn is False:
            self.has_server = self.open_server()
        else:
            self.has_server = False
        self.real_path = None

    def callback(self,source,condition):

        if condition & glib.IO_ERR or condition & glib.IO_HUP:
            return False

        (conn,addr) = self.sock.accept()
        strv = conn.recv(1024).strip().split('\n')
        if self.hook:
            self.hook(strv,self.hook_data)
        conn.close()
        return True

    def connect(self):
        try:
            self.sock.connect(self.sock_path)
            return True
        except:
            return False

    def __open_server(self):
        import tempfile
        (st,real_path) = tempfile.mkstemp(prefix='.osinstallerxx')
        try:
            try:
                os.unlink(real_path)
            except:
                pass
            self.sock.bind(real_path)
            self.sock.listen(5)
            try:
                os.unlink(self.sock_path)
            except:
                pass
            os.symlink(real_path,self.sock_path)
        except:
            error_except(msg='-server')
            return False
        fd=self.sock.makefile()
        glib.io_add_watch(fd,glib.IO_IN|glib.IO_ERR|glib.IO_HUP,self.callback)
        return True

    def open_server(self):
        try:
            self.sock.bind(self.sock_path)
            self.sock.listen(5)
        except:
            error_except(msg='-server')
            return False
        fd=self.sock.makefile()
        glib.io_add_watch(fd,glib.IO_IN|glib.IO_ERR|glib.IO_HUP,self.callback)
        return True

    def send_argv(self,argv=[]):
        for av in argv:
            av = str(av).strip()
            if len(av):
                self.sock.send(av+'\n')

    @property
    def client(self):
        return self.has_conn

    @property
    def server(self):
        return self.has_server

    def close():
        try:
            if self.real_path:os.unlink(self.real_path)
            self.sock.close()
        except:
            pass

class CancelException(Exception):
    """Raise me when want to cancel"""

class CmdException(Exception):
    """Raise me when cmd return non-zero"""

class DeviceBusyException(Exception):
    """Raise me when device is busy """

class PartGeomeryException(Exception):
    """Raise me when Geomery of partition is not right"""

class AbortException(Exception):
    """Raise me when process is abort"""

class CopyAbortException(AbortException):
    """Raise me when copy process is abort"""

class UsernameException(Exception):
    """Raise me when username is illegal"""

class MountException(Exception):
    """Raise me when fail to mount things"""


class GOBjectMod(gobject.GObject):

    def __init__(self):
        super(GOBjectMod,self).__init__()
        self.cancel_init()
        self._can_cancel = False

    def cancel_init(self):
        self._cancel = False
        self._cancel_exception = None

    def idle_timeout(self,sig,*args):

        try:
            #s=u"object: %s\nsig: %s\nargs: %s\n\n" % (self,sig,args)
            #sys.stderr.write(s)
            pass
        except:pass

        self.emit(sig,*args)
        return False

    def emit_signal(self,sig,*args):
        glib.idle_add(self.idle_timeout,sig,*args)

    @property
    def can_cancel(self):
        return self._can_cancel

    def cancel(self):
        self._cancel = True


class GOBjectThreadMod(GOBjectMod):

    __gsignals__ = {"progress": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,(gobject.TYPE_FLOAT,gobject.TYPE_STRING)),
                    "started": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,()),
                    "cancel": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,()),
                    "abort": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,(gobject.TYPE_STRING,)),
                    "error": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,(gobject.TYPE_STRING,gobject.TYPE_STRING)),
                    "finished": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,(gobject.TYPE_BOOLEAN,))}

    def __init__(self):
        super(GOBjectThreadMod,self).__init__()
        self._wait = True
        self._loop = None
        self.__thread_exited = False
        self._res_state = False
        self.__be_waiting_when_exit = False

    def __waiting_thread(self):
        if self.__be_waiting_when_exit:
            pass
        elif self.__thread_exited:
            if self._cancel:
                self._res_state = False
                self.emit('cancel')
            self._loop.quit()
            return False
        return True

    def set_waiting_when_exit(self,waiting=False):
        self.__be_waiting_when_exit = waiting

    def run(self):
        print "Hi,I'm %s" % self

    class WorkThread(threading.Thread):
        def __init__(self,obj):
            threading.Thread.__init__(self)
            self.obj = obj

        def run(self):
            self.obj.run()
            self.obj._GOBjectThreadMod__thread_exited = True

    def go(self,wait=True,fork_thread=True):
        self._wait = wait
        self.cancel_init()
        self.set_waiting_when_exit()
        self.__thread_exited = False
        if self._wait:
            if self._loop == None:
                self._loop = glib.MainLoop()
        if fork_thread:
            wt = self.WorkThread(self)
            wt.start()
        else:
            self.run()
            self.__thread_exited = True
        if self._wait:
            glib.timeout_add(500,self.__waiting_thread)
            self._loop.run()
        return self._res_state

    def walk(self):
        return self.go(fork_thread=False)

class Udisks:
    DUSISKS_BUS_NAME='org.freedesktop.UDisks'
    DUSISKS_OBJECT_PATH='/org/freedesktop/UDisks'
    DUSISKS_INTERFACE='org.freedesktop.UDisks'

    @classmethod
    def get_iface(cls,object_path=DUSISKS_OBJECT_PATH,interface=DUSISKS_INTERFACE):
        import dbus
        bus = dbus.SystemBus()
        obj = bus.get_object(cls.DUSISKS_BUS_NAME,object_path)
        iface = dbus.Interface(obj,interface)
        return iface

    @classmethod
    def get_iface_by_device(cls,device_file):
        iface = None
        object_path = None
        uiface = cls.get_iface()
        try:
            object_path = uiface.FindDeviceByDeviceFile(device_file)
        except:pass
        
        if object_path and len(object_path):
            iface_name = cls.DUSISKS_INTERFACE+'.Device'
            iface = cls.get_iface(object_path,iface_name)
            iface._prop = cls.get_iface(object_path,'org.freedesktop.DBus.Properties')
            iface._iface_name = iface_name
        return iface

    @classmethod
    def get_prop(cls,iface,prop_name):
        try:
            return iface._prop.Get(iface._iface_name,prop_name)
        except:raise
        return None

    @classmethod
    def get_device_prop(cls,device_file,prop_name):
        iface = cls.get_iface_by_device(device_file)
        if iface:
            return cls.get_prop(iface,prop_name)
        return None

    @classmethod
    def device_is_optical_disc(cls,device_file):
        res = False
        try:
            iface = Udisks.get_iface_by_device(device_file)
            res = bool(Udisks.get_prop(iface,'DeviceIsOpticalDisc'))
        except:pass
        return res

    @classmethod
    def get_optical_disc(cls):
        uiface = cls.get_iface()
        dev_files = []
        try:
            dev_files = uiface.EnumerateDeviceFiles()
        except:raise
        res = []
        for o in dev_files:
            if cls.device_is_optical_disc(o):
                res.append(o)
        return res

import ConfigParser
class MiscConfig(ConfigParser.SafeConfigParser):

    def optionxform(self,s):
        return s

    def write2file(self,filename):
        fd=None
        try:
            fd=open(filename,"w")
            self.write(fd)
        finally:
            if fd:fd.close()
        call(['sed','-i','s|[ \t]*=[ \t]*|=|g',filename])
    

def get_partitions():
    r=None
    paths = {}
    devices = []
    try:
        r = open('/proc/partitions')
        for l in r:
            if len(l) < 2:
                continue
            sv = l.split()
            sv[0] = sv[0].strip()
            if not sv[0].isdigit():
                continue
            lsv = len(sv[3])-1
            while lsv > 0:
                if not sv[3][lsv].isdigit():
                    break
                lsv=lsv-1;
            dev = sv[3][:lsv+1]
            devpath = '/dev/'+dev
            if os.path.exists(devpath):
                paths[dev]=devpath
            else:
                paths[sv[3]]='/dev/'+sv[3]
    except:raise
    finally:
        if r:
            r.close()
    return paths

def get_all_cdroms():
    if get_cmd_path('udisks'):
        return Udisks.get_optical_disc()
    ps=get_partitions()
    res=[]
    for (k,i) in ps.items():
        if is_device_cdrom(i):
            res.append(i)
    return res

def is_device_cdrom(device_file):
    (txt,sts) = get_cmd_output("udevadm info --query=property --name=" + device_file +"|grep ID_CDROM")
    if sts == 0 and len (txt.split()) > 0:
        return True
    return False

def get_partition_label(dev_file):
    if get_cmd_path('udisks'):
        label = Udisks.get_device_prop(dev_file,"IdLabel")
    else:
        (label,sts) = get_cmd_output('udisksctl info -b ' +dev_file +"|grep IdLabel|awk -F: '{print $2}'")
    return label

def get_partition_uuid(dev_file):
    if get_cmd_path('udisks'):
        uuid = Udisks.get_device_prop(dev_file,'IdUuid')
    else:
        (uuid,sts) = get_cmd_output('udisksctl info -b ' +dev_file +"|grep IdUUID|awk -F: '{print $2}'")
    return uuid

def os_prober(dev_file,fstype):
    cmd = insenv.datadir+'/osprober %s %s' % (dev_file,fstype)
    return get_cmd_output(cmd)

class MountMod:

    installing_source = None
    @classmethod
    def umount_all(cls,eject=False):
        rf = None
        dev_mdirs=[]
        fails=[]
        try:
            rf = open('/proc/mounts')
            for line in rf:
                line = line.strip()
                if line.startswith('/dev') or '/target' in line:
                    vv = line.split()
                    dev_mdirs.append((vv[0],vv[1]))
        except:
            pass
        finally:
            if rf:
                rf.close()
        os.system('sync;sync;sync;')
        dev_mdirs.reverse()
        for (dev,mdir) in dev_mdirs:
            mdir=strcompress(mdir)
            ndev = dev
            (ndev,sts) = get_cmd_output('readlink -f '+dev)
            dev=ndev.strip().split('\n')[0]
            opts = ""
            try:
                if insenv.is_yinst() and mdir.startswith('/isodevice'):
                    opts = ''
            except:pass

            sts=os.system('umount %s "%s"' % (opts,mdir))
            if Udisks.device_is_optical_disc(ndev):
                if eject:
                    os.system('eject ' + nodev)
                continue
            if insenv.is_yinst() and mdir.startswith('/isodevice'):
                continue

            if ndev.startswith('/dev/loop'):    ###忽略卸载loop设备的错误提示消息
                continue

            if os.path.exists(mdir+'/casper/filesystem.squashfs'):
                continue

            if sts != 0:
                fails.append((sts,dev,mdir))
        return fails

    @classmethod
    def get_mounts(cls,with_device=True,optical_first=True):
        cd_disc = []
        def _dev_cmp(a,b):
            a_is_optical = (a[0] in cd_disc)
            b_is_optical = (b[0] in cd_disc)
            if a_is_optical == b_is_optical:
                a_len = len(a[1])
                b_len = len(b[1])
                if a_len > b_len:
                    return 1
                elif a_len < b_len:
                    return -1
                else:
                    return 0
            if a_is_optical:
                return 1
            return -1
        
        def dev_cmp(a,b):
            res = _dev_cmp(a,b)
            return res

        rf = None
        dev_mdirs=[]
        try:
            rf = open('/proc/mounts')
            for line in rf:
                line = line.strip()
                if line.startswith('/dev') or '/target' in line:
                    vv = line.split()
                    dev_mdirs.append([vv[0],tostring(vv[1])])
        except:
            pass
        finally:
            if rf:
                rf.close()

        if optical_first:
            cd_disc = get_all_cdroms()
        dev_mdirs.sort(dev_cmp,reverse=True)

        dirs_only = []
        for o in dev_mdirs:
            (d,sts) = get_cmd_output('readlink -f "%s"' % o[0])
            if sts == 0:
                o[0] = d
            if not with_device:
                dirs_only.append(o[1])
        if not with_device:
            dev_mdirs = dirs_only

        return dev_mdirs

    @classmethod
    def LoadIso(cls,filename):
        cls.installing_source = '/tmp/.rofs'
        tmpiso='/tmp/.iso';
        cmd = "mkdir -p %s;mkdir -p %s" % (tmpiso,MountMod.installing_source)
        sts=cmd_output_log(cmd)
        mdirs=[]
        if sts != 0:
            return sts
        cmd = "mount -o loop %s %s" % (filename,tmpiso)
        sts=cmd_output_log(cmd)
        if sts == 0:
            mdirs.append(tmpiso)
            cmd = "mount -o loop %s/casper/filesystem.squashfs %s" %(tmpiso,cls.installing_source)
            sts = cmd_output_log(cmd)
            mdirs.append(cls.installing_source)
            os.chdir(cls.installing_source)
        if sts != 0:
            mdirs.reverse()
            for d in mdirs:
                cmd = "umount -l "+d
                os.system(cmd)
        return sts
#~ 
    @classmethod
    def swap_off(cls):
        rf = None
        fails = []
        try:
            rf = open('/proc/swaps')
            for line in rf:
                line = line.strip()
                if len(line) < 1:
                    continue
                if line.startswith('Filename'):
                    continue
                dev_path = line.split()[0]
                sts = os.system('swapoff "%s"' % dev_path)
                if sts != 0:
                    fails.append((sts,dev_path))
        except:
            pass
        finally:
            if rf:
                rf.close()
        return fails

    def __init__(self,insenv=None):
        self.mplist = []
        self.insenv = insenv

    def __check_mplist(self):
        has_root=False
        for m,path,fstype in self.mplist:
            if m == '/':
                has_root = True
        if not has_root:
            raise Exception(_("Must set mountpoint '/'"))
        return has_root

    def set_mplist(self,mplist,check=False):
        self.mplist = mplist
        self.mplist.sort(self.cmp_mp)
        if check:
            return self.__check_mplist()
        else:
            return True

    def write_etc_fstab(self):
        fstab_str = ""
        mp_lines={}
        fstab_str = 'proc            /proc           proc    nodev,noexec,nosuid 0       0\n'
        for (m,path,fstype) in self.mplist:
            opts='defaults      0       2'
            comment=""
            dev_str = path
            if m == '/':
                opts='errors=remount-ro     0       1'
            elif m == 'swap' or fstype.startswith('linux-swap'):
                opts='sw,pri=1       0      0'
                fstype = 'swap'
            if path.startswith('/isodevice/'):
                dev_str = path.replace('/isodevice/','/host/',1)

            if is_block_file(path):
                #dev_str="UUID=%s" % get_partition_uuid(path)
                #comment="### %s is %s during installation\n" % (m,path)
                dev_str=path
                comment="### %s is %s,uuid=%s during installation\n" % (m,path,get_partition_uuid(path))
            else:
                opts='loop,'+opts

            real_m = m
            while real_m == 'swap' and mp_lines.has_key(m):
                m=m+'_'
            if fstype == 'fat32' or fstype == 'fat16' or fstype == 'fat12':
                fstype = 'vfat'
                opts = 'codepage=936,iocharset=cp936,utf8  0    2'
                if real_m == '/boot/efi':
                    opts = 'uid=0,gid=0,' + opts
            mp_lines[m]='%s%-32s   %-16s   %-12s   %-32s\n' % (comment,dev_str,real_m,fstype,opts)
        fstab_str += mp_lines.pop('/')
        for s in mp_lines.values():
            fstab_str += s
        if self.insenv:
            fstab = self.insenv.target+'/etc/fstab'
            w = open(fstab,'w')
            w.write(fstab_str)
            w.close()

    def cmp_mp(self,a,b):
        ma = a[0]
        mb = b[0]
        la = len(ma)
        lb = len(mb)
        if ma > 0 and mb > 0:
            if a[0] != b[0]:
                if a[0] == '/':
                    return -1
                if b[0] == '/':
                    return 1
        if la == lb:
            return cmp(ma,mb)
        if la > lb:
            return 1
        if la < lb:
            return -1

    def mount_procfs(self):
        self.mount_target([('/sys','/sys',''),('/dev','/dev',''),('/proc','/proc','')])

    def mount_target(self,mplist=[]):
        if not mplist or len(mplist) < 1:
            mplist = self.mplist
        if self.insenv:
            target = self.insenv.target
            for (m,path,fstype) in mplist:
                opts=""
                if not is_block_file(path):
                    opts='-o loop'
                if m == path:
                    opts='--bind'
                elif m == 'swap' or fstype.startswith('linux-swap'):
                    cmd = 'swapon ' + path
                    err,sts = get_cmd_output(cmd,out_err=2)
                    continue
                if m == '/':
                    self.root_partition = path
                mp=target+m
                try:
                    os.makedirs(mp)
                except:pass
                if fstype.lower().startswith('fat'):
                    fstype="vfat"                       ##fat filesystem we don't use -t argument
                if fstype and len(fstype) > 0:
                    cmd = 'mount %s -t %s %s %s' % (opts,fstype,path,mp)
                else:
                    cmd = 'mount %s %s %s' % (opts,path,mp)
                err,sts = get_cmd_output(cmd,out_err=2)
                if sts != 0 and len(err) > 0:
                    raise MountException('cmdline:'+cmd+'\n\n'+err)
        else:
            return False
        return True

class WubiConfig:

    def __init__(self,args=None):
        self.username = ""
        self.login_name = ""
        self.encrypted_password = ""
        self.password = ""
        self.hostname = ""
        self.login_type = LOGIN_AUTOMATICALLY
        self.timezone = None
        self.quickly_mode = True
        self.mplist = []
        self.formating_list = []
        self.wubi_config(args)
        self._info()

    def _info(self):

        return
        print 'username:  ',self.username
        print 'login_nem: ',self.login_name
        print 'en passwd: ',self.encrypted_password
        print 'password:  ',self.password
        print 'hostname:  ',self.hostname
        print 'login_type:',self.login_type
        print 'mplist:    ',self.mplist
        print 'formating_list:',self.formating_list

    def __getvv(self,vv,i):
        if len(vv) > i:
            return vv[i]
        return ""

    def wubi_load_config(self,basedir):
        cfg = basedir+'/install/custom-installation/preseed.cfg'
        try:
            r=open(cfg)
            for line in r:
                if len(line) > 3 and line[:3]=='d-i':
                    vv=line.split()
                    if vv[1] == 'netcfg/get_hostname':
                        self.hostname = self.__getvv(vv,3)
                    elif vv[1] == 'passwd/user-fullname':
                        self.login_name = self.__getvv(vv,3)
                    elif vv[1] == 'passwd/username':
                        self.username = self.__getvv(vv,3)
                    elif vv[1] == 'passwd/user-password-crypted':
                        self.encrypted_password = self.__getvv(vv,3)
                    elif vv[1] == 'time/zone':
                        self.timezone = vv[3]
                    elif vv[1] == 'installation/quickly-mode':
                        if vv[2].upper() == 'true'.upper() or vv[2] == '1' :
                            self.quickly_mode = True
                        else:
                            self.quickly_mode = False
                    elif vv[1] == 'autologin':
                        if vv[2].upper() == 'true'.upper() or vv[2] == '1' :
                            self.login_type = LOGIN_AUTOMATICALLY
                        else:
                            self.login_type = LOGIN_USE_PASS_WORD
                    else:
                        pass
            r.close()
        except:
            self.hostname = 'wubi-startos'
            self.username = 'startos'
            self.password = 'startos'
            self.encrypted_passwd = None
            msg = _("Installer set:\n   Username=%s\n   Password=%s") % (self.username,self.password)
            warningbox(None,_('Can\'t get preseed.cfg'),msg,cancel=False)
        if self.hostname == "":
            self.hostname = 'wubi-startos'
        if self.username == "":
            self.username = 'startos'

    def wubi_config(self,args):
        if args == None:
            return
        basedir=args['wubi-dir']
        root_disk = basedir+'/disks/root.disk'
        swap_disk = basedir+'/disks/swap.disk'

        self.wubi_load_config(basedir)

        if os.path.exists(root_disk):
            self.formating_list.append(("",'ext4',root_disk))
        self.mplist.append(('/',root_disk,'ext4'))
        self.boot_dev = root_disk

        if os.path.exists(swap_disk):
            self.formating_list.append(("",'linux-swap',swap_disk))
        self.mplist.append(('swap',swap_disk,'linux-swap'))

class Consolekit:
    def __init__(self):
        import dbus
        try:
            bus = dbus.SystemBus()
            obj = bus.get_object('org.freedesktop.ConsoleKit','/org/freedesktop/ConsoleKit/Manager')
            self.iface = dbus.Interface(obj, 'org.freedesktop.ConsoleKit.Manager')
        except:
            self.iface = None
            type ,err, obj = sys.exc_info()
            print >> sys.stderr,err

    def restart(self):
        ret = True
        self.io_sync()
        if self.iface and os.getpid() != 0:
            self.iface.Restart()
        else:
            ret= (os.system('/sbin/init 6') == 0)
        return ret

    def io_sync(self):
        os.system("sync;sync;sync");

    def shutdown(self):
        ret = True
        self.io_sync()
        if self.iface and os.getpid() != 0:
            self.iface.Stop()
        else:
            ret=(os.system('/sbin/init 0') == 0)
        return ret

class PreConfig:

    def __init__(self,pre_config_file=None):
        self._pre_config_file = pre_config_file
        self._use_preconfig = False
        self._is_readonly = False
        self._autoinstall = False
        self._autorestart = False
        self._key_values = {}

        self.load_preconfig()

    def __str__(self):
        return str(self._key_values)

    @property
    def readonly(self):
        return self._is_readonly

    def set_readonly(self):
        self._is_readonly = True

    @property
    def autoinstall(self):
        """ check for autoinstall """
        return self._autoinstall

    @property
    def autorestart(self):
        """ check for autorestart """
        return (self.use_preconfig and self._autorestart)

    @property
    def use_preconfig(self):
        return self._use_preconfig

    def __getitem__(self,key):
        return self._key_values[key]

    def __setitem__(self,key,value):
        if value == None:
            try:
                del self._key_values[key]
            except:pass
        else:
            self._key_values[key] = value

    def has_key(self,key):
        return self._key_values.has_key(key)

    def get(self,key):
        try:
            return self[key]
        except:
            return None

    def load_preconfig(self):
        r=None
        try:
            r = open(self._pre_config_file)
            for line in r:
                key_value = line.strip().split('=',1)
                key = key_value[0].strip()
                value = None
                if len(key_value) > 1:
                    value=key_value[1].strip()
                key = key.lower()
                self._key_values[key]=value
            self._use_preconfig = True
        except:
            self._use_preconfig = False
        finally:
            if r:
                r.close()
        if self._key_values.has_key('readonly'):
            self._is_readonly = self.get_key_true('readonly')

        self._autoinstall = self.get_key_true('autoinstall')
        if self.autoinstall:
            self._is_readonly = True

        if self.get_key_false('use_auto_parted'):
            uek = self.get('use_entire_disk')
            if not(uek and os.path.exists(uek)):
                self._autoinstall = False

        self._autorestart = self.get_key_true('autorestart')

    def get_key_false(self,key):
        """ 默认值为真"""
        return not self._key_values.has_key(key) or self._get_false(self._key_values[key])

    def _get_false(self,s):
        """ 不匹配假值关键词则为真"""
        return not ( s.lower() == 'false' or (s.isdigit() and int(s) == 0) or s.lower() == 'no')

    def get_key_true(self,key):
        """默认值为假"""
        return self._key_values.has_key(key) and self._get_true(self._key_values[key])

    def _get_true(self,s):
        """ 只有匹配真值关键词 才为真"""
        return ( s.lower() == 'true' or (s.isdigit() and int(s) != 0) or s.lower() == 'yes')

    def update_preconfig(self,mf):
        self._key_values['lang'] = mf.ltz.locale
        self._key_values['user'] = mf.ahl.username
        self._key_values['hostname'] = mf.ahl.hostname
        #self._key_values['password'] = mf.ahl.password
        try:
            self._key_values.pop('password')
        except:pass
        self._key_values['logintype'] = mf.ahl.login_type
        self._key_values['install_bootloader'] = mf.pm.is_install_bldr
        self._key_values['bldr_to_root_disk'] = mf.pm.is_bldr_to_partition
        self._key_values['bootloader_device'] = mf.pm.boot_dev
        self._key_values['quickly_mode'] = mf.pm.quickly_mode
        self._key_values['use_auto_parted'] = mf.pm.use_auto_parted


    def save_preconfig(self,mf):
        if self._is_readonly:
            return
        self.update_preconfig(mf)
        w=None
        try:
            line = ""
            w = open(self._pre_config_file,'w')
            for (key,value) in self._key_values.items():
                if value != None:
                    line=line+key+'='+str(value)+'\n'
                else:
                    line=line+key+'\n'
            w.write(line)
        except:
            self._use_preconfig = False
            raise
        finally:
            if w:
                w.close()

def udisk_test():
    print Udisks.get_device_prop(sys.argv[1],sys.argv[2])

def test():
    def test_hook(strv,d):
        print '---',strv,'----'
    insenv = None
    try:
        import InsEnv
        insenv = InsEnv.InstallerEnv()
    except:pass
    mp=[('/','/dev/sda1','ext4'),('/home','/dev/sda5','ext4')]
    mm=MountMod(insenv)
    print mm.get_mounts(with_device=False)
    sys.exit(0)
    mm.umount_all()
    mm.mount_target()
    mm.write_etc_fstab()

    sys.exit(0)
    sa = SingleApp(hook=test_hook)
    print 'client:',sa.client
    print 'server:',sa.server
    if sa.server:
        loop = glib.MainLoop()
        loop.run()
    if sa.client:
        sa.send_argv(['-fu','dkdj','d0d'])


def test_get_cdroms():
    print get_all_cdroms()

if __name__ == '__main__':
    test_get_cdroms()
