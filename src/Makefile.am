SUBDIRS = 

pkgconfdir=$(sysconfdir)/$(PACKAGE)

pkgconf_DATA = preconfig.example

pkgpython_PYTHON = 							\
				keyboard_names.py			\
				installscript.py			\
				accountmod.py				\
				copyfilemod.py				\
				localetzonemod.py			\
				localetzonemap.py			\
				mainframemod.py				\
				partmod.py					\
				installerenv.py				\
				misc.py						\
				__init__.py					\
				layoutwidget.py				\
				testparted.py				\
				labelcontexts.py			\
				BGwidget.py					\
				$(NULL)

bin_SCRIPTS = osinstaller

pkgdata_SCRIPTS = pre_install post_install OSInstaller osprober clean_root

installerenv.py:installerenv.py.in Makefile.am Makefile
	sed -e 's|\@localedir\@|$(localedir)|g;s|\@GETTEXT_PACKAGE\@|$(GETTEXT_PACKAGE)|g;s|\@pkgdatadir\@|$(pkgdatadir)|g;s|\@VERSION\@|$(VERSION)|g;s|\@pkgconfdir\@|$(pkgconfdir)|g' $< >$@

bin_PROGRAMS = resize4fat

resize4fat_SOURCES = resize4fat.c
resize4fat_CFLAGS	=
resize4fat_LDFLAGS = -lparted
if HAS_LIBPARTED_FS_RESIZE
resize4fat_LDFLAGS += -lparted-fs-resize
endif

EXTRA_DIST = $(bin_SCRIPTS) $(pkgdata_SCRIPTS)

clean-local:
	rm -rf osenv.py 
