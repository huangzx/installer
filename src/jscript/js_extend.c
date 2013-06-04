/**
 * Copyright 2011 wkt  <weikting@gmail.com>
 * Python的C扩展模块jsextend
 * jsextend包含类JSInstaller
 * JSInstaller的属性为progress,is_working,jscontext
 * progress为只读属性
 * is_working可读写属性,is_working用于安装是否正在进行中
 * jscontext是JSGlobalContextRef的PyObject绑定
 * */

#include <stdio.h>
#include "js_extend.h"
#include "jsosinstaller.h"

void _js_installer_dealloc(JSInstaller *self);
int _js_installer_clear(JSInstaller *self);
int _js_installer_init(JSInstaller *self, PyObject *args, PyObject *kwds);
PyObject *_js_installer_get(JSInstaller *self, void *closure);
int _js_installer_set(JSInstaller *self, PyObject *value, void *closure);
PyObject *js_instaler_set_progress(JSInstaller *self,PyObject *args);
PyObject *js_instaler_set_restart(JSInstaller *self,PyObject *args);
PyObject *js_instaler_set_done(JSInstaller *self,PyObject *args);


static PyMemberDef _js_installer_members[] = {
    {"progress", T_DOUBLE, offsetof(JSInstaller, progress), READONLY,
            "progress of installing process"},
    {"restart",T_BOOL,offsetof(JSInstaller, restart), READONLY,
            "flag to indicate restart computer"},
    {NULL}
};

static PyMethodDef  _js_installer_methods[] =
{
    {"set_progress",js_instaler_set_progress,METH_VARARGS,"set installing progress"},
    {"set_restart",js_instaler_set_restart,METH_VARARGS,"set restart flags"},
    {"set_done",js_instaler_set_done,METH_NOARGS,"tell installing done"},
    {NULL}
};

static PyGetSetDef _js_installer_getset[] = 
{
    {"is_working", (getter) _js_installer_get,
              (setter) _js_installer_set,
              "flag to indicate installer working state.", "is_working"},

    {"jscontext", (getter) _js_installer_get,
              (setter) _js_installer_set,
              "context of javascript", "jscontext"},

    {NULL}  /* Sentinel */
};

PyTypeObject _JS_Installer_Type_obj = {
    PyObject_HEAD_INIT(&PyType_Type)
    .tp_name = "jsextend.JSInstaller",
    .tp_basicsize = sizeof(JSInstaller),
 /* .tp_itemsize = XXX */
 /*   .tp_dealloc = (destructor) _js_installer_dealloc,*/
 /* .tp_getattr = XXX */
 /* .tp_setattr = XXX */
 /*   .tp_compare = (cmpfunc) _js_installer_compare, */
 /* .tp_repr = XXX */
 /* .tp_as_number = XXX */
 /* .tp_as_sequence = XXX */
 /* .tp_as_mapping = XXX */
    .tp_hash = PyObject_HashNotImplemented,
    .tp_call = NULL,
 /*   .tp_str = (reprfunc) _js_installer_str, */
    .tp_getattro = PyObject_GenericGetAttr,
    .tp_setattro = PyObject_GenericSetAttr,
 /* .tp_as_buffer = XXX */
    .tp_flags = Py_TPFLAGS_HAVE_CLASS | Py_TPFLAGS_BASETYPE,
 /*   .tp_doc = _js_installer_doc,*/
 /*   .tp_traverse = (traverseproc) _js_installer_traverse, */
 /*   .tp_clear = (inquiry) _js_installer_clear,*/
 /*   .tp_richcompare = (richcmpfunc) _js_installer_richcompare, */
 /* .tp_weaklistoffset = XXX */
 /* .tp_iter = XXX */
 /* .tp_iternext = XXX */
    .tp_methods = _js_installer_methods,
    .tp_members = _js_installer_members,
    .tp_getset = _js_installer_getset,
    .tp_base = NULL,
    .tp_dict = NULL,
 /* .tp_descr_get = XXX */
 /* .tp_descr_set = XXX */
 /* .tp_dictoffset = XXX */
    .tp_init = (initproc) _js_installer_init,
    .tp_alloc = PyType_GenericAlloc,
    .tp_new = PyType_GenericNew,
 /* .tp_free = XXX */
 /* .tp_is_gc = XXX */
    .tp_bases = NULL,
 /* .tp_del = XXX */
};

void
log_msg_real(const char*filename,int lineno,const char *func,const char *msg)
{
    fprintf(stderr,"%s:%d:%s:%s\n",filename,lineno,func,msg);
}

void _js_installer_dealloc(JSInstaller *self)
{
    log_msg("");
    Py_CLEAR(self->js_context);
    self->js_context = NULL;
}

