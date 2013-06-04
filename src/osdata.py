#!/usr/bin/env python
# -*- coding: utf-8; Mode: Python; indent-tabs-mode: nil; tab-width: 4 -*-
# osdata.py
# Python module for osinstaller.
#
# Copyright (C) 2010 Ylmf, Inc.
#
#
# Ylmf Author(s): wkt <weikting@gmail.com>
#               
#

import osenv
import locale
import gettext

LangList={
"C":{
	'C':[]
	},
"English":{
      'en':['US','HK']
    },
"中文简体":{
    'zh':['CN']
    }
"中文繁体":{
    'zh':['TW','HK']
}
}

TZone={
'C': {'GMT':'GMT'},
'CN':{_('China(Chongqing,Shanghai,Beijing)'):'Asia/Chongqing'},
'TW':{_('China(Taibei)'):'Asia/Taipei'},
'HK':{_('China(xianggang)'):'Asia/Hong_Kong'},
'US':{_("United States (Tell City, Indiana)"):"America/Indiana/Tell_City",
      _("United States (Phoenix)"):"America/Phoenix",
    }
}


