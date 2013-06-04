#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       partmod.py
#       
#       Copyright 2010 wkt <weikting@gmail.com>
#       

import os
import sys

from misc import *

from gettext import *

import gobject
import gtk
import glib

import threading

import parted
from _ped import DiskLabelException


def part_hash(part):
    if not part:
        return '0_0_0'
    geometry = part.geometry
    s=str(geometry.start)
    l=str(geometry.length)
    e=str(geometry.end)
    return (part.disk.device.path+':'+s+'_'+l+'_'+e)

class FSType(object):
    def __init__(self,type,cmd,options,asroot):
        self._type = type
        self.cmd = cmd
        self.options = options
        self.asroot = asroot

    @property
    def type(self):
        if self._type == 'efi':
            return 'fat32'
        return self._type

    def __str__(self):
        return self.type

    @property
    def description(self):
        desc = ""
        if self._type.startswith("ext4"):
            desc = _("Recommended")
        elif self._type.startswith("linux-swap"):
            desc = _("Swap filesystem")
        elif self._type == 'efi':
            return _("EFI system")
        return self.type + '      ' + desc

    @property
    def cmd_exists(self):
        import stat
        for d in os.environ['PATH'].split(':'):
            try:
                f = os.path.join(d,self.cmd)
                st = os.stat(f)
            except:
                continue
            if bool(st.st_mode&stat.S_IXUSR):
                return True
        return False

    def exc_cmd(self,devfile,label=""):
        s=' %s ' % self.options
        label_flag = '-L'
        if self.type == 'fat32' or self.type == 'vfat':
            label_flag = '-n'
        elif self.type == 'reiserfs':
            label_flag = '--label'
        if label == None:
            label = ""
        label = label.strip()
        s=s+" %s '%s' " % (label_flag,label)
        s=self.cmd+s+"'%s'" % devfile
        return s


class PartMan(gobject.GObject):

    fstype=[
        FSType('ext4','mkfs.ext4','-v -F -j -O extent',True),
        FSType('ext3','mkfs.ext3','-v -j',True),
        FSType('ext2','mkfs.ext2','-v',True),
        FSType('xfs','mkfs.xfs','-v -f',True),
        FSType('reiserfs','mkfs.reiserfs','-f',True),
        FSType('linux-swap','mkswap','',False),
        FSType('fat32','mkdosfs','-v -F32',False),
#        FSType('fat16','mkdosfs','-v -F16',False),
    ]

    __gsignals__ = {"loaded": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,()),
                    "current-device-changed":(gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,())
                    }

    mount_points = [('/',N_('Where system will be')),
                    ('/home',N_('For user data')),
                    ('/boot',""),
                    ('/var',""),
                    ('/srv',""),
                    ('/opt',""),
#                    ('/usr',""),
                    ('/usr/local',""),
                    (None,N_("Don't configure mountpoint"))
                ]

    @classmethod
    def FStype(cls,type):
        for ft in cls.fstype:
            if type.startswith(ft.type):
                return ft
        return None

    def __init__(self):
        super(PartMan,self).__init__()
        self._devices = []
        self._device_path = None
        self._path_disk_map = {}    ##{dev_path:disk}
        self._part_mountpoint_map = {} ##{disk:{part_hash:(mp,path,fstype)}}
        self._formating_list = {}   #{path:{'disk':{part_hash:(label,fstye,path)}}}
        self._add_list = {}         ##{disk:{part_hash:path}}
        self._os_list = {}          ##{path:[long name,short name]}
        self._unused_size_cache = {}  ##{path:unusedsize}
        self._mini_size = 1024*1024*1024
        self._count_root_size()
        self._geom_label = {} ## {disk:{part_has:label}}
        self._use_entire_disk = False
        self._use_auto_parted = True
        self._can_auto_parted_shrink_partition = False
        self._auto_parted_use_entire_disk = None
        self._boot_dev = None
        self._auto_part = None
        self._auto_part_replace_mode = False
        self.is_install_bldr = True
        self.is_bldr_to_partition = False
        self.quickly_mode = False
        self.bldr_partition = None
        self.__scan_disck_lock = threading.Lock()
        self.load_devices(True)

    def _count_root_size(self):
        size = get_filesystem_size()
        self._mini_root_size = 0
        gb = 1024*1024*1024.0
        if size > 1:
            gb_size = int(size*1.3/gb)+1;
            self._mini_root_size = gb_size *gb
        else:
            self._mini_root_size = gb * 5

    @property
    def efi_mode(self):
        return os.path.isdir('/sys/firmware/efi/vars')

    @property
    def use_entire_disk(self):
        return self._use_entire_disk

    def set_use_auto_parted(self,_use_auto_parted):
        if not _use_auto_parted:
            self._auto_part = None
            self._use_entire_disk = False
        self._use_auto_parted = _use_auto_parted

    @property
    def auto_part(self):
        return self._auto_part

    @property
    def auto_part_replace_mode(self):
        return self._auto_part_replace_mode

    def set_auto_parted_use_entire_disk(self,disk_path):
        self._auto_parted_use_entire_disk = disk_path
        self._use_entire_disk = True

    use_auto_parted = property(lambda s:s._use_auto_parted,set_use_auto_parted)

    auto_parted_use_entire_disk = property(lambda s:s._auto_parted_use_entire_disk,
                                    set_auto_parted_use_entire_disk)

    def is_fstype_supported(self,fstype):
        for _fs in self.fstype:
            if _fs.type == fstype:
                return True
        return False

    def _get_disk_from_device(self,device):
        disk = None
        try:
            disk = parted.disk.Disk(device)
        except DiskLabelException:
            if device.getSize() >= 1.5*1024*1024 or (device.getSize() >= 1024 and self.efi_mode):
                disk=parted.freshDisk(device,'gpt')
            else:
                disk=parted.freshDisk(device,'msdos')
        return disk

    def load_devices(self,reset=True):
#        devs  = parted.getAllDevices()
        devs = self.getDevices()
        self._devices = []
        for a_dev in devs:
            if bool(a_dev.readOnly) == False:
                self._devices.append(a_dev)
                disk = self._get_disk_from_device(a_dev)
                self._path_disk_map[a_dev.path] = disk
#                if self.boot_dev == None:
#                    self.boot_dev = a_dev.path
                if self._device_path == None:
                    self._device_path = a_dev.path

        self.__scan_disck_lock.acquire()
        if reset:
            self.checkdisk()
            self._formating_list = {}
            self._part_mountpoint_map = {}
            self._add_list = {}
            self._os_list = {}
            self._unused_size_cache = {}
        self.__scan_disck_lock.release()
        self.load_geom_label()
        self.emit('loaded')

    def getDevices(self):
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
        except:raise
        finally:
            if r:
                r.close()
        for (k,path) in paths.items():
            try:
                d = parted.Device(path)
                devices.append(d)
            except:pass
        return devices

    def checkdisk(self):
        for (path,d) in self.disks.items():
            d.check()
            for pt in d.partitions:
                if not is_block_file(d.device.path):
                    raise Exception(_("Found partition table errors on \"%s\"") % path)
        return True

    def __getitem__(self,path):
        for a_dev in self._devices:
            if a_dev.path == path:
                return a_dev
        return None

    def get_current_device(self):
        if self._device_path == None:
            return None
        return self[self._device_path]

    def set_current_device(self,device):
        if self._device_path != device.path:
            self._device_path = device.path
            self.emit("current-device-changed")

    current_device = property(get_current_device,set_current_device)

    @property
    def device_path(self):
        return self._device_path

    @property
    def root_size(self):
        return self._mini_root_size

    @property
    def mini_size(self):
        return self._mini_size

    @property
    def mountpoint_map(self):
        return self._part_mountpoint_map

    @property
    def formating_list(self):
        try:
            self._formating_list[self._device_path]
        except:
            self._formating_list[self._device_path]={}
        return self._formating_list[self._device_path]

    @property
    def current_disk(self):
        if self._device_path == None:
            return None
        return self.disks[self._device_path]

    @property
    def current_disk_type(self):
        if self._device_path == None:
            return None
        return self.disks[self._device_path].type

    @property
    def disks(self):
        return self._path_disk_map

    @property
    def devices(self):
        return self._devices

    @property
    def add_list(self):
        return self._add_list

    @property
    def geom_label(self):
        return self._geom_label

    def root_fstype(self,fsty):
        for f in self.fstype:
            if fsty.startswith(f.type):
                return f.asroot
        return False

    def add_partition(self,part,disk=None):
        if disk == None:
            disk = part.disk
        if hasattr(part,"part_constraint"):
            constraint = part.part_constraint
            delattr(part,"part_constraint")
        else:
            constraint = parted.Constraint(minGeom=part.geometry,maxGeom=part.geometry)

        res = disk.addPartition(part,constraint)
        setattr(disk,'_changed',True)

        if res:
            hash_p = part_hash(part)
            try:
                self.add_list[disk]
            except:
                self.add_list[disk]={}
            self.add_list[disk][hash_p]=part.path
            if hasattr(part,'_new_part_'):
                self._add_list[hash_p] = True
        return res

    def remove_partition(self,part,disk=None):
        if disk == None:
            disk = part.disk
        setattr(disk,'_changed',True)
        rt = disk.removePartition(part)
        if rt:
            hash_p = part_hash(part)
            try:
                self.add_list[disk].pop(hash_p)
            except:pass
            try:
                self._add_list.pop(hash_p)
            except:pass
            try:
                self.formating_list[disk].pop(hash_p)
            except:pass
            try:
                self.mountpoint_map[disk].pop(hash_p)
            except:pass
            try:
                self.geom_label[disk].pop(hash_p)
            except:pass
        return rt

    def fresh_add_list(self,part,disk=None):
        hash_p = part_hash(part)
        if disk == None:
            disk = part.disk
        try:
            if self.add_list[disk][hash_p] != part.path:
                self.add_list[disk][hash_p] = part.path
        except:pass

    def is_new_partition(self,part,disk=None):
        hash_p = part_hash(part)
        if disk == None:
            disk = part.disk
        try:
            return self._add_list[hash_p]
        except:
            return False

    def new_filesytem(self,fstype,geom):
        if fstype == 'linux-swap':
            fstype=fstype+'(v1)'
        return parted.filesystem.FileSystem(type=fstype,geometry=geom)

    def create_new_partition(self,free_part,part_type,fstype,size,can_fix_size=True):
        mb=1024*1024

        sectors_in_mb = int(mb/free_part.geometry.device.sectorSize)

        geom = free_part.geometry

        if sectors_in_mb >= geom.end:
            raise PartGeomeryException("GeomeryException 0")

        start = geom.start + sectors_in_mb
        max_end = geom.end - sectors_in_mb

        if sectors_in_mb > geom.start:
            start = sectors_in_mb

        if can_fix_size:
            _start = start
            if start % sectors_in_mb != 0:
                _start = long((start+sectors_in_mb)/sectors_in_mb)*sectors_in_mb

            _end = max_end
            if max_end % sectors_in_mb != 0:
                _end = long((max_end-sectors_in_mb)/sectors_in_mb)*sectors_in_mb

            if _start < _end:
                start = _start
                max_end = _end

        length = size * sectors_in_mb
        
        end = start+length-1
        while end > max_end:
            length -= sectors_in_mb
            end = start+length-1

        if length <= sectors_in_mb * 8:
            raise PartGeomeryException("GeomeryException 0")

        gmy = parted.geometry.Geometry(geom.device,start,length,end,None)
        if fstype:
            fs=self.new_filesytem(fstype,gmy)
        else:
            fs=None
        np = parted.partition.Partition(free_part.disk,part_type,fs,gmy)
        setattr(np,'_new_part_',True)
        if part_type == parted.PARTITION_LOGICAL or (geom.start <= (start-geom.start)):
            part_constraint = parted.Constraint(minGeom=gmy,maxGeom=gmy)
        else:
            part_constraint = parted.Constraint(minGeom=gmy,maxGeom=geom)
        setattr(np,'part_constraint',part_constraint)
        return np

    def recreate_partition(self,part,fstype=None,disk=None):
        if disk == None:
            disk = part.disk
        if fstype:
            fs = self.new_filesytem(fstype,part.geometry)
        else:
            fs = None

        if fs:
            part.system = fs.getPedFileSystem().type
        else:
            part.system = None

        """
        np = parted.partition.Partition(disk,part.type,fs,part.geometry)
        for k,v in parted.partition.partitionFlag.items():
            try:
                if part.getFlag(k):
                    np.setFlag(k)
            except:pass
        if self.remove_partition(part):
            self.add_partition(np)
            part = np
        """
        return part

    def add_partition_mountpoint(self,part,mp_dir,disk=None):
        if disk == None:
            disk = part.disk
        p_size = part.getSize(unit='b')
        exce_str = None
        if  mp_dir == '/' and p_size < self.root_size:
            exce_str = _('Device is too small.\n    The "<b>/</b>" device must be more than %sB.') % (size2str(self.root_size))
            self.bldr_partition = part.path
        elif mp_dir and len(mp_dir) > 0 and p_size < self.mini_size and (not (part.active and part.getFlag(parted.PARTITION_BOOT))):
            exce_str = _('Device is too small.\n    Device must be more than %sB.') % (size2str(self.mini_size))

        if exce_str:
            raise Exception(exce_str)
            return False

        geom = part_hash(part)
        try:
            for_rm=[]
            for dk in self.mountpoint_map:
                for (h,v) in self.mountpoint_map[dk].items():
                    mdir=v[0]
                    if mdir == mp_dir:
                        for_rm.append(h)
                for o in for_rm:
                    self.mountpoint_map[dk].pop(o)
            if mp_dir and len(mp_dir) > 0:
                try:
                    fs = self.FStype(part.fileSystem.type)
                    fstype = fs.type
                except:
                    fstype = None
                if not self.mountpoint_map.has_key(disk):
                    self.mountpoint_map[disk] = {}
                self.mountpoint_map[disk][geom]=(mp_dir,part.path,fstype)
            else:
                self.mountpoint_map[disk].pop(geom)
        except:
            pass
