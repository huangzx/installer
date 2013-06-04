#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  未命名.py
#  
#  Copyright 2012 weiketing <weikting@gmail.com>
#  

import os
import gtk
import cairo


class bgwidget(gtk.Window):

    def __init__(self,bgfile='/usr/share/osinstaller/installbg.png'):
        super(bgwidget,self).__init__()
        self._bgfile=bgfile
        self.set_redraw_on_allocate(True)
        self.toplevel.set_skip_pager_hint(True);
        self.toplevel.set_skip_taskbar_hint(True)
#        self.toplevel.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DESKTOP)
        self.toplevel.set_deletable(False)
        self.toplevel.set_keep_below(True)
        self.toplevel.set_app_paintable(True)
        self._bgwidget = gtk.Alignment(0.5,0.5,1.0,1.0);
        self.add(self._bgwidget)
        self._bgwidget.connect("expose-event",self._on_bg_expose)
        self.fullscreen()
        self._bgwidget.show()

    @property
    def toplevel(self):
        return self.get_toplevel()

    def _on_bg_expose(self,widget,event):
        try:
            alc  = widget.allocation
            cr = self.get_window().cairo_create();
            bg_im = cairo.ImageSurface.create_from_png(self._bgfile)
            w = bg_im.get_width()
            h = bg_im.get_height()
            cr.scale(alc.width*1.0/w,alc.height*1.0/h)
            cr.set_source_surface(bg_im)
            cr.paint()
        except:pass

def main():
    bg = bgwidget('/usr/share/osinstaller/gtkrc/installing_bg.png')
    bg.show_all()
    bg.connect("destroy",gtk.main_quit)
    gtk.main()
    return 0

if __name__ == '__main__':
	main()

