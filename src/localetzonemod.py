# -*- coding: utf-8; Mode: Python; indent-tabs-mode: nil; tab-width: 4 -*-
# localetzonemod.py
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

from misc import *
from localetzonemap import *

_supported_locales = None

####copy from ubiquity by wkt
def get_supported_locales():
    """Returns a list of all locales supported by the installation system."""
    global _supported_locales
    if _supported_locales == None:
        _supported_locales = {}
        supported = open('/usr/share/i18n/SUPPORTED')

        for line in supported:
            (locale, charset) = line.strip().split(None, 1)
            _supported_locales[locale] = charset
        supported.close()
    return _supported_locales
###copy end


class LocaleTZone(GOBjectThreadMod):

    __gsignals__ = {
                    "tzone-changed": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,()),
                    "locale-changed": (gobject.SIGNAL_RUN_FIRST,gobject.TYPE_NONE,()),
                    }

    def __init__(self,insenv=None):
        GOBjectThreadMod.__init__(self)
        self.insenv = insenv
        self.langlist = LangList
        self.tzones = TZones
        self.locales = get_supported_locales()
        self._lang = 'C' ## zh_CN.utf-8 self._lang = '中文'
        self._kbd = 'us'
        self._zone = 'Asia/Chongqing'
        self._area = 'CN'
        self._locale = 'C'
        self.init()


    def ___str__(self):
        s = "\nlang:%s\narea:%s\ntzone:%s\nlocale:%s\nkbd:%s\n" % (self._lang,self.get_area(),self.tzone,self.locale,self.keyboard)
        return s

    def configure_by_locale(self,locale_str,do_emit=True):
        if locale_str.lower() == 'posix':
            locale_str = 'C'
        (self._lang,self._locale,self._zone) = self.parser_locale(locale_str)
        if do_emit:
            self.update_kbd_follow_zone()
            self.detect_locale()
#        print str(self)+"\n---configure"

    def parser_locale(self,locale_str,level=0):
        l_a = locale_str
        if '.' in locale_str:
            l_a = locale_str.split('.',1)[0]
        res_l = 'C'
        res_zone = 'GMT'
        for ll in self.langlist:
            (l,value)=ll.items()[0]
            if value[0][0].startswith(l_a):
                try:
                    res_zone=value[1]
                except:pass
                res_l = l
                l_a = value[0][0]
                break
        if res_l == 'C':
            l_a = 'C'
        return (res_l,l_a,res_zone)

    def get_charset(self,locale):
        lv = locale.split('.',1)
        if len(lv) < 2:
            lv.append("")
        else:
            lv[1] = '.'+lv[1]
            lv[1] = lv[1].upper()
            if lv[1] == '.UTF8':
                lv[1] = '.UTF-8'
        return self.locales[lv[0]+lv[1]]

    def init(self):
        try:
            locale_str = os.environ['LANG']
        except:
            locale_str = 'C'
        self.configure_by_locale(locale_str)

    def set_lang(self,lang):
        for ll in self.langlist:
#            print ll
            if ll.has_key(lang):
                self._locale =ll[lang][0][0]
                break
        self.update_follow_locale()
        self.detect_locale()

    def update_follow_locale(self):
        (self._lang,_locale,self._zone) = self.parser_locale(self._locale)
        self.update_kbd_follow_zone()


    def detect_locale(self):
        try:
            locale_str = os.environ['LANG']
        except:
            locale_str = "C"

        os.environ['LANG'] = self.locale
        os.environ['LANGUAGE']=self.locale.split('.')[0]
        try:
            import gettext
            gettext.install(self.insenv.pkgname,self.insenv.localedir)
        except:pass