#        self.boot_dev = disk.device.path
        return True

    def delete_partition_mountpoint(self,part,disk=None):
        if disk == None:
            disk = part.disk
        geom = part_hash(part)
        try:
            self.mountpoint_map[disk].pop(geom)
        except:
            pass

    def has_mountpoint(self,mp_dir,disk=None):
        if disk == None:
            disk = self.current_disk
        try:
            for (m,path,fstype) in self.mountpoint_map[disk].values():
                if m == mp_dir:
                    return True
        except:
            pass
        return False

    def set_preroot(self,root,fstype,formating):
        """set root as / and it's fstype filesystem """
        for (path,disk_object) in self.disks.items():
            if root.startswith(path):
                self.set_current_device(disk_object.device) 
                part = disk_object.getPartitionByPath(root)
                origin_fstype = None
                try:
                    origin_fstype = part.fileSystem.type
                except:pass
                if not bool(fstype):
                    fstype = origin_fstype
                self.add_partition_mountpoint(part,'/')
                if origin_fstype != fstype:
                    formating = True
                if formating:
                    if not self.formating_list.has_key(disk_object):
                        self.formating_list[disk_object] = {}
                    self.formating_list[disk_object][part_hash(part)] = ("",fstype,path)
                break

    def set_current_device_by_path(self,device_path):
        for (path,disk_object) in self.disks.items():
            if device_path.startswith(path):
                self.set_current_device(disk_object.device)
                break

    def set_root_size(self,size):
        if size > self._mini_root_size:
            self._mini_root_size = size

    def load_geom_label(self):
        self.geom_label.clear()
        for dk in self.disks.values():
            part = dk.getFirstPartition()
            try:
                self.geom_label[dk]
            except:
                self.geom_label[dk]={}
            while part != None:
                if (part.type & parted.PARTITION_METADATA or \
                    part.type & parted.PARTITION_PROTECTED):
                    pass
                else:
                    p_h = part_hash(part)
                    label = get_partition_label(part.path)
                    if label and len(label) > 0:
                        self.geom_label[dk][p_h]=label
                part = part.nextPartition()

    def _get_swaps(self,disk,formating_list):
        part = disk.getFirstPartition()
        swap_list =[]
        while part != None:
            if (part.type & parted.PARTITION_METADATA or \
                part.type & parted.PARTITION_PROTECTED):
                pass
            else:
                p_h = part_hash(part)
                fstype = None
                path = None
                try:
                    (l,fstype,path) = formating_list[p_h]
                except:
                    fstype = None
                    path = None
                try:
                    if fstype == None:
                        fstype = part.fileSystem.type
                except:
                    pass
                if fstype and fstype.startswith('linux-swap'):
                    if path == None:
                        path = part.path
                    swap_list.append(path)
            part = part.nextPartition()
        return swap_list

    def set_boot_dev(self,boot_dev):
        self._boot_dev = boot_dev

    def root_device_path(self):
        cur_device_path = None
        if self.current_device:
            cur_device_path = self.current_device.path
        root_dev_path = cur_device_path
        root_dev_list = []
        for (disk,v) in self.mountpoint_map.items():
            t_path = disk.device.path
            for (hs,vv) in v.items():
                if vv[0].strip() == '/':
                    root_dev_list.append(t_path)
        if not (root_dev_path in root_dev_list):
            if len(root_dev_list) > 0:
                root_dev_path = root_dev_list[0]
        return root_dev_path

    def get_boot_dev(self):
        if not (self._boot_dev) or not os.path.exists(self._boot_dev):
            return self.root_device_path()
        return self._boot_dev

    boot_dev = property(get_boot_dev,set_boot_dev)

    def get_changes(self,disks):

        def check_mdir_list(list,mp):
            #print list
            if len(list) < 1 or not mp.startswith('/'):
                return False
            for _t_mp in list:
                if _t_mp[0] == mp:
                    return True
            return False

        m_dir_list=[]
        f_list=[]

        for dk in disks:
            try:
                self.mountpoint_map[dk]
            except KeyError:
                self.mountpoint_map[dk] = {}
            
            mv = self.mountpoint_map[dk]
            try:
                self._formating_list[dk.device.path]
            except KeyError:
                self._formating_list[dk.device.path] = {}
            try:
                self._formating_list[dk.device.path][dk]
            except KeyError:
                self._formating_list[dk.device.path][dk]={}
            fv = self._formating_list[dk.device.path][dk]

            for (h,vv) in mv.items():
                m_dir_list.append(vv)

            for vv in fv.values():
                f_list.append(vv)
            
            for d in self._get_swaps(dk,fv):
                item = ('swap',d,'linux-swap')
                if not (item in m_dir_list):
                    m_dir_list.append(item)
        _m_dir_list = []
        for d in m_dir_list:
            if not check_mdir_list(_m_dir_list,d[0]):
                _m_dir_list.append(d)
        m_dir_list = _m_dir_list
        return (f_list,m_dir_list)

    def clear_mountpoint_map(self):
        disks = self.disks.values()
        for d in self.mountpoint_map.keys():
            if not (d in disks):
                self.mountpoint_map.pop(d)

    def show_geometry(self,part):
        geometry = part.geometry
        s=str(geometry.start)
        l=str(geometry.length)
        e=str(geometry.end)
        print "%10s,start:%012s,end:%012s,%012s,%8sB" % (part.path,s,e,l,size2str(part.getSize(unit='b')))

    @property
    def constraint(self):
        return self.current_device.getConstraint()

    def is_efi_partition(self,part):
        return (part.active and part.getFlag(parted.PARTITION_BOOT) \
                and part.fileSystem and (part.fileSystem.type == 'fat16' or part.fileSystem.type == 'fat32'))

    def is_bios_grub_partiton(self,part):
        return (part.active and part.getFlag(parted.PARTITION_BIOS_GRUB))

    def get_efi_partition(self,disk):
        for np in disk.partitions:
            if self.is_efi_partition(np):
                return np
        return None

    def get_bios_grub_partition(self,disk):
        for np in disk.partitions:
            if np.active and np.getFlag(parted.PARTITION_BIOS_GRUB):
                return np
        return None

    def ext_unused_size(self,part):
        """ Function doc """
        cmd = "dumpe2fs -h "+part.path
        lines = cmd_output_lines(cmd)
        bsize=0
        fbsize=0
        for l in lines:
            if 'Block size:' in l:
                bsize=long(l.split(':')[1].strip())
            if 'Free blocks:' in l:
                fbsize=long(l.split(':')[1].strip())
            if 'Block count:' in l:
                fs_blocks = long(l.split(':')[1].strip())
        fs_unused_size=bsize*fbsize
        fs_size = fs_blocks * bsize
        _unused_size = part.getLength('B')-(fs_size- fs_unused_size)
        setattr(part,'_unusedSize',_unused_size)
        return _unused_size

    def fat_unused_size(self,part):
        cmd='dosfsck -n -v '+part.path
        lines = cmd_output_lines(cmd)
        csize=0
        psize=0
        for l in lines:
            if 'files,' in l:
                t=l.split(',')[1].strip().split('/')
                csize = long(t[1].split()[0])-long(t[0])
            if 'per cluster' in l:
                psize = long(l.strip().split()[0].strip())
        _unused_size = csize * psize
        setattr(part,'_unusedSize',_unused_size)
        return _unused_size

    def ntfs_unused_size(self,part):
        cmd='ntfsresize --info --force --no-progress-bar '+part.path
        lines = cmd_output_lines(cmd)
        _unused_size=0
        for l in lines:
            if 'resize at' in l:
                _unused_size = part.getLength('B')-long(l.split('at')[1].strip().split()[0].strip())
                break
        setattr(part,'_unusedSize',_unused_size)
        return _unused_size

    def reiserfs_unused_size(self,part):
        cmd='debugreiserfs '+part.path
        lines = cmd_output_lines(cmd)
        bsize = 0
        fsize = 0
        fs_size = 0
        for l in lines:
            if 'Blocksize:' in l:
                bsize=long(l.split(':')[1].strip())
            elif "Free blocks" in l:
                fsize=long(l.split(':')[1].strip())
            elif 'Count of blocks on the device:' in l:
                fs_size = long(l.split(':')[1].strip())
        _unused_size=part.getLength('B') - (fs_size - fsize)*bsize
        setattr(part,'_unusedSize',_unused_size)
        return _unused_size

    def part_unused_size(self,part):
        free_size = 0;
        if not self._can_auto_parted_shrink_partition:
            setattr(part,'_unusedSize',0)
            return 0
        if self._unused_size_cache.has_key(part.path):
            setattr(part,'_unusedSize',self._unused_size_cache[part.path])
        elif part.fileSystem.type.startswith('fat'):
            free_size=self.fat_unused_size(part)
        elif part.fileSystem.type == 'ntfs':
            free_size=self.ntfs_unused_size(part)
        elif part.fileSystem.type.startswith('ext'):
            free_size=self.ext_unused_size(part)
        elif part.fileSystem.type == 'reiserfs':
            free_size=self.reiserfs_unused_size(part)
        if free_size > 0 and not self._unused_size_cache.has_key(part.path):
            self._unused_size_cache[part.path] = free_size;
        return free_size;

    def _is_part_fixed_shrink_auto_parted(self,part):
        disk = part.disk
        new_primary_count = disk.maxPrimaryPartitionCount - disk.primaryPartitionCount
        rs = True
        if not(part.type & parted.PARTITION_LOGICAL):
            ####不是逻辑分区即认为是主分区
            """efi 模式下需要efi分区，主分区压缩后剩下的空间只能创建主分区"""
            if self.efi_mode:
                efi_part = self.get_efi_partition(disk)
                if efi_part and new_primary_count < 1:
                    rs = False
                if efi_part is None and new_primary_count < 2:
                    rs = False
            elif new_primary_count < 1:
                rs = False
