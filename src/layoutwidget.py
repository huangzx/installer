#!/usr/bin/env python
# -*- coding: utf-8 -*-
# layoutwidget.py
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
import gtk


class LayoutWidget(gtk.Bin):

    def __init__(self):
        super(LayoutWidget,self).__init__()
        self._label_widget = None
        self._space = 10

    def get_label_widget(self):
        if self._label_widget == None:
            label = gtk.Label("")
            label.show()
            label.set_alignment(0.0,0.5)
            label.set_name('label_widget')
            self.queue_resize()
            self.set_label_widget(label)
        return self._label_widget

    def set_label_widget(self,widget):
        if self._label_widget:
            try:
                self._label_widget.unparent()
            except:
                raise
        self._label_widget = widget
        try:
            self._label_widget.set_parent(self)
        except:pass
        self.queue_resize()

    label_widget = property(get_label_widget,set_label_widget)

    def set_label(self,text):
        self.label_widget.set_label(text)

    def set_markup(self,text):
        self.label_widget.set_markup(text)

    def _get_label_widget_requisition(self):
        return self.label_widget.get_child_requisition()

    def _get_child_allocation(self):
        child_allocation =  gtk.gdk.Rectangle()
        allocation = self.allocation
        label_with,label_height = self._get_label_widget_requisition()
        top_margin = max(self.style.ythickness,(label_height + self._space + self.border_width + self.style.ythickness))
        child_allocation.x = self.border_width + self.style.xthickness
        child_allocation.y = self.border_width + top_margin

        child_allocation.width = max(1, allocation.width - child_allocation.x*2 );
        child_allocation.height = max (1, (allocation.height - child_allocation.y - 2*(self.border_width + self.style.ythickness)))

        child_allocation.x += allocation.x
        child_allocation.y += allocation.y 

        return child_allocation

    def do_size_allocate(self,allocation):
        self.allocation = allocation
        if self.label_widget and self.label_widget.get_visible():
            (label_width,label_height) = self._get_label_widget_requisition()
            label_allocation =  gtk.gdk.Rectangle()
            label_allocation.x = self.border_width + self.style.xthickness
            label_allocation.y = self.border_width + self.style.ythickness
            label_allocation.width = max(1,allocation.width - label_allocation.x * 2)
            label_allocation.height = max (1, label_height)
            label_allocation.x += allocation.x
            label_allocation.y += allocation.y 
            
            self.label_widget.size_allocate(label_allocation)
        else:
            (label_width,label_height) = (0,0)
        if self.child and self.child.get_visible():
            child_allocation =  self._get_child_allocation()
            self.child.size_allocate(child_allocation)

    def do_size_request(self,requisition):
        
        if self.label_widget.get_visible():
            (label_width,label_height) = self.label_widget.size_request()
        else:
            (label_width,label_height) = (0,0)

        requisition.width = label_width
        requisition.height = label_height

        if self.child and self.child.get_visible():
            (child_width,child_height) = self.child.size_request()
        else:
            (child_width,child_height) = (0,0)

        requisition.width = max(requisition.width,child_width)
        requisition.height += (child_height + self._space)

        requisition.width += (self.border_width + self.style.xthickness)*2
        requisition.height += (self.border_width + self.style.ythickness)*3

    def do_forall(self,include_internals,callback,object):
        if self.child:
            callback(self.child,object)
        callback(self.label_widget,object)

    def do_remove(self,widget):
        if self.label_widget == widget:
            pass
        else:
            #S = super(LayoutWidget,self)
            #S.do_remove(self,widget)
            gtk.Bin.do_remove(self,widget)

    def do_expose_event(self,event):
        window = self.get_window()
        
        self.style.paint_box(window,
                                gtk.STATE_NORMAL,
                                gtk.SHADOW_OUT,
                                event.area,
                                self,
                                'layoutwidget',
                                self.allocation.x,self.allocation.y,
                                self.allocation.width,self.allocation.height)

        label_allocation = self.label_widget.allocation

        self.style.paint_box_gap(window,
                                gtk.STATE_NORMAL,
                                gtk.SHADOW_OUT,
                                event.area,
                                self,
                                'layoutwidget',
                                self.allocation.x,self.allocation.y,
                                self.allocation.width,label_allocation.height + (label_allocation.y-self.allocation.y)+self._space/2,
                                gtk.POS_BOTTOM,
                                0,self.allocation.width)
        return gtk.Bin.do_expose_event(self,event)

gobject.type_register(LayoutWidget)

if __name__ == '__main__':
    gtk.rc_parse(sys.argv[1])
    win = gtk.Window()
    lw = LayoutWidget()
    lw.set_markup("<b><big>test</big></b>")
    al = gtk.Alignment(0.5,0.5,1.0,1.0)
    al.set_padding(30,20,30,30)
    l = gtk.Label("jjjjjjjjjjjjjjjjjjjjjjjjj")
    lw.show()
    lw.add(l)
    al.add(lw)
    win.add(al)
    win.show_all()
    print lw.path()
    print lw._get_label_widget_requisition()
    gtk.main()
