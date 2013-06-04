#!/usr/bin/env python
# -*- coding: utf-8; -*-
# mainframemod.py
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

import gtk
import cairo
import pangocairo
import pango

import locale
import gettext

import installerenv

from accountmod     import *
from copyfilemod    import *
from localetzonemod import *
from partmod        import *
from installscript  import *
from misc           import *
#from layoutwidget   import *
#from jsextend import *

class ProgressWidget(gtk.Widget):

    def __init__(self):
        super(ProgressWidget,self).__init__()
        self._mini_width = 100;
        self._mini_heigt = 9;
        self._progressbar_size = 8;
        self._label = gtk.Label();
        self._label.show()
        self.set_progress(0.0)
        self.set_has_window(False)

    def set_progress(self,progress):
        if progress < 0.0:
            progress = 0.0;
        elif progress > 1.0:
            progress = 1.0
        self._progress = progress
        if hasattr(self,'child') and self.child:
            text = "%0.2lf%%" % (100*progress)
            self._label.set_alignment(progress,0.0)
            self._label.set_text(text)
        if self.is_drawable():
            self.queue_draw()

    def do_size_allocate(self,allocation):
        self.allocation = allocation
        if hasattr(self,'child') and self.child:
            bin_alc =  gtk.gdk.Rectangle()
            bin_alc.x = allocation.x;
            bin_alc.y = allocation.y + self._progressbar_size;
            bin_alc.width = allocation.width;
            bin_alc.height = allocation.height - self._progressbar_size;
            self.child.size_allocate(bin_alc);

    def do_size_request(self,requisition):
        (requisition.width,requisition.height) = (0,0);
        if hasattr(self,'child') and self.child:
            (requisition.width,requisition.height) = self.child.size_request()
        
        requisition.width = max(requisition.width,self._mini_width);
        requisition.height += max(requisition.height,self._mini_heigt);

        if hasattr(self,'border_width'):
            requisition.width += (self.border_width + self.style.xthickness)*2
            requisition.height += (self.border_width + self.style.ythickness)*2

    def do_expose_event(self,event):
        cr = self.get_window().cairo_create()
        alc = self.allocation
        linear = cairo.LinearGradient(alc.x,alc.y,alc.x + alc.width*self._progress,alc.y);
        linear.add_color_stop_rgb(0.0,0.41796875,0.85546875,0.6328125);
        linear.add_color_stop_rgb(1.0,0.31640625,0.71484375,0.95703125);
        if not hasattr(self,'child') and alc.height-self._progressbar_size > 0:
            alc.y += (alc.height - self._progressbar_size)/2.0
        alc.height = min(alc.height,self._progressbar_size);
        cr.rectangle(alc.x,alc.y,alc.width*self._progress,alc.height);
        cr.clip()
        cr.set_source(linear)
        cr.paint()
        res = False
        if hasattr(self,'child'):
            res = gtk.Bin.do_expose_event(self,event)
        return res

gobject.type_register(ProgressWidget)

class LabelWidget(gtk.Widget):

    def __init__(self):
        super(LabelWidget,self).__init__()
        self._label = ""
        self._new_label = ""
        self.set_has_window(False)
        self.set_redraw_on_allocate(True)
        self._alpha = 1.0;
        self._layout = self.create_pango_layout("")
        self._xpad = 0;
        self._line_height = 0;
        self._layout.set_wrap(pango.WRAP_WORD)

    def set_label(self,text):
        self._new_label = text;
        glib.timeout_add(10,self._on_changing_label)

    def set_text(self,text):
        self._label = text;
        self._layout.set_text(self._label)
        if self.is_drawable():
            self.queue_draw()

    def do_size_allocate(self,allocation):
        self.allocation = allocation
        self._layout.set_width((allocation.width)*pango.SCALE);

    def do_size_request(self,requisition):
        (t,(x,y,w,h)) = self._layout.get_pixel_extents()
        requisition.width = min(550,w)+self._xpad*3;

        self._line_height = h/self._layout.get_line_count()
        requisition.height = max(self._line_height,h)
        requisition.width += self._line_height

    def _on_changing_label(self):
        res = True
        step = 0.05;
        if self._new_label != self._label:
            if not self._label:
                self._alpha = 0.0
            if self._alpha <= 0:
                self._label = self._new_label
                self._layout.set_text(self._label);
                self._alpha = 0.0;
            else:
                self._alpha -= step;
        else:
            self._alpha += step

        if self._alpha >= 1.0:
            self._alpha = 1.0;
            self._new_label = ""
            res = False

        self.queue_draw()
        return res

    def do_expose_event(self,event):
        cr = self.get_window().cairo_create()
        (t,(x,y,w,h)) = self._layout.get_pixel_extents()

        cr = self.get_window().cairo_create()
        alc = self.allocation
        cr.rectangle(alc)
        cr.clip()

        alc.x += self._line_height+self._xpad*2
        alc.width = w;

        cl = self.style.fg[gtk.STATE_NORMAL]
        cr.set_source_rgba(cl.red/65536,cl.green/65536,cl.blue/65536,self._alpha)
        cr.move_to(alc.x,alc.y)

        cr.show_layout(self._layout)

        alc.x = self.allocation.x + self._xpad;
        alc.width = self._line_height*0.7
        alc.height = self._line_height*0.7
        alc.y += (self._line_height-alc.height)/2.0;

        cr.save();
        cr.rectangle(alc)
        cr.clip_preserve()
        cr.set_source_rgba(0.41796875,0.85546875,0.6328125,self._alpha);
        cr.paint()
        cr.restore()

        return False

