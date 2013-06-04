#ifndef ___js_os_installer_H__

#define ___js_os_installer_H__


#include "js_extend.h"

void
JSOSInstaller_maker(JSGlobalContextRef context,JSInstaller* jsinst);

void
JSOSInstaller_progressChanged(JSGlobalContextRef context,JSInstaller* jsinst);

void
JSOSInstaller_setDone(JSGlobalContextRef context,JSInstaller* jsinst);

#define NO_DEBUG 1

#if defined(NO_DEBUG) && NO_DEBUG
#define log_msg(msg) 
#else
#define log_msg(msg) log_msg_real( __FILE__,__LINE__,__func__,msg)
#endif


#endif ///___js_os_installer_H__