##        elif disk.maxSupportedPartitionCount <= len(disk.partitions):
##            rs = False
##        print 'rs:',rs
        return rs

    def _is_freespace_fixed_auto_parted(self,part):
        disk = part.disk
        new_primary_count = disk.maxPrimaryPartitionCount - disk.primaryPartitionCount
        rs = False
        extend_part = disk.getExtendedPartition()
        if extend_part:
            if extend_part.geometry.start <= part.geometry.start \
               and extend_part.geometry.end >= part.geometry.end:
                rs = True ###disk.maxSupportedPartitionCount <= len(disk.partitions)
        if not rs:
            if self.efi_mode:
                efi_part = self.get_efi_partition(disk)
                if efi_part and new_primary_count > 0:
                    rs = True
                elif efi_part is None and new_primary_count > 1:
                    rs = True
            elif disk.type == 'gpt':
                bios_grub_part = self.get_bios_grub_partition()
                
                if bios_grub_part and new_primary_count > 0:
                    rs = True
                elif bios_grub_part is None and new_primary_count > 1:
                    rs = True
            elif new_primary_count > 0:
                rs = True
        return rs

    def _os_prober(self,part):
        (s,sts) = os_prober(part.path,part.fileSystem.type)
        s = s.strip()
        if sts == 0 and len(s) > 0:
            vv=s.split(':')
            vv[1]=vv[1].replace('(loader)','').strip()
            self._os_list[vv[0]]=(vv[1],vv[2])
            return part
        return None

    def scan_disk(self,disk):
        max_free_space=None
        max_part_with_free_space = None
        rs=[]

        self.__scan_disck_lock.acquire()
        try:
            if disk.type == 'msdos':
                extend_part = disk.getExtendedPartition()
                if extend_part:
                    try:
    ##                    geom = disk.calculateMaxPartitionGeometry(extend_part,disk.device.getConstraint())
                        disk.maximizePartition(extend_part,disk.device.getConstraint())
                    except:pass

            for pt in disk.partitions:
                if pt.fileSystem:
                    free_size = self.part_unused_size(pt)
                    if not self._os_list.has_key(disk.device.path) \
                        and not self._os_list.has_key(pt.path):self._os_prober(pt)
    ##                print "freeSize:" + size2str(pt._unusedSize)

                    if self._is_part_fixed_shrink_auto_parted(pt):
                        if max_part_with_free_space is None:
                            max_part_with_free_space = pt
                        elif max_part_with_free_space._unusedSize < free_size:
                            max_part_with_free_space = pt
                        elif self._os_list.has_key(pt.path):
                            rs.append(pt)

            for pt in disk.getFreeSpacePartitions():
                if pt.type & parted.PARTITION_FREESPACE and self._is_freespace_fixed_auto_parted(pt):
                    if max_free_space is None:
                        max_free_space = pt
                    elif max_free_space.getLength('B') < pt.getLength('B'):
                        max_free_space = pt

            if max_free_space:
                rs.append(max_free_space)
            
            if max_part_with_free_space:
                rs.append(max_part_with_free_space)
            self._os_list[disk.device.path] = True

        finally:
            self.__scan_disck_lock.release()

        return rs

    def _part_resize_command(self,part,new_size=0):
        """new_size is MiB unit"""
        cmd=None
        if part.fileSystem:
            if part.fileSystem.type.startswith('ext'):
                cmd = 'resize2fs ' + part.path
                if new_size > 0:
                    cmd = cmd + ' ' + str(new_size) + 'M'
            elif part.fileSystem.type == 'ntfs':
                cmd = 'ntfsresize -P --force --force'
                if new_size > 0:
                    cmd += ' -s '+str(new_size*1024*1024) + ' '
                cmd += part.path
            elif part.fileSystem.type == 'reiserfs':
                cmd = 'resize_reiserfs -f '
                if new_size > 0:
                    cmd += ' -s '+str(new_size) + 'M '
                cmd += part.path
                cmd= "/bin/sh -c 'echo y|" + cmd +"'"
            elif part.fileSystem.type.startswith('fat'):
                cmd = 'resize4fat ' + part.path
                if new_size > 0:
                    cmd += ' '+str(new_size) + 'M '
        return cmd

    def _part_fsck_command(self,part):
        cmd = 'fsck -f -y -v ' + part.path
        if part.fileSystem:
            fstype = part.fileSystem.type
            if fstype.startswith('ext'):
                cmd = 'e2fsck -f -y -v ' + part.path
            elif fstype.startswith('fat'):
                cmd = 'dosfsck -a -w -v ' + part.path
            elif fstype == 'ntfs':
                cmd = 'ntfsresize -P -i -f -v ' + part.path
            elif fstype == 'reiserfs':
                cmd = 'reiserfsck --yes --fix-fixable --quiet ' + part.path
        return cmd

    def _fsck_part(self,part):
        fsckcmd = self._part_fsck_command(part)

        _out_err=2
        if part.fileSystem and part.fileSystem.type == 'ntfs':
            _out_err=1
        (err,sts) = get_cmd_output(fsckcmd,out_err=_out_err)
        rs=(sts == 0)
        if part.fileSystem.type == 'reiserfs':
            rs = (sts == 0 or sts == 1 or sts == 256)
        if not rs:
            raise Exception(_("fsck error:%s,code:%d") % (err,sts))

    def _resize_part(self,part,new_size):
        _out_err=2
        if part.fileSystem and part.fileSystem.type == 'ntfs':
            _out_err=1
        cmd = self._part_resize_command(part,new_size)
        if part.fileSystem.type == 'ntfs':
            test_cmd = cmd +' --no-action'
            (err,sts) = get_cmd_output(test_cmd,out_err=_out_err)
            if sts != 0:
                raise Exception(_("resize test error:%s,code:%d") % (err,sts))

        (err,sts) = get_cmd_output(cmd,out_err=_out_err)
        rs=(sts == 0)
        if part.fileSystem.type == 'reiserfs':
            rs = (sts == 0 or sts == 256)
        if not rs:
            raise Exception(_("resize error:%s,code:%d") % (err,sts))


    def shrink_part_size(self,part,new_size):
        """new_size is MiB unit"""
        part.disk.commit()
        self._fsck_part(part)
        new_part = None
        try:
            self._resize_part(part,new_size)
            self._fsck_part(part)
            new_size *= (1024 * 1024)

            length = new_size/part.disk.device.sectorSize

            geom = parted.Geometry(part.disk.device,part.geometry.start,length)
            constraint = parted.Constraint(minGeom=geom,maxGeom=part.geometry)
            part.disk.setPartitionGeometry(partition=part,constraint=constraint,start=geom.start,end=geom.end)
            part.disk.commit()
        finally:
            self._fsck_part(part)
            pass

        return part.nextPartition()

    def auto_parted_from(self,part):

        part_type = parted.PARTITION_NORMAL
        if part.type & parted.PARTITION_LOGICAL:
            part_type = parted.PARTITION_LOGICAL

        fstype = 'ext4'
        if self._auto_part_replace_mode:
            self.recreate_partition(part,fstype)
            self.add_partition_mountpoint(part,"/")
            self.formating_list[part.disk][part_hash(part)]=('',fstype,part.path)
            return

        if part.type & parted.PARTITION_FREESPACE:
            pass
        else:
            part_size = part.getLength('B')
            free_size = part._unusedSize
            new_size = part_size - self.root_size - (part._unusedSize - self.root_size)/2.0 
            part = self.shrink_part_size(part,long(new_size/1024.0/1024.0))

        efi_fstype = 'fat32'

        if self.efi_mode:
            efi_part = None
            efi_part = self.get_efi_partition(part.disk)
            if efi_part is None:
                efi_part = self.create_new_partition(part,part_type,efi_fstype,128)
                efi_part.setFlag(parted.PARTITION_BOOT)
                self.add_partition(efi_part)
                self.formating_list[efi_part.disk][part_hash(efi_part)]=('',efi_fstype,efi_part.path)
                part = efi_part.nextPartition()
        else:
            if part.disk.type == 'gpt':
                bios_grub_part = self.get_bios_grub_partition()
                if bios_grub_part is None:
                    self.create_new_partition(part,part_type,None,8)
                    bios_grub_part.setFlag(parted.PARTITION_BIOS_GRUB)
                    self.add_partition(bios_grub_part)
                    part = bios_grub_part.nextPartition()
        part = self.create_new_partition(part,part_type,fstype,part.getLength('MiB'))
        self.add_partition(part)
        self.add_partition_mountpoint(part,"/")
        self.formating_list[part.disk][part_hash(part)]=('',fstype,part.path)

    def make_use_entire_disk(self,disk):
        use_swap = True
        (msize,dw)=get_memory_size()
        if (not disk) or (not disk.deleteAllPartitions()):
            return False
        setattr(disk,'deleteAll',True)
        mp_map={}
        formating_list={}
        part = disk.getFreeSpacePartitions()[0]

        if self.efi_mode:
            fstype = 'fat32'
            np = self.create_new_partition(part,parted.PARTITION_NORMAL,fstype,128)
            np.setFlag(parted.PARTITION_BOOT)
            self.add_partition(np,disk)
            formating_list[part_hash(np)]=("",fstype,np.path)
            part = np.nextPartition()
        elif part.disk.type == 'gpt':
            np = self.create_new_partition(part,parted.PARTITION_NORMAL,fstype,8)
            np.setFlag(parted.PARTITION_BIOS_GRUB)
            self.add_partition(np,disk)
            part = np.nextPartition()

        size = part.getLength('MiB')
        m_s = size - msize*2
        root_mbsize = self.root_size/1024.0/1024.0
        if m_s < msize*8 or msize > 1024*3 or m_s < root_mbsize:
            use_swap = False
            m_s = size
        if m_s < root_mbsize:
            raise Exception(_('Please select a disk that is more than %sB.') % (size2str(self.root_size)))
        fstype = 'ext4'
        np = self.create_new_partition(part,parted.PARTITION_NORMAL,fstype,m_s)
        self.add_partition(np,disk)
        mp_map[part_hash(np)]=('/',np.path,fstype)
        formating_list[part_hash(np)]=("",fstype,np.path)

        if use_swap:
            part = np.nextPartition()
            np = self.create_new_partition(part,parted.PARTITION_NORMAL,'linux-swap',part.getSize())
            disk.addPartition(np,self.constraint)
            mp_map[part_hash(np)]=('swap',np.path,'linux-swap')
            formating_list[part_hash(np)]=("",'linux-swap',np.path)
        self.mountpoint_map[disk]=mp_map
        self.formating_list[disk]=formating_list

