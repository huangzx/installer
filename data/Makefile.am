@INTLTOOL_DESKTOP_RULE@


desktop_in_in_files = osinstaller.desktop.in.in
desktop_in_files = $(desktop_in_in_files:.desktop.in.in=.desktop.in) 

desktopdir = $(datadir)/applications
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)

html_files = $(shell find  html|sort)

pkgdata_DATA = installer_ui.glade parted_man.glade localetzone_ui.glade account_ui.glade blacklist


install-data-local:
	for f in $(html_files);do \
		if test -d $$f;then \
			mkdir -p $(DESTDIR)$(pkgdatadir)/$$f; \
			continue; \
		fi; \
		$(install_sh_DATA) $(top_srcdir)/data/$$f $(DESTDIR)$(pkgdatadir)/$$f; \
	done

uninstall-local:
	for f in $(html_files);do \
		if test -d $$f;then \
			rm -rf $(DESTDIR)$(pkgdatadir)/$$f; \
		else \
			continue; \
		fi; \
	done


EXTRA_DIST = $(pkgdata_DATA)
