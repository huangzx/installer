/**
 * Copyright 2011 wkt  <weikting@gmail.com>
 * Javascript 扩展
 * 添加一个对象JSOSInstaller,
 * 对象属性为working,progress,version
 * 分别用于表示osinstaller是否在安装进度中,安装的进度,扩展的版本
 * 
 **/

#include "jsosinstaller.h"

JSClassRef JSOSInstaller_class(JSContextRef context);

static JSValueRef JSOSInstaller_getWorking(JSContextRef context, JSObjectRef object, JSStringRef propertyName, JSValueRef* exception)
{
    JSInstaller* jsinst = JSObjectGetPrivate(object);
    if (jsinst) {
        JSValueRef value = JSValueMakeBoolean(context, jsinst->is_working);
        return value;
    }else{
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: Failed to get inside JSInstaller");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    }
    return NULL;
}

static JSValueRef JSOSInstaller_getProgress(JSContextRef context, JSObjectRef object, JSStringRef propertyName, JSValueRef* exception)
{
    JSInstaller* jsinst = JSObjectGetPrivate(object);
    if (jsinst) {
        JSValueRef value = JSValueMakeNumber(context, jsinst->progress);
        return value;
    }else{
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: Failed to get inside JSInstaller");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    }
    return NULL;
}

static JSValueRef JSOSInstaller_getVersion(JSContextRef context, JSObjectRef object, JSStringRef propertyName, JSValueRef* exception)
{
    JSInstaller* jsinst = JSObjectGetPrivate(object);
    if (jsinst) {
        JSStringRef message = JSStringCreateWithUTF8CString("1.0");
        JSValueRef value = JSValueMakeString(context, message);
        JSStringRelease(message);
        return value;
    }else{
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: Failed to get inside JSInstaller");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    }
    return NULL;
}

static JSValueRef
JSOSInstaller_setRestart(JSContextRef context, JSObjectRef function, JSObjectRef thisObject, size_t argumentCount, const JSValueRef arguments[], JSValueRef* exception)
{
    if (!JSValueIsObjectOfClass(context, thisObject, JSOSInstaller_class(context))) {
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: setRestart can only be called on JSOSInstaller");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    } else if (argumentCount < 1 || !JSValueIsBoolean(context, arguments[0])) {
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: first argument to setRestart must be a boolean");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    } else {
        JSInstaller* jsinst = JSObjectGetPrivate(thisObject);
        jsinst->restart = JSValueToBoolean(context,arguments[0]);
    }

    return JSValueMakeUndefined(context);
}

static JSValueRef
JSOSInstaller_setProgressChangedFunc(JSContextRef context, JSObjectRef function, JSObjectRef thisObject, size_t argumentCount, const JSValueRef arguments[], JSValueRef* exception)
{
    if (!JSValueIsObjectOfClass(context, thisObject, JSOSInstaller_class(context))) {
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: SetProgressChangedFunc can only be called on JSOSInstaller");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    } else if (argumentCount < 1 || !JSValueIsObject(context, arguments[0])) {
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: first argument to SetProgressChangedFunc must be a callable");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    } else {
        JSInstaller* jsinst = JSObjectGetPrivate(thisObject);
        jsinst->progress_changed = JSValueToObject(context,arguments[0],exception);
    }

    return JSValueMakeUndefined(context);
}

static JSValueRef
JSOSInstaller_setDoneHookFunc(JSContextRef context, JSObjectRef function, JSObjectRef thisObject, size_t argumentCount, const JSValueRef arguments[], JSValueRef* exception)
{
    if (!JSValueIsObjectOfClass(context, thisObject, JSOSInstaller_class(context))) {
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: SetDoneHookFunc can only be called on JSOSInstaller");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    } else if (argumentCount < 1 || !JSValueIsObject(context, arguments[0])) {
        JSStringRef message = JSStringCreateWithUTF8CString("TypeError: first argument to SetDoneHookFunc must be a callable");
        *exception = JSValueMakeString(context, message);
        JSStringRelease(message);
    } else {
        JSInstaller* jsinst = JSObjectGetPrivate(thisObject);
        jsinst->done_func = JSValueToObject(context,arguments[0],exception);
    }

    return JSValueMakeUndefined(context);
}

static void JSOSInstaller_initialize(JSContextRef context, JSObjectRef object)
{

    JSInstaller* jsinst = JSObjectGetPrivate(object);
    Py_INCREF(jsinst);
}

static void JSOSInstaller_finalize(JSObjectRef object)
{
    JSInstaller* jsinst = JSObjectGetPrivate(object);
    Py_CLEAR(jsinst);
}

static JSStaticValue JSOSInstaller_staticValues[] = {
    { "working", JSOSInstaller_getWorking, NULL, kJSPropertyAttributeDontDelete | kJSPropertyAttributeReadOnly },
    { "progress", JSOSInstaller_getProgress, NULL, kJSPropertyAttributeDontDelete | kJSPropertyAttributeReadOnly },
    { "version", JSOSInstaller_getVersion, NULL, kJSPropertyAttributeDontDelete | kJSPropertyAttributeReadOnly },
    { 0, 0, 0, 0 }
};

static JSStaticFunction JSOSInstaller_staticFunctions[] = {
///    {"SetRestart", JSOSInstaller_setRestart, kJSPropertyAttributeDontDelete },
    {"SetProgressChangedFunc", JSOSInstaller_setProgressChangedFunc, kJSPropertyAttributeDontDelete },
    {"SetDoneHookFunc", JSOSInstaller_setDoneHookFunc, kJSPropertyAttributeDontDelete },
    { 0, 0, 0 }
};


JSClassRef JSOSInstaller_class(JSContextRef context)
{

    static JSClassRef jsClass;
    if (!jsClass) {
        JSClassDefinition definition = kJSClassDefinitionEmpty;
        definition.staticValues = JSOSInstaller_staticValues;
        definition.staticFunctions = JSOSInstaller_staticFunctions;
        definition.initialize = JSOSInstaller_initialize;
        definition.finalize = JSOSInstaller_finalize;

        jsClass = JSClassCreate(&definition);
    }
    return jsClass;
}

JSObjectRef JSOSInstaller_new(JSContextRef context, JSInstaller* jsinst)
{
    JSObjectRef jsobj;
    jsobj = JSObjectMake(context, JSOSInstaller_class(context), jsinst);
    jsinst->js_self = jsobj;
    return jsobj;
}

/*
JSObjectRef JSOSInstaller_construct(JSContextRef context, JSObjectRef object, size_t argumentCount, const JSValueRef arguments[], JSValueRef* exception)
{
    JSInstaller* jsinst;
    return JSOSInstaller_new(context, jsinst);
}
*/

void
JSOSInstaller_maker(JSGlobalContextRef context,JSInstaller* jsinst)
{
    JSStringRef jsinst_name = JSStringCreateWithUTF8CString("JSOSInstaller");
    JSObjectRef globalObject = JSContextGetGlobalObject(context);
    ///JSObjectSetProperty(context, globalObject, jsinst_name, 
    ///    JSObjectMakeConstructor(context, JSNode_class(context), JSNode_construct),
    ///    kJSPropertyAttributeNone, NULL);
    JSObjectSetProperty(context, globalObject, jsinst_name,JSOSInstaller_new(context,jsinst),kJSPropertyAttributeNone|kJSPropertyAttributeReadOnly|kJSPropertyAttributeDontDelete, NULL);
    JSStringRelease(jsinst_name);
}

void
JSOSInstaller_progressChanged(JSGlobalContextRef context,JSInstaller* jsinst)
{
///JS_EXPORT JSValueRef JSObjectCallAsFunction(JSContextRef ctx, JSObjectRef object, JSObjectRef thisObject, size_t argumentCount, const JSValueRef arguments[], JSValueRef* exception);
    log_msg("start");
    if(jsinst->js_self && jsinst->progress_changed){
        JSValueRef arguments[]={jsinst->js_self};
        JSObjectCallAsFunction(context,jsinst->progress_changed,NULL,1,arguments,NULL);
    }
    log_msg("end");
}


void
JSOSInstaller_setDone(JSGlobalContextRef context,JSInstaller* jsinst)
{
///JS_EXPORT JSValueRef JSObjectCallAsFunction(JSContextRef ctx, JSObjectRef object, JSObjectRef thisObject, size_t argumentCount, const JSValueRef arguments[], JSValueRef* exception);
    log_msg("start");
    if(jsinst->js_self && jsinst->done_func){
        JSValueRef arguments[]={jsinst->js_self};
        JSObjectCallAsFunction(context,jsinst->done_func,NULL,1,arguments,NULL);
    }
    log_msg("end");
}