gobject.type_register(LabelWidget)


class InstallingView(gtk.Container):

    label_contexts = None
    try:
        import labelcontexts
        label_contexts = labelcontexts.label_contexts
    except:
        label_contexts = [
            "",
        ]

    def __init__(self,insenv = None):
        super(InstallingView,self).__init__()
        self.insenv = insenv
        self._bg_filename = None
        if self.insenv:
            self._bg_filename = self.insenv.datadir+'/gtkrc/installing_bg.png'
        self._progressbar = ProgressWidget()
        self._progressnum = gtk.Label("")
        self._progresslabel = gtk.Label("")
        self._progressbox = gtk.VBox(spacing=5)
        self._progressbox.pack_start(self._progressnum)
        self._progressbox.pack_start(self._progresslabel)
        self._label = LabelWidget()
        self._cancel_button = gtk.Button(gtk.STOCK_CANCEL)
        self._restart_later_button = gtk.Button(_("_Quit"))
        self._is_finished = False
        self.set_has_window(False)
        self._working = False
        self.forall(gtk.Widget.set_parent,self)
        self._label_index = 0;

        self._timeout_id = -1;

        self.set_progress(0.0)
        self._cancel_button.set_use_stock(True);
        self._restart_later_button.hide()
        self._restart_later_button.set_can_focus(True);
        self._cancel_button.set_can_focus(True);
        self.set_cancellable(False)
        self._progresslabel.modify_fg(gtk.STATE_NORMAL,gtk.gdk.Color("#fb4b06"));
        self._progressnum.modify_fg(gtk.STATE_NORMAL,gtk.gdk.Color("#fb4b06"));
        self.forall(gtk.Widget.show_all)
        self.show()
        self._progresslabel.set_size_request(-1,20)
        self._progresslabel.set_justify(gtk.JUSTIFY_CENTER)
        self._progresslabel.set_ellipsize(pango.ELLIPSIZE_END)

    def set_progress(self,progress,text=None):
        if progress > 1.0:
            progress = 1.0;
        elif progress < 0:
            progress = 0;
        self._progressbar.set_progress(progress)
        prog_text = "%.2lf%%" % (progress*100)
        fmt="<span font='12.5' >%s</span>"
        self._progressnum.set_markup( fmt % (prog_text))

        if progress >= 0.95 and progress < 0.99:
            text = _("Almost finished")
        if text and len(text) > 0:
            self.set_progresslabel(fmt % (text))

    def set_fraction(self,prog):
        self.set_progress(prog)

    def _rolling_label(self):
        length = len(self.label_contexts);
        if self._label_index >= length:
            self._label_index = 0;

        self.set_label(self.label_contexts[self._label_index]);
        self._label_index += 1
        return True

    def label_rolling_start(self):
        self.label_rolling_stop()
        self._rolling_label()
        self._timeout_id = glib.timeout_add_seconds(15,self._rolling_label);

    def label_rolling_stop(self):
        if self._timeout_id > 0:
            glib.source_remove(self._timeout_id);

    def set_progresslabel(self,label):
        text=label #'<span font="14" size="x-large" >' + label +'</span>'
        self._progresslabel.set_markup(text)

    def set_installing(self):
        self.label_rolling_start();

    def set_label(self,label):
        self._label.set_label(label)

    def set_text(self,label):
        self._label.set_text(label)

    def set_cancellable(self,cancellable):
        self._cancel_button.set_sensitive(cancellable)

    def set_success(self):
        self.set_progress(1.0,_("Installation finished"));
        self.label_rolling_stop()
        self.set_label(_("StartOS is ready now\nPlease restart and use it!"))

    def set_disable_mouse(self):
        pass

    def set_failed(self):
        self.set_progresslabel(_("<b>Installation failed .</b>"))

    def set_working(self,working):
        self._working = working

    def do_size_allocate(self,allocation):
        self.allocation = allocation
        alc = gtk.gdk.Rectangle(allocation.x,allocation.y,allocation.width,allocation.height)

        alc.x += 1;
        alc.y += 1;
        alc.width -= 2;
        alc.height -= 2;
        alc.y = 322;
        (t,alc.height) = self._progressbar.get_child_requisition()
        self._progressbar.size_allocate(alc)

        w = alc.width
        alc.y += alc.height+20;
        t,alc.height = self._progressbox.get_child_requisition()
        alc.width = 192;
        alc.x = (allocation.width-alc.width)/2.0
        self._progressbox.size_allocate(alc)
        alc.width = w

        alc.x = 40;
        alc.width -= 80;
        alc.y += alc.height+30;
        alc.height = allocation.y + allocation.height - alc.y - 60;
        self._label.size_allocate(alc)

        edge_size = 20;
        mini_width = 100;
        alc.width,alc.height = self._restart_later_button.get_child_requisition()
        alc.width = max(alc.width,mini_width)
        alc.y = allocation.y + allocation.height-alc.height - edge_size;
        if self._restart_later_button.get_visible():
            alc.x = allocation.x + allocation.width-alc.width-edge_size;
            self._restart_later_button.size_allocate(alc)
        else:
            alc.width = 0;
            alc.x = allocation.x + allocation.width-alc.width;

        alc.width,alc.height = self._cancel_button.get_child_requisition()
        alc.width = max(alc.width,mini_width)
        alc.x = alc.x -alc.width - edge_size;
        self._cancel_button.size_allocate(alc)

    def do_size_request(self,requisition):
        requisition.width = 795
        requisition.height = 552;
        self.forall(gtk.Widget.size_request)

    def do_forall(self,include_internals,callback,object):
        if include_internals:
            callback(self._progressbar,object)
            callback(self._progressbox,object)
            callback(self._label,object)
            callback(self._cancel_button,object)
            callback(self._restart_later_button,object)

    def do_expose_event(self,event):
        cr = self.get_window().cairo_create();
        bg_im = cairo.ImageSurface.create_from_png(self._bg_filename)
        cr.set_source_surface(bg_im)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        return gtk.Container.do_expose_event(self,event)