class PartViewMenu:

    ui_str= "<ui>"\
            "   <popup name='menu'>"\
            "       <menuitem name='new' action='new_action' />"\
            "       <menuitem name='change' action='change_action' />"\
            "       <menuitem name='delete' action='delete_action' />"\
            "   </popup>"\
            "</ui>"

#            "       <menuitem name='mp' action='mountpoint_action' />"\
#            "       <separator/>"\

    def __init__(self,pu):
        self._pu = pu

        menu_entry=[
                    ("mountpoint_action",                      #name
                    None,                                  #STOCK ID
                    _("configure mountpoint"),                                  #label
                    None,                                  #accelerator
                    _("configure partittion's mountpoint"),                      #tooltip
                     self.mountpoint_action_callback                #callback
                    ),
                    ("new_action",                       #name
                    gtk.STOCK_NEW,                       #STOCK ID
                    None,                                #label
                    None,                                #accelerator
                    _("Add new partition"),                          #tooltip
                     self.new_action_callback                #callback
                    ),
                    ("delete_action",                      #name
                    gtk.STOCK_DELETE,                      #STOCK ID
                    None,                                  #label
                    None,                                  #accelerator
                    _("Delete this partition"),                          #tooltip
                     self.delete_action_callback                #callback
                    ),
                    ("change_action",                      #name
                    None,                                  #STOCK ID
                    _("Change"),                                  #label
                    None,                                  #accelerator
                    _("change partittion configuration"),                      #tooltip
                     self.change_action_callback                #callback
                    )
                  ]

        ui = gtk.UIManager()
        ag = gtk.ActionGroup('name')

        ui.add_ui_from_string(self.ui_str)
        ag.add_actions(menu_entry)
        ui.insert_action_group(ag)

        self.menu = ui.get_widget("/menu")
        self.menu_new = ui.get_widget('/menu/new')
        self.menu_delete = ui.get_widget('/menu/delete')
        self.menu_change = ui.get_widget('/menu/change')

        self.menu_mp = ui.get_widget('/menu/mp')

        try:
            gtk.settings_get_default().set_property("gtk-menu-images",False)
        except:pass

    def mountpoint_action_callback(self,action):
        self._pu.configure_mountpoint()

    def new_action_callback(self,action):
        self._pu.new_button.clicked()

    def delete_action_callback(self,action):
        self._pu.delete_button.clicked()

    def change_action_callback(self,action):
        self._pu.change_button.clicked()

    def popup(self,event=None):
        if event :
            time = event.time
        time = gtk.get_current_event_time()
        self.menu.popup(None,None,None,0,time)

class PartUI(gobject.GObject):

    __gsignals__ = {"use-entire-disk-changed": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,())}

    (COL_OBJECT,
     COL_PARTITION,
     COL_FSTYPE,
     COL_LABEL,
     COL_MOUNTPOINT,
     COL_SIZE,
     COL_EXTENDED,
     COL_FREESPACE,
     COL_FORMAT,
     COL_TOOLTIP)=range(10)

    def __init__(self,insenv=None,pm=None,build=None):
        super(PartUI,self).__init__()
        self._pm = pm
        self.minimize_part_size = 8*1024*1024

        if build == None:
            build = gtk.Builder()

        self.menu = PartViewMenu(self)

        ui_file = '../data/parted_man.glade'
        if insenv:
            build.set_translation_domain(insenv.pkgname)
            ui_file=insenv.datadir+'/parted_man.glade'
        build.add_from_file(ui_file)

        self.build  = build

        self.diskbox = build.get_object('diskbox')

        self.radio_manual_parted = build.get_object('radio_manual_parted')
        self.radio_auto_parted = build.get_object('radio_auto_parted')

        self.partview = build.get_object('partview')
        self.new_button = build.get_object('new_button')
        self.delete_button = build.get_object('delete_button')
        self.undo_button = build.get_object('undo_button')
        self.change_button = build.get_object('change_button')
        self.desc_label = build.get_object('desc_label')
        self.error_label = build.get_object('error_label')

        self.radio_box = build.get_object('radio_box')

        self.advance_button = build.get_object('advance_button')

        self.partshow = build.get_object('partshow')

        self.auto_parted_box = build.get_object('auto_parted_box')
        self.auto_parted_align = build.get_object('auto_parted_align')
        self.partview_scrolledwindow = build.get_object('partview_scrolledwindow')
        self.partview_box = build.get_object('partview_box')
        self.auto_parted_scrolledwindow = build.get_object('auto_parted_scrolledwindow')

        self.radio_manual_parted.connect("toggled",self._radio_disk_parted)
        self.radio_auto_parted.connect("toggled",self._radio_disk_parted)

        self.configure_partview()
        self.configure_diskbox()

        if self.pm.use_auto_parted:
            self.radio_auto_parted.set_active(True)
        else:
            self.radio_manual_parted.set_active(True)

        self.new_button.connect("clicked",self._on_new_button)
        self.change_button.connect("clicked",self._on_change_button)
        self.undo_button.connect('clicked',self._on_undo_button)
        self.delete_button.connect('clicked',self._on_delete_button)
        self.advance_button.connect('clicked',self._on_advance_button)

    @property
    def pm(self):
        return self._pm

    def configure_partview(self):

        model = gtk.TreeStore(
                gobject.TYPE_PYOBJECT, ##partition object 0
                gobject.TYPE_STRING,   ##disk 1
                gobject.TYPE_STRING,   ##type 2
                gobject.TYPE_STRING,   ##Label 3
                gobject.TYPE_STRING,   ##mount point 4
                gobject.TYPE_STRING,   ##size 5
                gobject.TYPE_BOOLEAN,  ##extended 6
                gobject.TYPE_BOOLEAN,  ##is free 7
                gobject.TYPE_BOOLEAN,  ##is format 8
                gobject.TYPE_STRING,  ##tooltip
                )

        column = gtk.TreeViewColumn()
        column.set_title(_("Partition"))
        cell = gtk.CellRendererText()
        column.pack_start(cell,True)
        column.set_attributes(cell,text=self.COL_PARTITION)
        self.partview.append_column(column)

        column = gtk.TreeViewColumn()
        column.set_title(_("Filesystem"))
        cell = gtk.CellRendererText()
        column.pack_start(cell,True)
        column.set_attributes(cell,text=self.COL_FSTYPE)
        self.partview.append_column(column)

        column = gtk.TreeViewColumn()
        column.set_title(_("Mountpoint"))
        cell = gtk.CellRendererText()
        column.pack_start(cell,True)
        column.set_attributes(cell,text=self.COL_MOUNTPOINT)
        self.partview.append_column(column)

        column = gtk.TreeViewColumn()
        column.set_title(_("Label"))
        cell = gtk.CellRendererText()
        column.pack_start(cell,True)
        column.set_attributes(cell,text=self.COL_LABEL)
        self.partview.append_column(column)

        column = gtk.TreeViewColumn()
        column.set_title(_("Size"))
        cell = gtk.CellRendererText()
        column.pack_start(cell,True)
        column.set_attributes(cell,text=self.COL_SIZE)
        self.partview.append_column(column)

        column = gtk.TreeViewColumn()
        column.set_title(_("Format?"))
        cell = gtk.CellRendererToggle()
        column.pack_start(cell,False)
        column.set_attributes(cell,active=self.COL_FORMAT)
        self.partview.append_column(column)

        self.partview.set_tooltip_column(self.COL_TOOLTIP)

        self.partview.set_model(model)

        selection = self.partview.get_selection()

        selection.connect("changed",self._on_selection_changed)
        self.partview.connect("button-release-event",self._on_button_release_event)
        self.partview.connect('row-activated',self._on_row_activated)

    def configure_diskbox(self):
        model = gtk.ListStore(gobject.TYPE_STRING,gobject.TYPE_PYOBJECT)
        cell = gtk.CellRendererText()
        self.diskbox.pack_start(cell)
        self.diskbox.set_attributes(cell,text=0)
        self.diskbox.set_model(model)
        self.diskbox.connect("changed",self._diskbox_changed)

    def diskbox_load_device(self):
        if self.pm == None:
            return
        model = self.diskbox.get_model()
        model.clear()
        aiter = None
        try:
            cur_dev = self.pm.current_device.path
        except:
            cur_dev = self.pm.boot_dev
        for a_dev in self.pm.devices:
            iter = model.append()
            text = '%s(%sB)' % (a_dev.path,size2str(a_dev.getSize(unit='b')))
            model.set(iter,0,text,1,a_dev)
            if aiter is None:
                aiter = iter
            if cur_dev == a_dev.path:
                aiter = iter
                
        if aiter:
            self.diskbox.set_active_iter(aiter)

    def partview_load_disk(self,disk,mp_map={},formating_list={}):
        extended_part = None
        extended_iter = None
        ret_mp_map = {}

        model = self.partview.get_model()
        model.clear()
        if disk == None:
            iter = model.append(None)
            model.set(iter,self.COL_PARTITION,_("Get no disk ..."))
            return
        self.partview.set_data("disk",disk)
        part = disk.getFirstPartition()
        while part != None:
            part_path = ""
            part_fstype = ""
            part_label = ""
            part_mountpoint = ""
            part_sizestr = "0 B"
            part_format_flag = False
            part_isfree = False
            size = part.getSize(unit='b')