#        print locale_str,self.locale+' -----detect_locale'
        if locale_str != self.locale:
            self.emit("locale-changed")

    def get_locale(self):
        return self._locale

    def set_locale(self,_locale):
        (self._lang,self._locale,_zone) = self.parser_locale(_locale)

    locale = property(get_locale,set_locale)

    @property
    def all_locales(self):
        lls = ['ISO-8859-1']
        for ll in self.langlist:
            if ll.has_key(self._lang):
                lls = ll[self._lang][0]
                break
        return lls

    def update_kbd_follow_zone(self):
        self._kbd = self.get_keyboard_for_area(self.get_area())

    def get_tzone(self):
        return self._zone

    def set_tzone(self,_zone):
        is_find = False
        for vv in self.tzones.values():
            if _zone in vv.keys():
                is_find = True
                break
        if not is_find:
            self.tzones['Myadd']={}
            self.tzones['Myadd'][_zone]=_zone
        self._zone = _zone

    tzone = property(get_tzone,set_tzone)

    def get_area(self):
        area = None
        for (a,av) in self.tzones.items():
            if av.has_key(self.tzone):
                area = a
        if area == None:
            ll = self.locale.split('.',1)[0]
            if '_' in ll:
                area = ll.split('_',1)[1]
        if area == None:
            area = 'CN'
        return area

    def get_keyboard_for_area(self,area):
        area = area.lower()
        kbds = self.get_keyboards()
        _kbd = None
        for (ar,v) in kbds.items():
            for (kv,vv) in v.items():
                if ar == area:
                    if not vv or len(vv) < 1:
                        vv = ar
                        _kbd = vv
                    if _kbd == None:
                        _kbd = vv
                    if vv == self.keyboard:
                        _kbd = vv
                        break
            if _kbd:
                break
        if _kbd == None:
            _kbd='us'
        return _kbd

    def get_keyboards(self):
        import keyboard_names
        try:
            c=os.environ['LANG'].split('.')[0]
        except:
            c="C"
        if not keyboard_names.lang.has_key(c):
            c='C'
        variants = keyboard_names.lang[c]['variants']
        return variants

    @property
    def keyboard(self):
        return self._kbd

    def set_keyboard(self,kbd):
        self._kbd = kbd

    def write_tzone(self):
        if self.insenv:
            target = self.insenv.target
        else:
            target = "/tmp"
        try:
            w=open(target+'/etc/timezone','w')
            w.write(self.tzone)
            w.close()
        except:
            log_msg(error_msg())
            raise

        try:
            try:
                os.remove(target+'/etc/localtime')
            except:pass
            os.symlink('/usr/share/zoneinfo/'+self.tzone,target+'/etc/localtime')
        except:
            log_msg(error_msg())
            raise

        try:
            s='TMPTIME=0\nSULOGIN=no\nDELAYLOGIN=no\nUTC=no\nVERBOSE=no\nFSCKFIX=no\n'
            w = open(target+'/etc/default/rcS','w')
            w.write(s)
            w.close()
        except:
            log_msg(error_msg())
            raise

    def write_console(self):
        if self.insenv:
            target = self.insenv.target
        else:
            target ='/tmp'
        con= target+'/etc/default/console-setup'
        str='VERBOSE_OUTPUT=no\n'\
            'ACTIVE_CONSOLES="/dev/tty[1-6]"\n'\
            'CHARMAP="UTF-8"\n'\
            'CODESET="Uni1"\n'\
            'FONTFACE="Fixed"\n'\
            'FONTSIZE="16"\n'\
            'XKBMODEL="pc105"\n'\
            'XKBLAYOUT="%s"\n'\
            'XKBVARIANT=""\n'\
            'XKBOPTIONS=""\n' % self.keyboard
        try:
            w=open(con,'w')
            w.write(str)
            w.close()
        except:
            log_msg(error_msg())
            raise

    def write_locale(self):
        if self.insenv:
            target = self.insenv.target
        else:
            target ='/tmp'
        envfile=target+'/etc/default/locale'
        if not os.path.exists(envfile):
            os.system('touch '+envfile)
        os.system('sed -i /LANG.*=/d '+envfile)
        os.system('echo LANG='+self.locale+' >>'+envfile)

        for l in self.all_locales:
            cmd='chroot %s localedef -f %s -i %s %s' % (target,self.get_charset(l),l.split('.',1)[0],l)
            log_msg(cmd)
            os.system(cmd)

    def _run(self):
        self.emit_signal('started')
        res = True
        try:
            cmds=[
                  (self.write_locale,_("Configuring locales ...")),
                  (self.write_tzone,_("Configuring timezone...")),
                  (self.write_console,_("Configuring console ..."))
                 ]

            l = len(cmds)
            i = 0.0
            for cmd in cmds:
                self.emit_signal("progress",i/l,cmd[1])
                cmd[0]()
                i += 1
                self.emit_signal("progress",i/l,"")
        except:
            res = False
            self.emit_signal('error',error_msg(),exception_msg())
        self._res_state = res
        self.emit_signal("finished",res)

    def run(self):
        self._run()