gobject.type_register(InstallingView)

class MainUIFrame:

    def __init__(self,insenv = None):
        self.insenv = insenv
        self.mf = None

        build = gtk.Builder()
        self.build  = build
        ui_file = '../data/installer_ui.glade'
        if insenv:
            build.set_translation_domain(insenv.pkgname)
            ui_file = insenv.datadir+'/installer_ui.glade'
        build.add_from_file(ui_file)

        self.install_view = InstallingView(insenv)
        self.install_view.show()

        self.locale_tzone_kbd = build.get_object('locale_tzone_kbd')
        self.account_host_login = build.get_object('account_host_login')
        self.part_man = build.get_object('part_man')
        self.install_box = build.get_object('install_box')
        self.install_button = build.get_object('install_button')
        self.cancel_button =  build.get_object('cancel_button')

        self.install_progressbar = self.install_view

        self.install_progress_button = self.install_view._cancel_button ###build.get_object('install_progress_button')
        self.install_progress_button.set_name('install_progress_button')

        self.restart_later_button = self.install_view._restart_later_button ###build.get_object('restart_later_button')
        self.restart_later_button.set_name('restart_later_button')

        self.install_info_pad = build.get_object('install_info_pad')
        self.install_box.set_focus_chain([self.install_info_pad])
        self.install_box.show_all();

        try:
            gtk.settings_get_default().set_property("gtk-button-images",False)
        except:pass

    def set_widget_same_size(self,*args):
        w=-1
        h=-1
        for widget in args:
            (w1,h1) = widget.size_request()
            if w1 > w:
                w = w1
            if h1 > h:
                h = h1
        for widget in args:
            widget.set_size_request(w,h)

    def copy_error_func(self,msg):

        dialog = self.build.get_object('copy_error_dialog')
        dialog.set_markup(msg)
        dialog.set_transient_for(self.toplevel)
        res = dialog.run()
        dialog.hide()

        res_str = 'ignore'
        if res == 0:
            res_str = 'retry'
        elif res == 2:
            res_str = 'abort'
        else:
            pass
        return res_str

    def preumount_error_func(self,msg):
        dialog = self.build.get_object('umount_error_dialog')

        umount_error_textview = self.build.get_object('umount_error_textview')
        buffer = umount_error_textview.get_buffer()
        buffer.set_text(msg)

        umount_error_expander = self.build.get_object('umount_error_expander')
        umount_error_expander.set_expanded(False)

        dialog.set_transient_for(self.toplevel)
        res = dialog.run()
        dialog.hide()

        res_str = 'abort'
        if res == 0:
            res_str = 'retry'
        elif res == 1:
            res_str = 'ignore'
        else:
            pass
        return res_str

    def ignore_umount_error_func(self,msg):
        return 'ignore'

    def postumount_error_func(self,msg):
        return self.ignore_umount_error_func(msg)

    def on_install_error(self,object,error,error_detail):
        log_msg("ERROR:%s:%s" % (object,error))
        dialog = self.build.get_object('install_error_dialog')
        dialog.format_secondary_markup(error)

        install_error_expander = self.build.get_object('install_error_expander')
        install_error_expander.set_expanded(False)

        install_error_textview = self.build.get_object('install_error_textview')
        buffer = install_error_textview.get_buffer()
        buffer.set_text(error_detail)

        dialog.set_transient_for(self.toplevel)
        dialog.run()
        dialog.hide()
        if self.insenv.is_desktop and self.mf:
            self.mf.fresh_ui(True)
        else:
            self.mf.emit('restart')

    def _install_progress_button_clicked(self,button,mf):
        if mf.is_working:
            obj = button.get_data('work-object')
            if obj:
                obj.set_waiting_when_exit(True)
                if warningbox(self.toplevel,_("Cancel ?"),_("Are you sure to cancel this installation ?")):
                    obj.cancel()
                obj.set_waiting_when_exit(False)
        elif self.install_progress_button.get_data('install'):
            self.mf.emit("restart")
        else:
            self.mf.emit("simple-quit")

    def _restart_later_button_clicked(self,button,mf):
        self.mf.emit("simple-quit")

    def _install_button_clicked(self,button):
        go_install = False
        if self.insenv.use_wubi:
            go_install = True
        elif self.check_can_go_install():
            go_install = True

        if not go_install:
            return

        self.install_info_pad.add(self.install_view)

        self.mf.hide()
        self.mf.is_working = True
        self.install_view.set_installing()
        self.mf.switch_to(self.installbox)
        self.mf.toplevel.set_size_request(795,552)
        self.mf.walk_install()
