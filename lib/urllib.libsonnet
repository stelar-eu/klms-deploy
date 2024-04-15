/*
    URL formulation library.

    Simple-minded functions, follow the eponymous python module.

 */


local _portspec(port) =
        if port==null || port=="" then ""
        else if std.isNumber(port) then ":%d" %port
        else port;

local _netloc(args) = 
    if args.host!=null then
    (if args.port!= null then "%(host)s:%(port)s" % {host: args.host, port: })
    
    std.isString() then netlock
    else if std.isObject(netlock) then std.format("%(host)%(portspec)", netlock { portspec: _portspec}


 {

    /*
        Compose a URL from arguments.

        If `host` is specified, then host/port is used, else netloc must be specified.
     */
    url(scheme='http', netloc=null, path="", host=null, port=null, user=null, password=null):
        local args={
            scheme: scheme,
            netloc: netloc,
            path: path,
            host: host,
            port: port,
            user: user,
            password: password,
        };
        "%(scheme)s://%auth%(netloc)s%(path)s" % {
            scheme: scheme,
            netloc: _netloc(args),

        }

 }