class LocaleTZoneUI(gobject.GObject):

    import gtk
    
    def __init__(self,ltz,insenv=None,build = None):

        self._ltz = ltz

        ui_file = '../data/localetzone_ui.glade'

        if build == None:
            build = gtk.Builder()
            build.add_from_file(ui_file)

        if insenv:
            build.set_translation_domain(insenv.pkgname)
            ui_file=insenv.datadir+'/localetzone_ui.glade'

        self.build  = build

        self.lang_box = build.get_object('lang_box')
        self.tzone_box = build.get_object('tzone_box')
        self.kbd_box = build.get_object('kbd_box')

        self.lang_box_init()
        self.tzone_box_init()
        self.kbd_box_init()

        self.load_lang()
        self.load_tzone()
        self.load_kbd()

        self.kbd_box.connect('changed',self._on_kbd_box_changed)
        self.tzone_box.connect('changed',self._on_tzone_box_changed)
        self.lang_box.connect("changed",self._on_lang_box_changed)

    def lang_box_init(self):
        model = gtk.ListStore(gobject.TYPE_STRING, ##display name
                              gobject.TYPE_STRING  ##lang code
                              )
        self.lang_box.set_model(model)
        cell = gtk.CellRendererText()
        self.lang_box.pack_start(cell)
        self.lang_box.set_attributes(cell,text=0)

    def tzone_box_init(self):
        model = gtk.ListStore(gobject.TYPE_STRING,###display text for tzone
                              gobject.TYPE_STRING,###ara code to tzone
                              gobject.TYPE_STRING,###key to tzone
                              )
        self.tzone_box.set_model(model)
        cell = gtk.CellRendererText()
        self.tzone_box.pack_start(cell)
        self.tzone_box.set_attributes(cell,text=0)

    def kbd_box_init(self):
        model = gtk.ListStore(gobject.TYPE_STRING,###display text for tzone
                              gobject.TYPE_STRING,###code for keyboard
                              )
        self.kbd_box.set_model(model)
        cell = gtk.CellRendererText()
        self.kbd_box.pack_start(cell)
        self.kbd_box.set_attributes(cell,text=0)

    def load_lang(self):
        model = self.lang_box.get_model()
        aiter = None
        model.clear()
#        print self.localetzone
        for v in self.localetzone.langlist:
            #print v
            (kv,vv) = v.items()[0]
            iter = model.append()
            model.set(iter,0,kv,1,vv[0])
            if aiter == None:
                aiter = iter
#            print self.localetzone._lang ,kv
            if self.localetzone._lang == kv:
                aiter = iter
        if aiter:
            self.lang_box.set_active_iter(aiter)

    def load_tzone(self):
        model = self.tzone_box.get_model()
        aiter = None
        miter = None
        area,tzone = self.localetzone.get_area(),self.localetzone.tzone
        model.clear()
        for (k,v) in self.localetzone.tzones.items():
            for (kv,vv) in v.items():
                iter = model.append()
                model.set(iter,0,_(vv),1,k,2,kv)
                if aiter == None:
                    aiter = iter
                if miter == None:
                    if area == k :
                        aiter = iter
                        if kv == tzone:
                            miter = iter
        if aiter:
            self.tzone_box.set_active_iter(aiter)
#        print self.localetzone.tzones

    def load_kbd(self):
        model = self.kbd_box.get_model()
        aiter = None
        miter = None
        kbds = self.localetzone.get_keyboards()
        model.clear()
        for (area,v) in kbds.items():
            for (kv,vv) in v.items():
                iter = model.append()
                if not vv or len(vv) < 1:
                    vv = area
                kv = kv+('(%s)' % vv)
                model.set(iter,0,kv,1,vv)
                if miter == None :
                    if self.localetzone.keyboard == area:
                        if aiter == None:
                            aiter = iter
                        if self.localetzone.keyboard == vv :
                            miter = iter
                            aiter = miter
        if aiter:
            self.kbd_box.set_active_iter(aiter)

    def _on_lang_box_changed(self,cbox):
        model = cbox.get_model()
        iter = cbox.get_active_iter()
        if iter:
            (lang,lc) = model.get(iter,0,1)
            self.localetzone.set_lang(lang)
            self.load_tzone()

    def _on_tzone_box_changed(self,cbox):
        model = cbox.get_model()
        iter = cbox.get_active_iter()
        if iter:
            (area,tz) = model.get(iter,1,2)
#            print area,tz
            self.localetzone.tzone=tz
            self.load_kbd()

    def _on_kbd_box_changed(self,cbox):
        model = cbox.get_model()
        iter = cbox.get_active_iter()
        if iter:
            (kbd,) = model.get(iter,1)
            self.localetzone.set_keyboard(kbd)

    @property
    def localetzone(self):
        return self._ltz

    @property
    def widget(self):
        return self.build.get_object("localetzone_box")

    @property
    def toplevel(self):
        return self.widget.get_toplevel()


if __name__ == '__main__':
    import gtk
    import glib

    glib.threads_init()
    ltz = LocaleTZone()

    def test1():
        win = gtk.Window()
        ltzu = LocaleTZoneUI(ltz)
        win.add(ltzu.widget)
        win.show_all()
        win.connect("destroy",gtk.main_quit)
        gtk.main()

    test1()
    ltz.write_locale()
    ltz.write_tzone()
    ltz.write_console()
    print ltz.all_locales
    print ltz