#        self.mf.go_install()

    def _cancel_button_clicked(self,button,mf):
        if warningbox(self.toplevel,_("Cancel Installation ?"),_("The program will quit.")):
            if self.insenv.is_desktop:
                self.mf.emit("simple-quit")
            else:
                self.mf.emit("restart")

    def check_can_go_install(self):

        if not self.pu.radio_box.get_sensitive():
            return False

        if len(self.mf.ahl.username) <1:
            self.ahlu.account_error(_("username is empty"))
            return False

        if len(self.mf.ahl.hostname) <1:
            self.ahlu.account_error(_("hostname is empty"))
            return False

        if len(self.mf.ahl.password) <1:
            self.ahlu.account_error(_("password is empty"))
            return False

        if self.mf.ahl.password != self.ahlu.passwd_confirm_entry.get_text():
            self.ahlu.account_error(_("Confirm failed!"))
            return False

        if not self.pu.has_root():
            if self.pu.pm.use_auto_parted and not self.pu.pm.use_entire_disk:
                pass
            else:
                errorbox(self.toplevel,_('Please configure "/" mountpoint'))
                return False

        if self.pu.pm.use_auto_parted:
            if self.pu.pm.use_entire_disk:
                if not self.mf._autoinstall:
                    return warningbox(self.toplevel,_("LOST of DATA"),_("Any partition(s) and file(s) on the disk '%s' will be deleted") % self.pu.pm.current_device.path)
            elif self.pu.pm.auto_part and self.pu.pm.auto_part_replace_mode:
                return warningbox(self.toplevel,_("LOST of DATA"),_("Files on partition '%s' will be deleted") % self.pu.pm.auto_part.path)
            elif self.pu.pm.auto_part is None:
                errorbox(self.toplevel,_('No automatically option'))
                return False
        elif self.pu.pm.efi_mode:
            if self.pu.check_efi_partition():
                self.pu.add_efi_partition_mountpoint()
            else:
                return False
        else:
            return self.pu.check_bois_grub_partition()

        return True

    @property
    def mainbox(self):
        return self.build.get_object('main_ui_box')

    @property
    def installbox(self):
        return self.install_box

    def set_locale_tzone_kbd(self,ltz):
        self.ltzu = LocaleTZoneUI(ltz,self.insenv,self.build)

    def set_account_host_login(self,ahl):
        try:
            del self.ahlu.widget
        except:pass
        self.ahlu = AccountHostUI(ahl,self.insenv,self.build)

    def set_part_man(self,pm):
        self.pu = PartUI(self.insenv,pm)
        self.part_man.add(self.pu.widget)
        self.pu.load_devices()
        self.pu.diskbox_load_device()
        self.pu.reload()

    @property
    def toplevel(self):
        widget_list = [self.installbox,self.mainbox]
        for wid in widget_list:
            top = wid.get_toplevel()
            if (top.flags() & gtk.TOPLEVEL) == gtk.TOPLEVEL:
                return top
        return None

    def set_mainframe(self,mf,reset=False):
        self.mf = mf

        if reset:
            mf.ahl.password = ""
            mf.ahl.confirm_password = ""
            mf.pm.load_devices()

        self.set_locale_tzone_kbd(mf.ltz)
        self.set_account_host_login(mf.ahl)
        self.set_part_man(mf.pm)

        self.mf.cf.copy_error_func = self.copy_error_func

        if self.mf.ignore_mount_error:
            self.mf.preum.umount_error_func = self.ignore_umount_error_func
        else:
            self.mf.preum.umount_error_func = self.preumount_error_func

        self.mf.postum.umount_error_func = self.postumount_error_func

        self.install_button.connect('clicked',self._install_button_clicked)
        self.install_progress_button.connect('clicked',self._install_progress_button_clicked,mf)
        self.restart_later_button.connect('clicked',self._restart_later_button_clicked,mf)
        self.cancel_button.connect('clicked',self._cancel_button_clicked,mf)
        self.mf.switch_to(self.mainbox)
        self.mf.toplevel.set_size_request(-1,-1)


