#!/usr/bin/env python
# accountmod.py
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

from misc import *


class AccountHost(GOBjectThreadMod):


    def __init__(self,insenv=None):
        GOBjectThreadMod.__init__(self)
        self._illegal_keys=' \t\n\r~`!@#$%^&*()+}{|\\\':;<,>.?/'
        self._username = ""
        self._login_name = ""
        self._hostname = ""
        self._login_type = LOGIN_AUTOMATICALLY
        self._password = ""
        self._confirm_password = ""
        self._encrypted_password = ""
        self.insenv = insenv
        self._steps = 4 ##hostname,username_password,chown,login_type
        self._step = 0.0
        self.is_laptop = (os.system('laptop-detect') == 0)

    def _____str__(self):
        s = "username:%s\nhostname:%s\nlogin_type:%s\n" % (self.username,self.hostname,self.login_type)
        return s

    def _get_systemusers(self):
        fpr = None
        users = []
        try:
            fpr = open(self.insenv.source+'/etc/passwd')
            for l in fpr:
                u = l.split(':',1)[0]
                users.append(u)
        except:
            pass
        finally:
            if fpr:
                fpr.close()
        return users

    def set_password(self,pw):
        self._password = pw

    def get_password(self):
        return self._password

    password = property(get_password,set_password)

    def get_confirm_password(self):
        return self._confirm_password

    def set_confirm_password(self,text):
        self._confirm_password = text

    confirm_password =  property(get_confirm_password,set_confirm_password)

    def get_encrypted_password(self):
        return self._encrypted_password

    def set_encrypted_password(self,password):
        self._encrypted_password = password

    encrypted_password = property(get_encrypted_password,set_encrypted_password)

    def set_username(self,name):
        if name:
            if name in self._get_systemusers():
                raise UsernameException(_('"%s" has been used as a system user') % name)
            for d in self._illegal_keys:
                if d in name:
                    raise UsernameException(_('username can\'t contain "%s"') % d)
                    break
        self._username = name

    def get_username(self):
        return self._username

    username = property(get_username,set_username)

    def set_login_name(self,name):
        self._login_name = name

    def get_login_name(self):
        return self._login_name

    login_name = property(get_login_name,set_login_name)

    def set_hostname(self,hostname):
        self._hostname=hostname

    def get_hostname(self):
        return self._hostname

    hostname = property(get_hostname,set_hostname)

    def get_login_type(self):
        return self._login_type

    def set_login_type(self,type):
        self._login_type = type

    login_type = property(get_login_type,set_login_type)

    def set_gdm_autologin(self):
        mf='/etc/gdm/custom.conf'
        if not os.path.exists(mf):
            return False
        gdmf=self.insenv.target+mf
        os.system('mkdir -p '+os.path.dirname(gdmf))
        os.system("touch "+gdmf)
        config = MiscConfig()
        try:
            config.read(mf)
        except:raise
        
        if not config.has_section('daemon'):
            config.add_section('daemon')
        
        config.set('daemon','TimedLoginEnable','false')
        config.set('daemon','AutomaticLogin',self.username)
        config.set('daemon','TimedLoginDelay','1000')
        config.set('daemon','AutomaticLoginEnable','true')
        config.set('daemon','TimedLogin',self.username)
        config.set('daemon','DefaultSession','gnome')

        config.write2file(gdmf)
        return True

    def set_lightdm_autologin(self):
        live_cf='/etc/lightdm/lightdm.conf'
        cf=self.insenv.target+live_cf
        os.system('mkdir -p '+os.path.dirname(cf))
        config = MiscConfig()
        os.system("touch "+cf)
        try:
            config.read(live_cf)
        except:raise
        if not config.has_section('SeatDefaults'):
            config.add_section('SeatDefaults')

        config.set('SeatDefaults','autologin-user',self.username)
        config.set('SeatDefaults','autologin-user-timeout','0')

        config.write2file(cf)

    def set_kdm_autologin(self):
        live_cf='/usr/share/config/kdm/kdmrc'
        cf=self.insenv.target+live_cf

        os.system('mkdir -p '+os.path.dirname(cf))
        config = MiscConfig()
        if os.path.exists(cf):
            cmd='sed -i -e "\
                    s/.*AutoLoginEnable=.*\$/AutoLoginEnable=true/;\
                    s/.*AutoLoginUser=.*\$/AutoLoginUser=%s/;\
                    s/.*AutoReLogin=.*\$/AutoReLogin=true/" %s' % (self.username,cf)
            log_msg(cmd)
            os.system(cmd)
            return True
        return False
 

    def setup_login_type(self):
        self.emit_signal("progress",self._step/self._steps,_("Configuring login method"))
        if self._login_type == LOGIN_AUTOMATICALLY:
            if not self.set_kdm_autologin() and not self.set_gdm_autologin():
                self.set_lightdm_autologin()
        self._step += 1
        self.emit_signal("progress",self._step/self._steps,"")

    def setup_user(self):
        user_steps=0
        gps=['adm','floppy','audio','video','sambashare','wheel','lp','scanner']

        user_steps = 2+len(gps)
        user_step = 0.0

        cmd='useradd -U -m --skel /etc/skel --shell /bin/bash '+self.username
        if self.encrypted_password and len(self.encrypted_password) > 12:
             self.password = None
        user_steps +=1

        text = _("Adding user <b>%s</b> ...") % self.username
        self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)

        (err,sts) = get_cmd_output(cmd,insenv=self.insenv,out_err=2)
        user_step += 1
        if sts != 0 and err:
            raise Exception(err)

        text = _("User <b>%s</b> added") % self.username
        self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)

        cmd = 'chown -hR %s:%s %s' %(self.username,self.username,gethome(self.username,self.insenv.target))
        (err,sts) = get_cmd_output(cmd,insenv=self.insenv,out_err=2)
        user_step += 1
        if sts != 0 and err:
            raise Exception(err)

        cmd = 'chmod 700 %s' %(gethome(self.username,self.insenv.target))
        (err,sts) = get_cmd_output(cmd,insenv=self.insenv,out_err=2)
        user_step += 1
        if sts != 0 and err:
            raise Exception(err)


        if self.login_name and len(self.login_name) > 1:
            cmd='usermod -c "%s" %s' % (self.login_name,self.username)
            get_cmd_output(cmd,insenv=self.insenv)

        if self.password:
            text = _("Configure password for <b>%s</b>") % self.username
            self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)
            chpw='echo "'+self.password+'\n'+self.password+'" |chroot '+self.insenv.target+' passwd '+self.username
            (err,sts)= get_cmd_output(chpw,out_err=2)
            if sts != 0 and err:
                raise Exception(err)

        elif self.encrypted_password :
            text = _("Configure encrypted password for <b>%s</b>") % self.username
            self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)

            cmd = "usermod --password '%s' '%s'" % (self.encrypted_password,self.username)
            (err,sts) = get_cmd_output(cmd,insenv=self.insenv,out_err=2)
            if sts != 0 and err:
                raise Exception(err)

        user_step += 1
        text = _("Password for <b>%s</b> done") % self.username
        self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)

        text = _("Configuring <b>%s</b> as sudoer") % self.username
        self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)

        #sudoer=self.insenv.target+'/etc/sudoers'
        #os.system('sed -i "/^%s[ \t]/d" %s' % (self.username,sudoer))
        #(err,sts)=get_cmd_output('echo \"%s ALL=(ALL) NOPASSWD: ALL\" >>%s' % (self.username,sudoer))
        #if sts != 0:
        #    print err

        user_step += 1
        text = _("<b>%s</b> is sudoer") % self.username
        self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)

        for g in gps:
            cmds=["groupadd --system -f "+g,'gpasswd --add %s %s' % (self.username,g)]
            text = _('Configuring <b>%s</b> as member of group "%s"') % (self.username,g)
            self.emit_signal("progress",(self._step+user_step/user_steps)/self._steps,text)
            for cmd in cmds:
                (err,sts)=get_cmd_output(cmd,insenv=self.insenv,out_err=2)
                if sts != 0:
                    print err

        text = _("User configuration is done")
        self._step += 1
        self.emit_signal("progress",self._step/self._steps,text)

    def setup_hostname(self):
        text = _("Configuring hostname")
        self.emit_signal("progress",self._step/self._steps,text)

        os.system("echo "+self.hostname+" >"+self.insenv.target+'/etc/hostname')
        os.system("mkdir -p "+self.insenv.target+'/etc/sysconfig')
        os.system("echo HOSTNAME="+self.hostname+" >"+self.insenv.target+'/etc/sysconfig/network')
        try:
            w=open(self.insenv.target+'/etc/hosts','w')
            w.write('127.0.1.1	'+self.hostname+'\n')
            w.write('127.0.0.1	localhost\n')
            w.close()
        except:
            (e1,e2,e3)=sys.exc_info()
            print e2
        self._step += 1
        text = _("Hostname done")
        self.emit_signal("progress",self._step/self._steps,text)


    def set_from_wubi(self,wubi):
        self.username = wubi.username
        self.hostname = wubi.hostname
        self.login_name = wubi.login_name
        self.login_type = wubi.login_type
        self.password = wubi.password
        self.encrypted_password = wubi.encrypted_password

    def _run(self):
        self.emit_signal('started')
        res = True
        try:
            self.setup_hostname()
            self.setup_user()
            self.setup_login_type()
        except:
            self.emit_signal('error',error_msg(),exception_msg())
            res = False
        self._res_state = res
        self.emit_signal('finished',res)

    def run(self):
        self._run()


