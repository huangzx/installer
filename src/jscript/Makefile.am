
PYTHON_LIBS = $(shell python-config --libs)
PYTHON_CFLAGS = $(shell python-config --cflags)

pkgpyexecdir = $(pyexecdir)


jsextend_la_SOURCES =    js_extend.c 				\
						 js_extend.h				\
						 jsosinstaller.c			\
						 jsosinstaller.h			\
						 $(NULL)


jsextend_la_CFLAGS = $(PYTHON_CFLAGS) $(WEBKIT_CFLAGS)
jsextend_la_LDFLAGS =  -module -avoid-version $(PYTHON_LIBS) $(WEBKIT_LIBS)

pkgpyexec_LTLIBRARIES = jsextend.la