class MainFrameMod(gtk.Alignment):

    __gsignals__ = {"quit": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,()),
                    "simple-quit":(gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,()),
                    "restart":(gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,())
                    }

    def __init__(self,insenv=None):

        super(MainFrameMod,self).__init__(xalign=0.5, yalign=0.5, xscale=1.0, yscale=1.0)
        self._title = N_('Wellcome to StartOS')
        if insenv == None:
            self.insenv = installerenv.InstallerEnv()
        else:
            self.insenv = insenv

        self.bg_file = self.insenv.datadir+'/gtkrc/main_pixmap_bg.png'

        self.is_working = False

        self._bg_im = None
        self._window = gtk.Window()
        self.toplevel.set_app_paintable(True)

        self.title_bar_event = gtk.EventBox()
        self.title_bar = gtk.Label("")
        self.title_bar.set_alignment(0.5,0.5)
#        self.title_bar.set_name("titlebar1")
        self.title_bar_event.set_name("titlebar_event")
        self.title_bar_event.add(self.title_bar)
        self.title_bar_event.set_visible_window(False)
#        self.title_bar.connect("expose-event",self._do_titlebar_expose)

        self.pad = gtk.EventBox()

        vbox = gtk.VBox()
        vbox.pack_start(self.title_bar_event,expand=False,fill=False)
        self.pad.set_visible_window(False)
        vbox.pack_start(self.pad)
        vbox.show()
        self.pad.show()
        self.title_bar_event.show_all()
        self.add(vbox)

        self.mountm = MountMod(self.insenv)
        self.preinst = PreInstall(self.insenv,self.mountm)     ## preinstall,mount target filesystem
        self.mps     = MountProcfs(self.insenv,self.mountm)
        self.postinst = PostInstall(self.insenv,self.mountm)   ## postinstall

        self.preum = UmountInstall(self.insenv,self.mountm)    ###umount filesystem
        self.postum = UmountInstall(self.insenv,self.mountm)   ###umount filesystem
        self.ltz = LocaleTZone(self.insenv)                    ##locale tzone console
        self.cf  = CopyFile(self.insenv)                       ##copyfile
        try:
            self.pm = PartMan()                                    #partman
        except:
            errorbox(self.toplevel,error_msg())
            self._on_quit(self,False)
        self.ahl = AccountHost(self.insenv)                    ##user things
        self.ckit = None

        if self.cf.total_size > 2:
            self.pm.set_root_size(self.cf.total_size*1.1)

        self.wubi = None
        self.uiframe = None
        self.ignore_mount_error = False

        self.toplevel.connect("delete-event",self._on_window_delete_event)
        self.connect("quit",self._on_quit)
        self.connect("simple-quit",self._on_simple_quit)
        self.connect("restart",self._on_restart_computer)

        self.title_bar_event.connect('button-press-event',self._title_bar_button_press_event)

        self.toplevel.set_decorated(False)
        self.connect('size-allocate',self._on_size_allocate)
        self.connect('expose-event',self._do_expose_event)
        self.toplevel.set_resizable(False)
        self.toplevel.set_position(gtk.WIN_POS_CENTER_ALWAYS)

        self.work_objects = []

        self.toplevel.set_keep_above(True)
        self._autorestart = False
        self._autoinstall = False
        self._is_installed = False
        self.toplevel.add(self)

    @property
    def toplevel(self):
        return self._window

    @property
    def autorestart(self):
        return self._autorestart

    def set_title(self,title):
        self.toplevel.set_title(title)

    def present(self):
        self.toplevel.present()

    def begin_move_drag(self,bt,x,y,event_time):
        self.toplevel.begin_move_drag(bt,x,y,event_time)

    def set_focus(self,_focus):
        self.toplevel.set_focus(_focus)

    def _on_window_delete_event(self,window,event):
        self.emit("quit")
        return True

    def _title_bar_button_press_event(self,widget,event):
        if event.button != 1:
            return False;

        if not self.insenv.is_desktop:
            return False

        self.begin_move_drag(event.button,int(event.x_root),int(event.y_root),event.time)
        return True

    def _on_locale_changed(self,object):