##            self.pm.show_geometry(part)
            if (part.type & parted.PARTITION_METADATA or \
                part.type & parted.PARTITION_PROTECTED):
                pass
            else:
                part_path = part.path
                p_hash = part_hash(part)
                try:
                    fstype = part.fileSystem.type
                    if 'linux-swap' in fstype:
                        fstype='linux-swap'
                    part_fstype = fstype
                except:
                    pass
                try:
                    part_label = self.pm.geom_label[disk][p_hash]
                except:
                    part_label = ""
                try:
                    (part_label,part_fstype,t_path) = formating_list[p_hash]
                    formating_list[p_hash] = (part_label,part_fstype,part_path)
                    part_format_flag = True
                except:
                    pass
                if (part.type & parted.PARTITION_FREESPACE):
                    part_path = _('free space')
                    part_isfree = True
                    if size < self.minimize_part_size:
                        part = part.nextPartition()
                        continue

                try:
                    part_mountpoint,t_path,o_fstype = mp_map[p_hash]
                    ret_mp_map[part_hash(part)]=(part_mountpoint,part_path,part_fstype)
                except:
                    pass

                tooltip_str = None
                if self.pm.root_fstype(part_fstype) and (not part.busy):
                    tooltip_str = _('Double click to configure mountpoint for "<b>%s</b>"') % part_path
                else:
                    if part_isfree:
                        tooltip_str = _("free space")
                    elif part.busy:
                        tooltip_str = _("Device '<b>%s</b>' is busy") % part_path
                    elif part_fstype and len(part_fstype) > 0 :
                        tooltip_str = _('<b>%s</b> is <b>%s</b> filesystem can\'t mount for "/"') % (part_path,part_fstype)

                if extended_part and extended_iter and (extended_part.geometry.start <= part.geometry.start) and \
                (part.geometry.end <= extended_part.geometry.end) :
                    iter = model.append(extended_iter)
                else:
                    iter = model.append(None)
                if (part.type & parted.PARTITION_EXTENDED):
                    extended_part = part
                    extended_iter = iter
                    part_fstype="extend"
                    model.set(iter,self.COL_EXTENDED,True)
                
                if part.active:             ####没有active的part,getFlag返回false就行啦，非要搞个异常出来
                    if part.disk.type == 'gpt' or self.pm.efi_mode:
                        if part.getFlag(parted.PARTITION_BOOT) and (part_fstype == 'fat32' or part_fstype == 'fat16' ):
                            part_fstype = _("EFI system")
                            tooltip_str = part_fstype
                    if part.getFlag(parted.PARTITION_BIOS_GRUB):
                        part_fstype = "bios_grub"
                        tooltip_str = _("bios_grub system")

                part_sizestr = size2str(size)
                model.set(iter,
                        self.COL_OBJECT,part,
                        self.COL_PARTITION,part_path,
                        self.COL_FSTYPE,part_fstype,
                        self.COL_LABEL,part_label,
                        self.COL_MOUNTPOINT,part_mountpoint,
                        self.COL_SIZE,part_sizestr,
                        self.COL_FORMAT,part_format_flag,
                        self.COL_FREESPACE,part_isfree,
                        self.COL_TOOLTIP,tooltip_str
                        )
            part = part.nextPartition()
        self.partview.expand_all()
        mp_map.update(ret_mp_map)

    def bootldr_dialog(self):
        dialog = self.build.get_object('bldr_dialog')
        disk_list_box = self.build.get_object('disk_list_box')
        bldr_check = self.build.get_object('bldr_check')
        bldr_to_partition = self.build.get_object('bldr_to_partition')
        quickly_check = self.build.get_object('quickly_check')
        device_box = self.build.get_object('device_box')
        disk_list_box.set_sensitive(True)

        sigs = {}
        def _on_bldr_check(widget,cbox):
            return
##            cbox.set_sensitive(widget.get_active())

        sigs[bldr_check] = bldr_check.connect('toggled',_on_bldr_check,disk_list_box)
        bldr_check.set_active(self.pm.is_install_bldr)
        _on_bldr_check(bldr_check,disk_list_box)

        if self.pm.efi_mode:
            bldr_to_partition.set_visible(False)
            device_box.set_visible(False)
            

        bldr_to_partition.set_active(self.pm.is_bldr_to_partition)
        quickly_check.set_active(self.pm.quickly_mode )

        model  = disk_list_box.get_model()
        if model == None:
            model = gtk.ListStore(gobject.TYPE_STRING,gobject.TYPE_STRING)
            disk_list_box.set_model(model)
            cell = gtk.CellRendererText()
            disk_list_box.pack_start(cell,True)
            disk_list_box.set_attributes(cell,text=0)

        model.clear()
        disks = self.get_disks()
        aiter = None
        boot_dev = self.pm.boot_dev
        for d in disks:
            path = d.device.path
            text = '%s  ---- %s' % (path,d.device.model)
            iter = model.append()
            if aiter == None:
                aiter = iter
            if boot_dev == path:
                aiter = iter
            model.set(iter,0,text,1,path)
        if aiter:
            disk_list_box.set_active_iter(aiter)

        if self.pm.efi_mode:
            bldr_to_partition.set_active(False)
            bldr_to_partition.set_sensitive(False)

        dialog.set_transient_for(self.toplevel)

        rs = dialog.run()
        if rs == 0:
            self.pm.is_bldr_to_partition = bldr_to_partition.get_active()
            self.pm.is_install_bldr =  bldr_check.get_active()
            self.pm.quickly_mode = quickly_check.get_active()
            iter = disk_list_box.get_active_iter()
            (_boot_dev,) = model.get(iter,1)
            if boot_dev != _boot_dev:self.pm.boot_dev = _boot_dev
        dialog.hide()
        for (o,i) in sigs.items():
            o.disconnect(i)
        sigs = None

    def edit_partition(self,model,iter,add_mode=True):
        part,_fstype,part_label,is_format,old_mdir = model.get(iter,self.COL_OBJECT,self.COL_FSTYPE,self.COL_LABEL,self.COL_FORMAT,self.COL_MOUNTPOINT)
        dialog = self.build.get_object('edit_parttion_dialog')

        edit_mainbox   = self.build.get_object('edit_mainbox')
        part_type_cbox = self.build.get_object('part_type_cbox')
        part_size_spin = self.build.get_object('part_size_spin')
        part_fstype_cbox = self.build.get_object('part_fstype_cbox')
        fortmat_checkbutton = self.build.get_object('fortmat_checkbutton')
        part_label_entry = self.build.get_object('part_label_entry')
        edit_desc_label = self.build.get_object('edit_desc_label')
        fortmat_checkbutton = self.build.get_object('fortmat_checkbutton')
        edit_ok_button = self.build.get_object('edit_ok_button')
        mp_combox = self.build.get_object('mp_combox')

        disk = part.disk

        part_fstype_cbox.set_sensitive(True)

        min_size = int(self.minimize_part_size/1024.0/1024.0)
        max_size = part.getSize()
        part_size_spin.set_range(min_size,max_size)
        part_size_spin.set_value(max_size)
        
        if max_size <= min_size:
            edit_ok_button.set_sensitive(False)
            edit_mainbox.set_sensitive(False)
        else:
            edit_mainbox.set_sensitive(True)
            edit_ok_button.set_sensitive(True)
        part_label_entry.set_text(part_label)

        if add_mode:
            is_format = True
        signal_ids={}

        def configure_part_type_cbox(cbox,disk,part):
            model = cbox.get_model()

            if not bool(model):
                model = gtk.ListStore(gobject.TYPE_STRING,   ##name of part type
                                      gobject.TYPE_BOOLEAN,  ##sensitive
                                      gobject.TYPE_INT       ##code of part type
                                    )
                cbox.set_model(model)
                cell = gtk.CellRendererText()
                cbox.pack_start(cell, False)
                cbox.set_attributes(cell,text=0,sensitive=1)

            can_primary = True
            can_logical = False
            can_extend =  True

            if part.type & parted.PARTITION_LOGICAL:
                can_logical = True
                can_primary = False
            if disk.getExtendedPartition():
                can_extend = False
            if disk.type == 'gpt':
                can_extend  = False

            part_types = []
            if disk.type == "msdos":
                part_types=[
                (_("Primary"),can_primary,parted.PARTITION_NORMAL),
                (_("Logical"),can_logical,parted.PARTITION_LOGICAL),
                (_("Extended"),can_extend,parted.PARTITION_EXTENDED)
               ]
            elif disk.type == 'gpt':
                part_types=[(_("Normal"),True,parted.PARTITION_NORMAL)]

            def _on_part_box_changed(cbox):
                aiter = cbox.get_active_iter()
                if not aiter:
                    return
                (ptype,) = model.get(aiter,2)
                part_fstype_cbox.set_sensitive(ptype!=parted.PARTITION_EXTENDED)
                fs_model = part_fstype_cbox.get_model()
                if fs_model:
                    aiter = fs_model.get_iter_first()
                    while aiter:
                        iter = fs_model.iter_next(aiter)
                        if not iter:
                            part_fstype_cbox.set_active_iter(aiter)
                        aiter = iter

            signal_ids[cbox]=cbox.connect("changed",_on_part_box_changed)

            model.clear()
            aiter = None
            for (text,is_sensitive,pt_type) in part_types:
                iter = model.append()
                model.set(iter,0,text,1,is_sensitive,2,pt_type)
                if is_sensitive and not aiter:
                    aiter = iter
            if aiter:
                cbox.set_active_iter(aiter)

        def configure_part_fstype_cbox(cbox,fstypes=[]):
            model = cbox.get_model()

            def _on_combo_box_changed(widget,value):
                iter = widget.get_active_iter()
                if not bool(iter):
                    return
                model = widget.get_model()
                (can_use,fs,) = model.get(iter,1,2)

                if fs.cmd.lower() == 'false':
                    can_use = False

                (part,is_format,add_mode,mp_box,o_mdir) = value
                is_same = False
                is_root_fstype = self.pm.root_fstype(fs.type)
                try:
                    is_same = part.fileSystem.type.startswith(fs.type)
                except:
                    is_same = False

                if is_same:
                    cbox_is_format = widget.get_data('is_format')
                    if cbox_is_format != None:
                        is_format = cbox_is_format
                else:
                    is_format = can_use

                fortmat_checkbutton.set_active(is_format)
                fortmat_checkbutton.set_sensitive(is_same and can_use and not self.pm.is_new_partition(part))

                if add_mode:
                    part_label_entry.set_sensitive(can_use)
                else :
                    part_label_entry.set_sensitive(is_format)

                if not is_root_fstype and fs:
                    o_mdir = ""
                    if not (hasattr(cbox,'_do_not_configure_mountpoint') and cbox._do_not_configure_mountpoint):
                        self.configure_mountpoint_box(mp_box,part,o_mdir)
                mp_box.set_sensitive(is_root_fstype)

            def _on_mount_point_changed(widget,cbutton):
                model = widget.get_model()
                iter = widget.get_active_iter()
                mp_dir = None
                if iter:
                    (mp_dir,) = model.get(iter,1)
                elif isinstance(widget,gtk.ComboBoxEntry):
                    mp_dir = widget.child.get_text()
                if mp_dir == '/':
