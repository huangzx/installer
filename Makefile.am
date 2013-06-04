SUBDIRS = icons po src data gtkrc

EXTRA_DIST = autogen.sh configure.in

update-po:
	ls src/*.py data/{*.glade,*.desktop.in.in} >po/POTFILES.in
	make -C po update-po

tmpdir=/tmp/$(PACKAGE)
tarbin:
	rm -rf $(tmpdir)
	make DESTDIR=$(tmpdir) install
	tar -jcpf $(PACKAGE)-$(VERSION)-install.tar.bz2 -C $(tmpdir) .

test-no-desktop:
	IS_DESKTOP=0 sudo -E ./src/OSInstaller 

clean-local:
	rm -rf $(PACKAGE).tar.bz2