#        os.system('locale')
        self.fresh_ui()
        pass

    def use_preconfig(self):
        if not self.preconfig.use_preconfig:
            return
        if self.preconfig.has_key('lang'):
            self.ltz.configure_by_locale(self.preconfig['lang'])
        if self.preconfig.has_key('tzone'):
            self.ltz.tzone = self.preconfig['tzone']
        if self.preconfig.has_key('kbd'):
            self.ltz.set_keyboard(self.preconfig['kbd'])

        if self.preconfig.has_key('user'):
            self.ahl.username = self.preconfig['user']
        if self.ahl.username and self.preconfig.has_key('password'):
            self.ahl.password = self.preconfig['password']
            self.ahl.confirm_password = self.preconfig['password']
        if self.ahl.username and self.preconfig.has_key('hostname'):
            self.ahl.hostname = self.preconfig['hostname']
        if self.preconfig.has_key('encrypted-password'):
            self.ahl.encrypted_password = self.preconfig['encrypted-password']

        if self.preconfig.has_key('logintype'):
            self.ahl.login_type = int(self.preconfig['logintype'])

        if self.pm.efi_mode:
            self.pm.is_bldr_to_partition = False
        else:
            self.pm.is_bldr_to_partition = self.preconfig.get_key_true('bldr_to_root_disk')

        self.pm.use_auto_parted = self.preconfig.get_key_false('use_auto_parted')
        entire_disk = self.preconfig.get('use_entire_disk')
        has_set_current_device = False
        if self.pm.use_auto_parted and entire_disk and os.path.exists(entire_disk):
            self.pm.set_current_device_by_path(entire_disk)
            self.pm.auto_parted_use_entire_disk = entire_disk
            has_set_current_device = True
        elif  self.preconfig.has_key('root'):
            root=self.preconfig['root']
            root_fstype = ""
            root_formating= self.preconfig.get_key_true('root_formating')
            if root_formating and self.preconfig.has_key('root_fstype'):
                root_fstype = self.preconfig['root_fstype']
            self.pm.set_preroot(root,root_fstype,root_formating)
            has_set_current_device = True

        self.pm.is_install_bldr = self.preconfig.get_key_false('install_bootloader')
        if self.pm.is_install_bldr and self.preconfig.has_key('bootloader_device'):
            self.pm.boot_dev = self.preconfig['bootloader_device']
            if not has_set_current_device and self.pm.boot_dev and os.path.exists(self.pm.boot_dev):
                self.pm.set_current_device_by_path(self.pm.boot_dev)

        self.pm.quickly_mode = self.preconfig.get_key_true('quickly_mode')
        self.ignore_mount_error = self.preconfig.get_key_true('ignore_mount_error')
        self._autorestart = self.preconfig.autorestart

    def save_preconfig(self):
        try:
            if not self.insenv.use_wubi:
                self.preconfig.save_preconfig(self)
        except:pass

    def _fresh_ui(self,reset):
        uiframe = MainUIFrame(self.insenv)
        uiframe.set_mainframe(self,reset)
        title = _(self._title)
        self.set_title(title)
