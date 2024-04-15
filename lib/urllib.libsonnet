/*
    URL formulation library.

    Simple-minded functions, follow the eponymous python module.

 */


local _portspec(port) =
    if port==null || port=="" then 
        ""
    else if std.isNumber(port) then 
        ":%d" % port
    else if std.isString(port) then
        ":"+port
    else
        error "A port must be integer or string.";

local _netloc_from_obj(netloc) = 
    if std.isString(netloc) then 
        netloc
    else if std.isObject(netloc) then 
        "%(host)s%(portspec)s" % (netloc { portspec: _portspec(netloc.port) })
    else
        error "Illegal type for netloc";
        
local _netloc(netloc, host, port) = 
    assert netloc!=null || host!=null;
    assert netloc==null || host==null;
    assert port==null || host!=null;
    if netloc!=null then
        _netloc_from_obj(netloc)
    else
        _netloc_from_obj({host: host, port: port});

local _usrpw(user, password) =
    assert password==null || user!=null;
    local up = {user: user, password: password};
    if user==null then
        ""
    else if password!=null then
        "%(user)s:%(password)s@" % up
    else
        "%(user)s@" % up;

 {

    url(scheme='http', netloc=null, path="", host=null, port=null, user=null, password=null):
        
        "%(scheme)s://%(usrpw)s%(netloc)s%(path)s" % {
            scheme: scheme,
            usrpw: _usrpw(user, password),
            netloc: _netloc(netloc, host, port),
            path: path
        }

 }
