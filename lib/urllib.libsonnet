/*
    URL formulation library.

    Simple-minded functions, follow the eponymous python module.

 */


local _portspec(port) =
        if port==null || port=="" then ""
        else if std.isNumber(port) then ":%d" %port
        else port;

local _netloc(netloc) = 

 {

    url(scheme='http', netloc=null, path="", host=null, port=null, user=null, password=null):
        "%(scheme)s://%(netloc)s%(path)s" % {
            scheme: scheme,
            netloc: 
                if std.isString(netloc) then netlock
                else if std.isObject(netlock) then std.format("%(host)%(portspec)", netlock { portspec: _portspec}

        }

 }