#        self.title_bar.set_markup('<span font="14" size="x-large" color="white">%s</span>' % title)
        self.title_bar.set_markup('<span size="x-large" color="white">%s</span>' % title)
        try:
            del self.uiframe.install_view
            del self.uiframe
        except:pass
        self.uiframe = uiframe

    def fresh_ui(self,reset=False):
        self._idle_refresh_ui(reset)

    def _idle_refresh_ui(self,reset):
        self._fresh_ui(reset)
        self.present()
        self.queue_resize()
        return False

    def idle_fresh_ui(self,reset=False):
        self.hide()
        glib.idle_add(self._idle_refresh_ui,reset)

    def switch_to(self,widget):
        child = self.pad.get_child()
        if child is widget:
            return
        if child:
            self.pad.remove(child)
        self.pad.add(widget)
        try:
            toplevel = self.pad.get_toplevel()
        except:
            toplevel = self.pad
        toplevel.queue_resize()
        self.show_all()

    def _paint_bg(self,widget,rect,bg_file=None,bg_im=None,expandx=True,expandy=True):
        if bg_im == None and bg_file:
            bg_im = cairo.ImageSurface.create_from_png(bg_file)
        if bg_im == None:
            return

        cr = widget.get_window().cairo_create()
        scx = 1.0
        scy = 1.0

        if expandx and rect.width != bg_im.get_width():
            scx = rect.width*1.0 / bg_im.get_width()

        if expandy and rect.height != bg_im.get_height():
            scy = rect.height*1.0/bg_im.get_height()

        cr.rectangle(rect.x,rect.y,rect.width,rect.height)
        cr.clip()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        if expandx or expandy:
            cr.scale(scx,scy)

        cr.set_source_surface(bg_im)
        cr.paint()

    def set_window_bg(self,bg_file):
        window = self
        self._bg_im = cairo.ImageSurface.create_from_png(bg_file)

    def _do_titlebar_expose(self,widget,event):
        if self.is_composited():
            alc = widget.get_allocation()
            self._paint_bg(widget,alc,bg_file=self.insenv.datadir+'/gtkrc/titlebar_bg.png')
        return False

    def do_size_request(self,req):
        gtk.Window.do_size_request(self,req)
        if self._bg_im:
            if req.width < self._bg_im.get_width():
                req.width = self._bg_im.get_width()
            if req.height < self._bg_im.get_height():
                req.height = self._bg_im.get_height()

    def _on_size_allocate(self,widget,allocate):
        self.set_window_bg(self.bg_file)

    def _do_expose_event(self,widget,event):
        alc = widget.get_allocation()
        self._paint_bg(widget,alc,bg_im=self._bg_im)
        return False

    def _on_work_progress(self,obj,progress,details,user_data):
        (i,step,steps) = user_data
        prog = (i*progress + step)/steps
        bar_text = '%.2lf%%' % (prog*100)
        if details:
            log_msg("%s:%f(%f)->%s" % (obj,progress,prog,details))
        try:
            if prog <= 0.99:
                self.uiframe.install_view.set_progress(prog,details)
        except:
            pass

    def _on_work_cancel(self,object):
        if self.insenv.is_desktop:
            ##MountMod.umount_all()
            self.pm.load_devices()
            self.fresh_ui(reset=True)
        else:
            self.emit('restart')
        log_msg("%s:Cancel" % (object))

    def _on_abort_error(self,object,error,*args,**kwarg):
        errorbox(self.toplevel,error)
        if self.insenv.is_desktop:
            self.emit('simple-quit')
        else:
            self.emit('restart')

    def walk_install(self):
        class JobsThread(GOBjectThreadMod):
            def __init__(self,mf):
                super(JobsThread,self).__init__()
                self.mf = mf
                self.connect('started',self._on_job_started)

            def _on_job_started(self,object):
                self.mf.present()

            def is_ok(self):
                return self._res_state

            def run(self):
                try:
                    self.emit_signal("started")
                    self._run()
                except:
                    self.emit_signal("error",error_msg(),exception_msg())
                finally:
                    log_msg("umount all filesystem");
                    try:
                        self.mf.postum.go()
                    except:pass
                    log_msg("umount done");
                    if self._cancel:
                        self.emit_signal("cancel")
                    self.emit_signal("finished",self._res_state)

            def _run(self):
                steps = 0
                for (obj,i) in self.mf.work_objects:
                    steps += i

                step = 0
                for (obj,i) in self.mf.work_objects:
                    sigs = []
                    self.mf.uiframe.install_progress_button.set_sensitive(obj.can_cancel and self.mf.insenv.is_desktop)
                    self.mf.uiframe.install_progress_button.set_data('work-object',obj)
                    sigs.append((obj,obj.connect('progress',self.mf._on_work_progress,(i,step,steps))))
                    res = obj.walk()
                    for (o,id) in sigs:
                        o.disconnect(id)
                    if not res:
                        break
                    step += i
                self._res_state = bool(step == steps)

        self.uiframe.install_progress_button.set_sensitive(False)
        self.uiframe.install_progress_button.set_label(gtk.STOCK_CANCEL)
        self.uiframe.restart_later_button.hide()
        self.uiframe.install_progressbar.show()

        jt = JobsThread(self)
        jt.connect("finished",self._on_finished)
        jt.connect('error',self._on_install_error)
        jt.connect('cancel',self._on_work_cancel)

        try:
            _pm = None
            if self.insenv.use_wubi:
                self.ahl.set_from_wubi(self.wubi)
                self.cf.set_use_extract(self.wubi.quickly_mode)
                os.environ['USEWUBI']='1'
                ds = []
                (formating_list,mplist) = (self.wubi.formating_list,self.wubi.mplist)
                self.postinst.setboot(self.wubi.boot_dev)
            else:
                try:
                    os.unsetenv('USEWUBI')
                except:pass
                ds = self.uiframe.pu.get_disks()
                (formating_list,mplist) = self.pm.get_changes(ds)
                if self.pm.use_auto_parted:
                    if not self.pm.use_entire_disk:
                        _pm = self.pm
                if self.pm.is_install_bldr:
                    self.postinst.setboot(self.pm.boot_dev)
                    self.uiframe.pu.check_bootflag_and_fix(ds,(formating_list,mplist))
                else:
                    self.postinst.setboot(None)

                if self.pm.is_bldr_to_partition:
                    self.postinst.boot_partition = self.pm.bldr_partition
                else:
                    self.postinst.boot_partition = None

                self.cf.set_use_extract(self.pm.quickly_mode)

            os.environ['TARGETDIR'] = self.insenv.target
            os.environ['INS_USERNAME'] = self.ahl.username

            self.mountm.set_mplist(mplist)
            commit = PartCommit(ds,formating_list,pm=_pm,mountm=self.mountm)
            if not self.work_objects:
                self.work_objects.append((self.preum,1))
                self.commit_index = len(self.work_objects)
                self.work_objects.append((None,2))
                self.work_objects.append((self.preinst,1))
                self.work_objects.append((self.cf,20))
                self.work_objects.append((self.mps,1))
                self.work_objects.append((self.ahl,1))
                self.work_objects.append((self.ltz,1))

                self.work_objects.append((self.postinst,1))
                for (obj,i) in self.work_objects:
                    if not obj:
                        continue
                    obj.connect('error',self._on_install_error)
                    obj.connect('abort',self._on_abort_error)
                    obj.connect('cancel',self._on_job_thread_cancel,jt)

            self.work_objects[self.commit_index] = (commit,2)

            commit.connect('error',self._on_install_error)
            commit.connect('abort',self._on_abort_error)
            commit.connect('cancel',self._on_job_thread_cancel,jt)
            jt.go(wait=False)

        except:
            errorbox(self,exception_msg())
            if self.insenv.is_desktop:
                self.emit('simple-quit')
            else:
                self.emit('restart')

    def _on_job_thread_cancel(self,object,jt):
        self.uiframe.install_progress_button.set_sensitive(False)
        jt.cancel()

    def _on_install_error(self,object,error,error_detail,*args,**kwarg):
        self.uiframe.on_install_error(object,error,error_detail)

    def _on_finished(self,obj,is_ok):
        log_msg("finishing")
        self.uiframe.install_progress_button.set_sensitive(False)
        self.is_working = False
        try:
            self.js.is_working = self.is_working
        except:
            pass
        self.uiframe.install_progress_button.set_sensitive(True)
        self.uiframe.install_progress_button.set_use_stock(True)
        ####self.uiframe.install_progressbar.hide()
        if is_ok:
