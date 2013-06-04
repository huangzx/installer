#!/usr/bin/env python
# -*- coding: utf-8; Mode: Python; indent-tabs-mode: nil; tab-width: 4 -*-
# localetzonemap.py
# Python module for osinstaller.
#
# Copyright (C) 2010 Ylmf, Inc.
#
#
# Ylmf Author(s): wkt <weikting@gmail.com>
#               
#

import locale
from gettext import *

def N_(s):
    return s



LangList=[
    {"C":[['C'],
     "GMT"]
    },
    {"中文简体":[['zh_CN.UTF-8','zh_CN'],
     'Asia/Chongqing']
    },
    {"中文繁体(香港)":[['zh_HK.UTF-8','en_HK.UTF-8','zh_HK','en_HK'], ###the first will default locale
                'Asia/Hong_Kong']                                      ###default timezone
    }, 
    {"中文繁体(台灣)":[['zh_TW.UTF-8','zh_TW'],'Asia/Taipei']
    },
    {"English(United States)":[['en_US.UTF-8','en_US'],'America/New_York']
    },
    {"English(Hong Kong)":[['en_HK.UTF-8','zh_HK.UTF-8','zh_HK','en_HK'],'Asia/Hong_Kong']
    },
]

TZones={
'C': {'GMT':'GMT'},
'CN':{'Asia/Chongqing':N_('China(Chongqing,Shanghai,Beijing)')},
'TW':{'Asia/Taipei':N_('China(Taibei)')},
'HK':{'Asia/Hong_Kong':N_('China(xianggang)')},
'US':{"America/Indiana/Tell_City":N_("United States (Tell City, Indiana)"),
      "America/Phoenix":N_("United States (Phoenix)"),
    }
}