#                    cbutton.set_active(True)
#                    cbutton.set_sensitive(False)
                    pass
                else:
                    setattr(cbox,'_do_not_configure_mountpoint',True)
                    cbox.emit("changed")
                    delattr(cbox,'_do_not_configure_mountpoint')
                    pass

            def _on_fortmat_checkbutton(widget,cbox,part):
                iter = cbox.get_active_iter()
                model = cbox.get_model()
                if not bool(iter):
                    widget.set_active(False)
                    widget.set_sensitive(False)
                    return
                is_active = widget.get_active()
                (fs,)=model.get(iter,2)
                try:
                    if part.fileSystem.type.startswith(fs.type) and not (self.pm.is_new_partition(part)):
                        #cbox.set_data('is_format',is_active)
                        pass
                except:pass
                part_label_entry.set_sensitive(is_active)

            if model == None:
                model = gtk.ListStore(gobject.TYPE_STRING,  ## description of fstype
                                      gobject.TYPE_BOOLEAN, ## can use it
                                      gobject.TYPE_PYOBJECT ## fstype
                                      )
                cbox.set_model(model)
                cell = gtk.CellRendererText()
                cbox.pack_start(cell, False)
                cbox.set_attributes(cell,text=0,sensitive=1)
            signal_ids[fortmat_checkbutton]=fortmat_checkbutton.connect("toggled",_on_fortmat_checkbutton,cbox,part)
            signal_ids[cbox]=cbox.connect("changed",_on_combo_box_changed,(part,is_format,add_mode,mp_combox,old_mdir))
            ###signal_ids[mp_combox]=mp_combox.connect("changed",_on_mount_point_changed,fortmat_checkbutton)

            model.clear()

            cbox.set_data('is_format',None)
            if self.pm.efi_mode:
                fstypes=fstypes+[FSType('efi','mkdosfs','-v -F32',False)]

            if part.disk.type == 'gpt':
                fstypes=fstypes+[FSType('bios_grub','false',None,False)]

            if add_mode:
                fstypes=fstypes+[FSType(_("Don't use this partition"),'false',None,False)]
            else:
                fstypes=fstypes+[FSType(_("Unformated partition"),'False',None,False)]
            aiter = None
            a_iter = None
            for fs in fstypes:
                iter = model.append()
                model.set(iter,0,fs.description,1,fs.cmd_exists,2,fs)
                aiter = iter
                try:
                    if part.fileSystem.type.startswith(fs.type):
                        if self.pm.is_efi_partition(part):
                            if fs._type == 'efi':
                                a_iter = iter
                        else:
                            if fs._type != 'efi':
                                a_iter = iter
                except:
                    pass
                if self.pm.is_bios_grub_partiton(part) and fs.type == 'bios_grub':
                    aiter = iter
            if not add_mode and a_iter == None and part.fileSystem:
                iter = model.append()
                fs = FSType(part.fileSystem.type,'False',None,False)
                model.set(iter,0,fs.type,1,False,2,fs)
                a_iter = iter
                fortmat_checkbutton.set_sensitive(False)
            if a_iter:
                aiter = a_iter
            if aiter:
                cbox.set_active_iter(aiter)

        part_label_entry.set_sensitive(add_mode)
        configure_part_type_cbox(part_type_cbox,disk,part)
        mp_model = self.configure_mountpoint_box(mp_combox,part,old_mdir)
        configure_part_fstype_cbox(part_fstype_cbox,self.pm.fstype)

        part_size_spin.set_sensitive(add_mode)
        part_type_cbox.set_sensitive(add_mode)

        if add_mode:
            dialog.set_title(_("Add"))
            edit_desc_label.set_markup(_("\n<b>Add a new partition</b>\n"))
        else:
            dialog.set_title(_("Edit"))
            edit_desc_label.set_markup(_("\n<b>Edit a partition</b>\n"))
        dialog.set_transient_for(self.widget.get_toplevel())
        id = dialog.run()
        dialog.hide()

        for (obj,sig) in signal_ids.iteritems():
            obj.handler_disconnect(sig)

        if id == 0:
            model = part_fstype_cbox.get_model()
            iter = part_fstype_cbox.get_active_iter()
            (part_fs,) = model.get(iter,2)
            part_is_format = fortmat_checkbutton.get_active()
            if part_fs.cmd == 'false':
                part_fstype = None
            else:
                part_fstype = part_fs.type
            part_label = part_label_entry.get_text().strip()
            if add_mode:
                model = part_type_cbox.get_model()
                iter = part_type_cbox.get_active_iter()
                (part_type,)=model.get(iter,2)
                part_size = part_size_spin.get_value()
                np = self.pm.create_new_partition(part,part_type,part_fstype,part_size)
                try:
                    res = self.pm.add_partition(np,disk)
                except:
                    errorbox(self.toplevel,error_msg())
                    res = False
                if res and part_is_format:
                    self.pm.formating_list[disk][part_hash(np)]=(part_label,part_fstype,np.path)
                part = np
            else:
                if part_is_format:
                    try:
                        part = self.pm.recreate_partition(part,fstype=part_fstype)
                    except:
                        errorbox(self.toplevel,exception_msg(),use_markup=False)
                    self.pm.formating_list[disk][part_hash(part)]=(part_label,part_fstype,part.path)
                else:
                    if self.pm.is_fstype_supported(part_fstype) or part_fs.type == 'bios_grub' or part_fs._type == 'efi':
                        try:
                            part = self.pm.recreate_partition(part,fstype=part_fstype)
                        except:
                            errorbox(self.toplevel,exception_msg(),use_markup=False)
                    try:
                        self.pm.formating_list[disk].pop(part_hash(part))
                    except:
                        pass
            iter = mp_combox.get_active_iter()
            if part_fs._type == 'efi':
                part.setFlag(parted.PARTITION_BOOT)
            else:
                part.unsetFlag(parted.PARTITION_BOOT)
            if part.disk.type == 'gpt':
                if part_fs._type == 'bios_grub':
                    part.setFlag(parted.PARTITION_BIOS_GRUB)
                else:
                    part.unsetFlag(parted.PARTITION_BIOS_GRUB)
            if iter:
                (mdir,) = mp_model.get(iter,1)
            elif isinstance(mp_combox,gtk.ComboBoxEntry):
                mdir = mp_combox.child.get_text()
                if len(mdir) > 0 and (not mdir.startswith('/')):
                    errorbox(self.toplevel,_('Mountpoint must be startswith "/"'))
                    mdir = '-'
            if not (mdir and mdir == '-'):
                self.add_partition_mountpoint(part,mdir)
            self.reload()

    def configure_mountpoint(self):
        selection = self.partview.get_selection()
        (model,iter) = selection.get_selected()

        dialog = self.build.get_object('mp_dialog')
        mp_label = self.build.get_object('mp_label')
        mp_combox = self.build.get_object('mp_combox1')

        (part,old_mdir) = model.get(iter,self.COL_OBJECT,self.COL_MOUNTPOINT)
        mp_label.set_markup(_('Configure mountpoint for "<b>%s</b>"') % part.path)
        mp_model = self.configure_mountpoint_box(mp_combox,part,old_mdir)
        dialog.set_transient_for(self.widget.get_toplevel())
        res = dialog.run()
        dialog.hide()
        if res == 0:
            iter = mp_combox.get_active_iter()
            (mdir,) = mp_model.get(iter,1)
            if self.add_partition_mountpoint(part,mdir):
                self.reload()

    def configure_mountpoint_box(self,mp_combox,part,old_mdir):

        mp_model = mp_combox.get_model()
        if mp_model == None:
            mp_model = gtk.ListStore(gobject.TYPE_STRING,## display text
                                     gobject.TYPE_STRING,## mountpoint
                                     )
            mp_combox.set_model(mp_model)
            cell = gtk.CellRendererText()
            mp_combox.pack_start(cell,False)
            if isinstance(mp_combox,gtk.ComboBoxEntry):
                mp_combox.set_text_column(0)
            else:
                mp_combox.set_attributes(cell,text=0)

        mp_model.clear()
        aiter = None
        for (mdir,text) in self.pm.mount_points:
            display_text = ""
            if mdir and len(mdir) > 0:
                if len(text) > 0:
                    display_text = "%s   -- %s" % (mdir,_(text))
                else:
                    display_text = mdir
            else:
                display_text = _(text)
            if len(display_text) > 0:
                iter = mp_model.append()
                mp_model.set(iter,0,display_text,1,mdir)
                if old_mdir == mdir or (len(old_mdir) < 1 and (mdir == None or len(mdir) < 1)):
                    aiter = iter
        if not aiter and len(old_mdir) > 0:
            iter = mp_model.append()
            mp_model.set(iter,0,old_mdir,1,old_mdir)
            aiter = iter
        if aiter:
            mp_combox.set_active_iter(aiter)

        return mp_model

    def add_partition_mountpoint(self,part,mdir,disk=None):
        res = False
        try:
            res = self.pm.add_partition_mountpoint(part,mdir,disk)
        except:
            errorbox(self.toplevel,error_msg())
            res = True
        return res

    def _diskbox_changed(self,widget):
        iter = self.diskbox.get_active_iter()
        model = self.diskbox.get_model()
        (device,) = model.get(iter,1)
        self.pm.current_device = device
        self.pm._use_entire_disk = False
        self.reload()
        if self.pm.efi_mode:
            self.pm.boot_dev = self.pm.current_device.path

    def set_auto_parted_visible(self,visible):
        self.auto_parted_scrolledwindow.set_visible(visible)
        self.partview_box.set_visible(not visible)

    def _radio_disk_parted(self,radio):
        if radio.get_active():
            if radio is self.radio_auto_parted:
                self.pm.use_auto_parted = True
            else:
                self.pm.use_auto_parted = False
            self.reload()

        if self.pm.use_auto_parted:
            self.desc_label_set(_("Please choose an option"))
        else:
            self.desc_label_set(_('Please choose a partition for "/"'))
            self.set_auto_parted_visible(self.pm.use_auto_parted)

    def _on_selection_changed(self,selection):
        is_free = False
        is_extend = False
        can_change = False
        can_delete = False
        can_be_root = False
        part = None
        try:
            (model,iter) = selection.get_selected()
            (part,is_extend,is_free,fs_type) = model.get(iter,self.COL_OBJECT,self.COL_EXTENDED,self.COL_FREESPACE,self.COL_FSTYPE)
            can_delete = not (is_free or part.busy)
            can_be_root = self.pm.root_fstype(fs_type) and (not part.busy)
        except:
            return

        if self.pm.root_fstype(fs_type):
            if (not part.busy):
                tooltip_str = _('Double click to configure mountpoint for "<b>%s</b>"') % part.path
            else:
                tooltip_str = _("Device '<b>%s</b>' is busy") % part.path
            model.set(iter,self.COL_TOOLTIP,tooltip_str)

        can_change = can_delete and not is_extend