#            self.uiframe.progress_label.set_markup(_("Complete"))
            self.uiframe.install_progress_button.set_label(_("_Reboot"))
            if self.insenv.is_desktop:
                self.uiframe.restart_later_button.show()
                self.uiframe.set_widget_same_size(self.uiframe.install_progress_button,self.uiframe.restart_later_button)
            self.uiframe.install_view.set_success()
            self.uiframe.install_view.set_disable_mouse()
            self.uiframe.install_progress_button.set_data('install',True)
            self._is_installed = True
        else:
            self.uiframe.install_progress_button.set_label(gtk.STOCK_QUIT)
            self.uiframe.install_progress_button.set_data('install',False)
#            self.uiframe.progress_label.set_markup(_("Installation aborted or cancel"))
            self._is_installed = False
            try:
                self.uiframe.install_view.set_failed()
            except:pass
        #self.uiframe.install_progress_button.grab_default()
        self.set_focus(self.uiframe.install_progress_button)
        self.present()
        if self._is_installed:
            self.save_preconfig()
            if self.autorestart:
                self.emit('quit')

    def _on_quit(self,object,confirm=True):
        if self.is_working:
            warningbox(self.toplevel,_("Busying"),_("Program is busying !"),cancel=False)
            return
        if not self._is_installed and confirm and not warningbox(self.toplevel,_("Exit"),_("Are you sure to exit ?")):
            return
        if self.insenv.is_desktop and not self.autorestart:
            self._on_simple_quit(object)
        else:
            self._on_restart_computer(object)

    def _on_simple_quit(self,object):
        try:
            gtk.main_quit()
        except:
            sys.exit(1)

    def _on_restart_computer(self,object):
        if self.ckit == None:
            self.ckit = Consolekit()
        self.ckit.restart()
        self._on_simple_quit(object)

    def action_auto_install(self):
        can_clicked = False
        if self.insenv.use_wubi:
            can_clicked = True
        else:
            can_clicked = self.uiframe.pu.radio_box.get_sensitive()
        if can_clicked:
            self.uiframe.install_button.clicked()
            self._autoinstall = False
        return (not can_clicked)

    def run(self,args=None):
        self.title_bar.set_size_request(-1,43)

#        self._on_size_allocate(self,None)
        can_autoinstall = False
        config = self.insenv.confdir+'/preconfig'

        if args.has_key('preconfig') and len(args['preconfig']) > 0:
            config = args['preconfig']

        self.preconfig = PreConfig(config)

        if args != None :
            if args.has_key('wubi-dir') and os.path.isdir(args['wubi-dir']):
                self.insenv.set_usewubi(True)
                self.ignore_mount_error = True
                self.wubi = WubiConfig(args)
                can_autoinstall = True
                self.preconfig.set_readonly()
                self._autorestart = self.preconfig.get_key_false('wubi_autorestart')

        if not self.insenv.use_wubi:
            try:
                self.use_preconfig()
                can_autoinstall = self.preconfig.autoinstall
            except:
                self.preconfig['root'] = None
                raise
            if not self.insenv.is_desktop:
                ###如果autorestart没有禁止自动重启,则nodesktop时自动重启
                self._autorestart = self.preconfig.get_key_false('autorestart')

        self.fresh_ui()
        self.ltz.connect("locale-changed",self._on_locale_changed)
##        self.pm.auto_parted_use_entire_disk = None
        if can_autoinstall:
            self._autoinstall = True
            glib.timeout_add(300,self.action_auto_install)

        gtk.main()

gobject.type_register(MainFrameMod)

if '__main__' == __name__:
    def timeout_func(obj):
        mfm.fresh_ui()
        return True
    #gtk.rc_parse('Luna/gtk-2.0/gtkrc')
    gtk.rc_parse('gtkrc/gtkrc')
    win =gtk.Window()
    glib.threads_init()
    mfm = MainUIFrame(insenv)
    win.add(mfm.install_box)
    mfm.install_progressbar.set_fraction(0.50)
    mfm.install_progress_button.set_sensitive(True)
    #glib.timeout_add(1000*5,timeout_func,mfm)
    label = gtk.Label("\n\nHello,World !\n\n")
    mfm.install_info_pad.add(label)
    label.show()
    win.show()
    print mfm.install_info_pad.path()
    gtk.main()