int _js_installer_clear(JSInstaller *self)
{
    log_msg("");
    Py_CLEAR(self->js_context);
    self->js_context = NULL;
    return 0;
}

int _js_installer_jscontext(JSInstaller *self,PyObject *js_obj)
{
    JSGlobalContextRef context = NULL;
    JSGlobalContextRef old_context = NULL;
    log_msg("");
    if(PyCObject_Check(js_obj)){
        context = PyCObject_AsVoidPtr(js_obj);
        if(self->js_context){
            old_context = PyCObject_AsVoidPtr(self->js_context);
        }
        if(context != old_context){
            log_msg("JSOSInstaller_maker");
            JSOSInstaller_maker(context,self);
            JSOSInstaller_progressChanged(context,self);
        }
        if(js_obj != self->js_context){
            self->js_context = js_obj;
            log_msg("set js_context");
            Py_INCREF(self->js_context);
        }
    }else{
        self->js_context = NULL;
    }
    return 0;
}

int _js_installer_init(JSInstaller *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"jscontext",NULL};
    PyObject *js_obj = NULL;

    log_msg("");
    if (kwds == NULL) {
        if (!PyArg_ParseTuple(args, "O", &js_obj)) {
            return -1;
        }
    }else{
        if (!PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist,&js_obj)) {
            return -2;
        }
    }
    _js_installer_jscontext(self,js_obj);
    self->is_working = 0;
    self->progress = 0.0;
    return 0;
}

PyObject *_js_installer_get(JSInstaller *self, void *closure)
{
    char *member = (char *) closure;

    if (member == NULL) {
        PyErr_SetString(PyExc_TypeError, "Empty JSInstaller()");
        return NULL;
    }
    if (!strcmp(member, "is_working")) {
        if(self->is_working){
            Py_RETURN_TRUE;
        }else{
            Py_RETURN_FALSE;
        }
    }else if (!strcmp(member, "jscontext")){
        if(self->js_context){
            return self->js_context;
        }else{
            Py_RETURN_NONE;
        }
    } else {
        PyErr_Format(PyExc_AttributeError, "JSInstaller object has no attribute %s", member);
        return NULL;
    }
    return NULL;
}


int _js_installer_set(JSInstaller *self, PyObject *value, void *closure)
{
    char *member = (char *) closure;
    int val;

    if (member == NULL) {
        PyErr_SetString(PyExc_TypeError, "Empty JSInstaller()");
        return -1;
    }
    if (!strcmp(member, "is_working")) {
        val = PyInt_AsLong(value);
        if (PyErr_Occurred()) {
            return -1;
        }
        self->is_working = (!(!val));
    }else if (!strcmp(member, "jscontext")){
        Py_CLEAR(self->js_context);
        _js_installer_jscontext(self,value);
    }  else {
        PyErr_Format(PyExc_AttributeError, "JSInstaller object has no attribute %s", member);
        return -1;
    }

    return 0;
}

PyObject *js_instaler_set_progress(JSInstaller *self,PyObject *args)
{
    double progress = 0;
    JSGlobalContextRef context = NULL;

    if(!PyArg_ParseTuple(args,"d",&progress)){
        return NULL;
    }
    if(progress < 0 || progress >1.0){
        PyErr_Format(PyExc_AttributeError, "progress must be >=0 and <= 1.0 ");
        return NULL;
    }
    self->progress = progress;
    if(self->js_context){
        context = PyCObject_AsVoidPtr(self->js_context);
        if(context)
            JSOSInstaller_progressChanged(context,self);
    }
    return Py_BuildValue("z",NULL);
}

PyObject *js_instaler_set_restart(JSInstaller *self,PyObject *args)
{
    char restart = 0;

    if(!PyArg_ParseTuple(args,"b",&restart)){
        return NULL;
    }
    self->restart = !(!restart);
    return Py_BuildValue("z",NULL);
}

PyObject *js_instaler_set_done(JSInstaller *self,PyObject *args)
{
    JSGlobalContextRef context = NULL;
    if(self->js_context){
        context = PyCObject_AsVoidPtr(self->js_context);
        if(context){
            JSOSInstaller_setDone(context,self);
        }
    }
    return Py_BuildValue("z",NULL);
}


static struct PyMethodDef js_installer_mod_methods[]=
{
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initjsextend(void)
{
    PyObject *m = NULL;

    /* init the main Python module and add methods */
    m = Py_InitModule3("jsextend", js_installer_mod_methods, "javascript extend for pywebkitgtk");

    Py_INCREF(&_JS_Installer_Type_obj);
    PyModule_AddObject(m, "JSInstaller", (PyObject *)&_JS_Installer_Type_obj);
}