class AccountHostUI(gobject.GObject):
    import gtk

    def __init__(self,ath,insenv=None,build = None):

        self._ath = ath

        if build == None:
            build = gtk.Builder()
            build.add_from_file(ui_file)

        ui_file = '../data/account_ui.glade'
        if insenv:
            build.set_translation_domain(insenv.pkgname)
            ui_file=insenv.datadir+'/account_ui.glade'

        self.build  = build

        self.username_entry = build.get_object('username_entry')
        self.hostname_entry = build.get_object('hostname_entry')

        self.passwd_entry = build.get_object('passwd_entry')
        self.passwd_confirm_entry = build.get_object('passwd_confirm_entry')

        self.account_error_label = build.get_object('account_error_label')

        self.auto_login_radio = build.get_object('auto_login_radio')
        self.passwd_login_radio = build.get_object('passwd_login_radio')

        self._has_username_focus = len(ath.username) > 0
        self._has_hostname_focus = len(ath.hostname) > 0
        self._has_passwd_focus = len(ath.password)
        self._has_passwd_confirm_focus = False

        self.username_entry.connect("changed",self._on_entry_changed)
        self.hostname_entry.connect("changed",self._on_entry_changed)
        self.passwd_entry.connect("changed",self._on_entry_changed)
        self.passwd_confirm_entry.connect("changed",self._on_entry_changed)

        self.username_entry.set_text(ath.username)
        self.hostname_entry.set_text(ath.hostname)
        self.passwd_entry.set_text(ath.password)
        self.passwd_confirm_entry.set_text(ath.confirm_password)

        self.entrys_init()

        self.username_entry.connect("focus-in-event",self._on_user_host_focus_in)
        self.hostname_entry.connect("focus-in-event",self._on_user_host_focus_in)

        self.username_entry.connect("focus-out-event",self._on_user_host_focus_out)
        self.hostname_entry.connect("focus-out-event",self._on_user_host_focus_out)

        self.passwd_confirm_entry.connect("focus-in-event",self._on_passwd_focus_in)
        self.passwd_entry.connect("focus-in-event",self._on_passwd_focus_in)

        self.passwd_confirm_entry.connect("focus-out-event",self._on_passwd_focus_out)
        self.passwd_entry.connect("focus-out-event",self._on_passwd_focus_out)


        self.auto_login_radio.connect("toggled",self._on_login_radio_toggled)
        self.passwd_login_radio.connect("toggled",self._on_login_radio_toggled)

        if ath.login_type == LOGIN_AUTOMATICALLY:
            self.auto_login_radio.set_active(True)
        else:
            self.passwd_login_radio.set_active(True)

        self.user_table = build.get_object('user_table')
        self.passwd_table = build.get_object('passwd_table')
        self.login_vbox = build.get_object('login_vbox')
        self.account_error(" ")

    def entrys_init(self):
        hui_color = gtk.gdk.color_parse('#AAA689')
        if  (not self._has_username_focus) and (not self._has_hostname_focus):
            self.username_entry.modify_text(gtk.STATE_NORMAL,hui_color)
            self.hostname_entry.modify_text(gtk.STATE_NORMAL,hui_color)
            self.username_entry.set_text(_("Your username"))
            self.hostname_entry.set_text(_("Your hostname"))
        if (not self._has_passwd_confirm_focus) and (not self._has_passwd_focus):
            self.passwd_entry.set_text(_("Your passowrd"))
            self.passwd_confirm_entry.set_text(_("Confirm password"))

            self.passwd_entry.modify_text(gtk.STATE_NORMAL,hui_color)
            self.passwd_confirm_entry.modify_text(gtk.STATE_NORMAL,hui_color)

            self.passwd_entry.set_visibility(True)
            self.passwd_confirm_entry.set_visibility(True)

    def _on_entry_changed(self,entry):
        if entry == self.username_entry and self._has_username_focus:
            try:
                tt = entry.get_text()
                if tt != self.accounthost.username:
                    self.accounthost.username = tt
                    self.account_error(" ")
                if not self._has_hostname_focus:
                    un = self.accounthost.username
                    if un and len(un) > 0:
                        if self.accounthost.is_laptop:
                            hs = un +'-laptop'
                        else:
                            hs = un +'-desktop'
                    else:
                        hs = ""
                    self.hostname_entry.set_text(hs)
            except:
                self.account_error(error_msg())
                entry.set_text(self.accounthost.username)
        elif entry == self.hostname_entry:
            try:
                if self._has_hostname_focus or self._has_username_focus:
                    self.accounthost.hostname = entry.get_text()
            except:
                self.account_error(error_msg())
            if not self._has_hostname_focus and self._has_username_focus:
                entry.select_region(0,-1)
        elif entry == self.passwd_entry and self._has_passwd_focus:
            self.accounthost.password = entry.get_text()
        elif entry == self.passwd_confirm_entry:
            self.accounthost.confirm_password = entry.get_text()
            if self.passwd_confirm_entry.get_text() != self.passwd_entry.get_text() and self._has_passwd_focus:
                self.account_error(_("Confirm failed"))
            else:
                self.account_error(" ")

    def _on_login_radio_toggled(self,radio):
        if radio.get_active():
            if radio == self.auto_login_radio:
                self.accounthost.login_type = LOGIN_AUTOMATICALLY
            elif radio == self.passwd_login_radio:
                self.accounthost.login_type = LOGIN_USE_PASS_WORD

    def _on_user_host_focus_in(self,entry,event):
        if not (self._has_username_focus or self._has_hostname_focus):
            self.username_entry.set_text("")
            self.hostname_entry.set_text("")

            self.username_entry.modify_text(gtk.STATE_NORMAL,None)
            self.hostname_entry.modify_text(gtk.STATE_NORMAL,None)
        if entry == self.username_entry:
            self._has_username_focus = True
        if entry == self.hostname_entry:
            self._has_hostname_focus = True
        self.account_error(" ")

    def _on_user_host_focus_out(self,entry,event):
        if entry == self.hostname_entry:
            self._has_hostname_focus = (entry.get_text_length() >0)
        if entry == self.username_entry:
            self._has_username_focus = (entry.get_text_length() >0)
        self.entrys_init()

    def _on_passwd_focus_in(self,entry,event):
        if not(self._has_passwd_focus or self._has_passwd_confirm_focus):
            self.passwd_entry.set_text("")
            self.passwd_confirm_entry.set_text("")

            self.passwd_entry.modify_text(gtk.STATE_NORMAL,None)
            self.passwd_confirm_entry.modify_text(gtk.STATE_NORMAL,None)

            self.passwd_entry.set_visibility(False)
            self.passwd_confirm_entry.set_visibility(False)

        if entry == self.passwd_entry:
            self._has_passwd_focus = True
        if entry == self.passwd_confirm_entry:
            self._has_passwd_confirm_focus = True
        #self.account_error(" ")

    def _on_passwd_focus_out(self,entry,event):
        if entry == self.passwd_entry:
            self._has_passwd_focus = (entry.get_text_length() >0)
            if not self._has_passwd_focus:
                self.account_error(_("Password is emtry"))
            else:
                 self.account_error(" ")
        elif entry == self.passwd_confirm_entry:
            self._has_passwd_confirm_focus = (entry.get_text_length() >0)
        if self.passwd_confirm_entry.get_text() != self.passwd_entry.get_text() and self._has_passwd_focus:
            self.account_error(_("Confirm failed"))
        else:
            self.account_error(" ")
        self.entrys_init()

    def account_error(self,msg,color='red'):
        markup = "<small><span color='%s' >%s</span></small>" % (color,msg)
        self.account_error_label.set_markup(markup)

    @property
    def accounthost(self):
        return self._ath

    @property
    def widget(self):
        return self.build.get_object('account_box')

    @property
    def toplevel(self):
        self.widget.get_toplevel()

if __name__ == "__main__":

    import InsEnv
    import glib
    import gtk

    glib.threads_init()
    insenv = InsEnv.InstallerEnv()
    ah = AccountHost(insenv)

    def test1():
        def err_msg(obj,msg):
            dialog = gtk.Dialog(title="test",buttons=(gtk.STOCK_OK,gtk.RESPONSE_OK))
            label = gtk.Label(msg)
            dialog.vbox.pack_start(label)
            dialog.show_all()
            label.set_selectable(True)
            dialog.run()
            dialog.destroy()

        ah.username = 'dd'
        ah.password = '12345'
        ah.hostname = 'kk'
        ah.connect('error',err_msg)
        ah.go()

    def test2():
        win = gtk.Window()
        ah.login_type = 2
        athu = AccountHostUI(ah)
        win.add(athu.widget)
        win.connect("destroy",gtk.main_quit)
        win.show_all()
        gtk.main()
        print ah

    test2()
