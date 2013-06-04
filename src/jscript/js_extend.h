#ifndef __os_installer_js_extend_h

#define __os_installer_js_extend_h

#include <Python.h>
#include <structmember.h>

#include <JavaScriptCore/JavaScript.h>

typedef struct _JSInstaller JSInstaller;

struct _JSInstaller
{
    PyObject_HEAD

    double progress;                /* progress */

    PyObject *js_context;

    char is_working;
    char restart;
    JSObjectRef progress_changed;
    JSObjectRef done_func;
    JSObjectRef js_self;
};

void
log_msg_real(const char*filename,int lineno,const char *func,const char *msg);

#endif ///__os_installer_js_extend_h