#        self.menu.menu_mp.set_sensitive(can_be_root)

        self.new_button.set_sensitive(is_free)
        self.delete_button.set_sensitive(can_delete)
        self.change_button.set_sensitive(can_change)

        self.menu.menu_new.set_sensitive(is_free)
        self.menu.menu_change.set_sensitive(can_change)
        self.menu.menu_delete.set_sensitive(can_delete)

    def _on_button_release_event(self,widget,event):
        self.error_label_set("")
        if event.button != 3:
            return False
        iterable = widget.get_path_at_pos(int(event.x), int(event.y))
        if iterable == None:
            return False
        self.menu.popup(event)
        return False

    def _on_row_activated(self,treeview, path, view_column):
        if self.new_button.get_sensitive():
            self.new_button.clicked()
        elif self.change_button.get_sensitive():
#            model = treeview.get_model()
#            iter = model.get_iter(path)
#            (fsty,part) = model.get(iter,self.COL_FSTYPE,self.COL_OBJECT)
#            if self.pm.root_fstype(fsty):
#                    self.configure_mountpoint()
#            else:
            self.change_button.clicked()

    def _on_new_button(self,button):
        selection = self.partview.get_selection()
        (model,iter) = selection.get_selected()
        self.edit_partition(model,iter)

    def _on_change_button(self,button):
        selection = self.partview.get_selection()
        (model,iter) = selection.get_selected()
        if iter:
            self.edit_partition(model,iter,add_mode=False)

    def _on_undo_button(self,button):
        if not self.pm.use_entire_disk:
            self.pm.load_devices()
            self.reload()

    def _on_delete_button(self,button):
        selection = self.partview.get_selection()
        (model,iter) = selection.get_selected()
        (part,) = model.get(iter,self.COL_OBJECT)
        try:
            self.pm.remove_partition(part)
            self.reload()
        except:
            errorbox(self.toplevel,glib.markup_escape_text(exception_msg()))

    def _on_advance_button(self,button):
        self.bootldr_dialog()

    def desc_label_set(self,label,color='black'):
        self.desc_label.set_markup("<b><span fgcolor='%s'>%s</span></b>" % (color,label))

    def error_label_set(self,text,color='red'):
        self.error_label.set_markup("<b><span fgcolor='%s'>%s</span></b>" % (color,text))

    def reload(self):
        self.pm.clear_mountpoint_map()
        if self.pm.use_auto_parted:
            self.radio_box.set_sensitive(False)
            self.diskbox.set_sensitive(False)
            self.set_auto_parted_visible(True)
            self.auto_parted()
            return
        else:
            disk = self.pm.current_disk

###        print str(self.pm.current_disk.device)

        try:
            mp_map = self.pm.mountpoint_map[disk]
        except:
            self.pm.mountpoint_map[disk] = {}
            mp_map = self.pm.mountpoint_map[disk]
        try:
            formating_list = self.pm.formating_list[disk]
        except:
            self.pm.formating_list[disk] = {}
            formating_list = self.pm.formating_list[disk]

        self.new_button.set_sensitive(False)
        self.delete_button.set_sensitive(False)
        self.change_button.set_sensitive(False)

        self.partview_load_disk(disk,mp_map,formating_list)


    def load_devices(self):
        if not self.pm.disks  or len(self.pm.disks) < 1:
            try:
                self.pm.load_devices()
            except:
                errorbox(self.toplevel,error_msg())

    def _clear_auto_parted_box(self):
        children=self.auto_parted_box.get_children()
        if children:
            for o in children:
                o.destroy()

    def _on_auto_parted_radio(self,w):
        if w.get_active():
            self.pm._auto_part = w.get_data('_part')
            _disk = w.get_data('_disk')
            if self.pm.auto_part and w.get_data('_replace'):
                self.pm._auto_part_replace_mode = True
            else:
                self.pm._auto_part_replace_mode = False
            if _disk and _disk == self.auto_parted_box.get_data('_disk'):
                self.pm._use_entire_disk = True
            else:
                self.pm._use_entire_disk = False
        else:
            self.pm._auto_part = None


    def auto_parted(self):
        disk=None
        
        self.auto_parted_align.set(0.5,0.5,0.0,0.0)
        class WorkThread(threading.Thread):
            
            def __init__(self,func):
                super(WorkThread,self).__init__()
                self._func = func
        
            def run(self):
                self._func()

        def _radio_with_label(group,label_text):
            label = gtk.Label(label_text)
            label.set_use_markup(True)
            label.set_alignment(0,0.5)
            hbox = gtk.HBox()
            hbox.set_size_request(600,-1)
            radio=gtk.RadioButton(group=group)
            radio.set_name('auto_parted_radio')
            hbox.pack_start(label,expand=True,fill=True)
            radio.add(hbox)
            return radio


        def _free_space_option(part,group):
            w=None
            if part.type & parted.PARTITION_FREESPACE and part.getLength('B') > self.pm.root_size:
                label=_("Install StartOS to free space(%s)\n") % (size2str(part.getLength('B')))
                label = label + '<span weight="light" size="small">' \
                        + _("this will create partiton(s) on the free space region") \
                        + '</span>'
                w=_radio_with_label(group,label)
                w.set_data('_part',part)

            return w

        def _shrink_part_option(part,group):
            w=None
            if hasattr(part,'_unusedSize') and part._unusedSize > 2*self.pm.root_size and not part.busy:
                label_head = _("Shrink partition(%s,%s) and Install StartOS\n") % (part.path,size2str(part.getLength('B')))
                label_end = _("Files on the partition will not be deleted.")
                if self.pm._os_list.has_key(part.path):
                    osinfo=self.pm._os_list[part.path]
                    label_head = _("Install StartOS alongside %s(%s,%s)\n") % (osinfo[0],part.path,size2str(part.getLength('B')))
                    label_end += _("\nYou can choose which operating system want each time the computer starts up.")
                label = label_head  \
                        + '<span weight="light" size="small">' \
                        + label_end \
                        + '</span>'
                w = _radio_with_label(group,label)
                w.set_data('_part',part)
            return w

        def _replace_os_option(part,group):
            w=None
            if self.pm._os_list.has_key(part.path) and part.getLength('B') > self.pm.root_size and not part.busy:
                osinfo=self.pm._os_list[part.path]
                label = (_("Replace %s(%s,%s) with StartOS\n") % 
                        (osinfo[0],part.path,size2str(part.getLength('B')))
                        +'<span weight="light" size="small">'
                        +_('<span color="red">WARNING:</span>Files on this partition will be deleted.')
                        +'</span>'
                        )
                w = _radio_with_label(group,label)
                w.set_data('_part',part)
                w.set_data('_replace',True)
            return w

        def _entire_disk_option(disk,group):
            w=None
            if disk and disk.device.getLength('B') >self.pm.root_size:
                label = (_("Erase and use entire disk(%s,%s)\n") % (disk.device.model,size2str(disk.device.getLength('B')))
                                 +'<span weight="light" size="small">'
                                 +_('<span color="red">WARNING:</span>this option will delete any partition(s) and files on the disk \'%s\'') % disk.device.path
                                 +'</span>')
                w = _radio_with_label(group,label)
                w.set_data('_disk',disk)
            return w


        def _finished(disk,part_list):
            _finished.has_auto_parted = False
            self._clear_auto_parted_box()
            _finished.group=None
            w=None
            self.auto_parted_align.set(0.0,0.5,1.0,0.5)

            def _add_option_to_box(w):
                
                if _finished.group is None:
                    _finished.group = w
                w.connect("toggled",self._on_auto_parted_radio)
                _finished.has_auto_parted = True
                align = gtk.Alignment()
                align.set(0.0,0.5,0,0)
                align.add(w)
                self.auto_parted_box.pack_start(align)

            for part in part_list:
                w=None
                if part is None:
                    continue
                w = _free_space_option(part,_finished.group)
                if w:
                    _add_option_to_box(w)
                else:
                    if self.pm._can_auto_parted_shrink_partition:
                        w = _shrink_part_option(part,_finished.group)
                    if w:
                        _add_option_to_box(w)
                    w = _replace_os_option(part,_finished.group)
                    if w:
                        _add_option_to_box(w)

            w = _entire_disk_option(disk,_finished.group)
            if w:
                _add_option_to_box(w)
                if disk and self.pm.auto_parted_use_entire_disk and \
                    self.pm.auto_parted_use_entire_disk == disk.device.path:
                    _finished.group = w

            if _finished.has_auto_parted:
                self.auto_parted_box.set_data('_disk',disk)
            else:
                self.auto_parted_box.set_data('_disk',None)
                self.auto_parted_box.pack_start(gtk.Label(_("No automatically solution")))
            self.auto_parted_box.show_all()
            self.radio_box.set_sensitive(True)
            self.diskbox.set_sensitive(True)
            if _finished.group:
                if _finished.group.get_active():
                    self._on_auto_parted_radio(_finished.group)
                else:
                    _finished.group.set_active(True)
            return False

        def _started():
            self._clear_auto_parted_box()
            widget=gtk.Spinner()
            widget.start()
            widget.set_size_request(48,48)
            self.auto_parted_box.pack_start(widget)
            self.auto_parted_box.show_all()
            return False

        def real_work_func():
            try:
                disk = self.pm._get_disk_from_device(parted.Device(self.pm.current_disk.device.path))
            except:
                return (None,[])
            return (disk,self.pm.scan_disk(disk))

        def work_func():
            part_list = []
            glib.idle_add(_started)
            _disk = None
            try:
                (_disk,part_list) = real_work_func()
            finally:
                glib.idle_add(_finished,_disk,part_list)

        self.auto_parted_box.set_data("_disk",None)
        self.pm._auto_part = None
        self.pm._auto_part_replace_mode = False
        WorkThread(work_func).start()

    @property
    def widget(self):
        return self.build.get_object('mainbox')

    @property
    def toplevel(self):
        toplevel =  self.widget.get_toplevel()
        if (toplevel.flags() & gtk.TOPLEVEL) == gtk.TOPLEVEL:
            return toplevel
        return None


    ###disks can be changed
    def get_disks(self):
        c_disk = None
        if self.pm.use_auto_parted:
            _disk = self.auto_parted_box.get_data("_disk")
            if self.pm.auto_part:
                c_disk = _disk
            elif self.pm.use_entire_disk and _disk:
                c_disk = _disk
                self.pm.make_use_entire_disk(_disk)
        else:
            c_disk = self.partview.get_data("disk")
        disk_list=[]
        if c_disk:
            disk_list.append(c_disk)
        else:
            return disk_list
        for dk in self.pm.disks.values():
            if dk.device.path == c_disk.device.path:
                continue
            disk_list.append(dk)
        return disk_list

    def has_root(self):
        ds = self.get_disks()
        (f,mp) = self.pm.get_changes(ds)
        for v in mp:
            if v[0] == '/':
                return True
        return False

    def check_efi_partition(self):
        part = self.pm.get_efi_partition(self.get_current_disk())
