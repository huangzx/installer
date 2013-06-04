#!/bin/sh
File="AUTHORS ChangeLog COPYING INSTALL  NEWS  README"
for f in ${File}
do
	touch ${f}
done

set -e
set -x

#autopoint --force
intltoolize --automake --copy --force || exit 1
libtoolize --automake --copy --force
aclocal --force
autoheader --force
automake --add-missing --copy --force
autoconf --force
if test -n "$1" ;then
	conflag=$@
else
	conflag=" --enable-maintainer-mode --prefix=/usr"
fi
./configure $conflag