##        print part
        if part == None:
            errorbox(self.toplevel,_("Please create an EFI system on device '%s'") % self.pm.boot_dev)
            return False
        return True

    def get_current_disk(self):
        disks = self.get_disks()
        boot_dev = self.pm.boot_dev
        res = disks[0]
        for dk in disks:
            if self.pm.current_device.path == dk.device.path:
                res = dk
                break;
            elif boot_dev == dk.device.path:
                res=dk
                break
        return res

    def check_bois_grub_partition(self):
        dk = self.get_current_disk()
        rs = True
        if dk.type == 'gpt':
            part = self.pm.get_bios_grub_partition(dk)
            if part == None:
                rs = warningbox(self.toplevel,
                _("Install grub to GPT disk(%s) without bios_grub ?") % self.pm.boot_dev,
                _("This computer is running on BIOS mode.\nIt's a good idea to make a biso_grub parttion.\n"))
        return rs

    def add_efi_partition_mountpoint(self):
        part = self.pm.get_efi_partition(self.get_current_disk())
        return self.add_partition_mountpoint(part,'/boot/efi')

    def check_bootflag_and_fix(self,ds=None,f_mp=None):
        """
        if there is no boot flag partition,then 
        set the root partition a boot flag
        """
        rp = None
        if ds is None:
            ds = self.get_disks()
        if f_mp is None:
            (f,mp) = self.pm.get_changes(ds)
        else:
            f,mp = f_mp
        rdev = self.get_root(mp)
        for d in ds:
            if self.pm.boot_dev != d.device.path:
                continue
            for p in d.partitions:
                if p.getFlag(parted.PARTITION_BOOT):
                    return
                if p.path == rdev:
                    rp = p
        ###{1: 'boot', 2: 'root', 3: 'swap', 4: 'hidden', 5: 'raid', 6: 'lvm', 7: 'lba', 8: 'hp-service', 9: 'palo', 10: 'prep', 11: 'msftres', 12: 'bios_grub', 13: 'atvrecv', 14: 'diag'}
        ###set boot flags,but it is not commit yet
        if rp:
            log_msg ("set boot flag to "+rp.path)
##            print "set boot flag to "+rp.path
            rp.setFlag(parted.PARTITION_BOOT)

    def get_root(self,mp=None):
        if mp is None:
            ds = self.get_disks()
            (f,mp) = self.pm.get_changes(ds)
        for v in mp:
            if v[0] == '/':
                return v[1]
        return None

class PartCommit(GOBjectThreadMod):

    def __init__(self,disks,formating_list,pm=None,mountm=None):
        #super(PartCommit,self).__init__()
        GOBjectThreadMod.__init__(self)
        self._disks = disks
        self._formating_list = formating_list
        self._step = 0
        self._can_cancel = False
        self._pm = pm
        self._mountm = mountm

    @property
    def steps(self):
        return self._steps

    @property
    def step(self):
        return self._step

    def is_device_busy(self,dev_path):
        r = None
        res = False
        try:
            r = open('/proc/mounts')
            for line in r:
                line = line.strip()
                if line.startswith(dev_path):
                    res = True
                    break
        except:
            pass
        finally:
            if r:
                r.close()
        return res

    def _commit_and_format(self):
        log_msg(str(self._disks))
        if self._pm and self._pm.use_auto_parted:
##            print self._pm,self._pm.use_auto_parted
            self.emit_signal("progress",0.0,_("Applying automatically partition solution"))
            self._pm.auto_parted_from(self._pm.auto_part)
            (formating_list,mplist) = self._pm.get_changes(self._disks)
            if self._mountm:
                self._mountm.set_mplist(mplist,check=True)
            self._formating_list = formating_list

        self._steps = len(self._disks) + len(self._formating_list)

        for dk in self._disks:
            if self._cancel:
                break
            dev_path = dk.device.path
            text = _('Commit changes to "<b>%s</b>" ...') % dev_path
            self.emit_signal("progress",self.step*1.0/self.steps,text)
            try:
                if dk.device.busy and dk.deleteAll:
                    raise DeviceBusyException(_('Device "<b>%s</b>" is busy !') % dev_path)
            except DeviceBusyException:
                raise
            except :pass

            if hasattr(dk,"_changed") and getattr(dk,"_changed"):
                dk.commit()
            self._step += 1
            text = _('"<b>%s</b>" changed') % dev_path
            self.emit_signal("progress",self.step*1.0/self.steps,text)

        log_msg(str(self._formating_list))
        for (label,type,path) in self._formating_list:
            if self._cancel:
                break

            fs=PartMan.FStype(type)
            cmd = fs.exc_cmd(path,label)

            text = _('Formating "<b>%s</b>" as %s filesystem ...') % (path,fs.type)
            self.emit_signal("progress",self.step*1.0/self.steps,text)
            self._formating_popen = None
            errmsg,st = cmd_output_log1(cmd)
            if st != 0:
                if not self._cancel:
                    raise CmdException(errmsg)
            self._step += 1
            text = _('"<b>%s</b>" formated') % path
            self.emit_signal("progress",self.step*1.0/self.steps,text)
        self.emit_signal("progress",1.0,"")

    def _run(self):
        res = True
        self.emit_signal('started')
        try:
            self._commit_and_format()
        except CancelException,e:
            self._cancel_exception = e
            res = False
        except :
            raise
            res = False
            if self._cancel:
                self._cancel_exception = CancelException('cancel')
            else:
                msg = exception_msg()
                self.emit_signal('error',error_msg(),msg)
        self.emit_signal('finished',res)
        self._res_state = res

    def cancel(self):
        self._cancel = True
        try:
            self._formating_popen.kill()
        except:
            pass

    def run(self):
        self._run()
        log_msg("cancel:%s"  % self._cancel)

def main():
    glib.threads_init()
    win = gtk.Window()
    pm=PartMan()
#    pm.use_entire_disk = True
    pu=PartUI(None,pm)
    win.add(pu.widget)
    win.resize(400,450)
    win.show()
    pu.load_devices()
    pu.diskbox_load_device()
    pu.reload()
    win.connect("destroy",gtk.main_quit)
    gtk.main()
    ds=pu.get_disks()
    (f,mp)=pm.get_changes(ds)
    print f,mp
    pu.check_bootflag_and_fix(ds,(f,mp))
    print pm.use_auto_parted,pm.auto_part
    pc=PartCommit(ds,f,pm=pm)
#    pc.go()
#    print pm.FStype('ext4')
#    print mp,pu.get_root()
#    print 'use_entire_disk:',pm.use_entire_disk
#    print f
    return 0

def test_resize():
    pm=PartMan()
    pm.load_devices()
    
    def part_by(dev_path):
        for p,dk in pm.disks.items():
            for np in pm.scan_disk(dk):
                if np.path == dev_path:
                    print np.fileSystem.geometry
                    print np.geometry
                    return np
        return None
    part = part_by(sys.argv[1])
    if part:
        new_size = (9663676416/1024/1024) ##(part.getLength('B') - (part._unusedSize/2))/1024.0/1024.0
        old_part=part
        part = pm.shrink_part_size(part,long(new_size))
        print old_part.fileSystem.geometry

if __name__ == '__main__':
	test_resize()

