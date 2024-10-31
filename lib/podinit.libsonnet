/**********************************************888

    Utilities for generating initContainers for pods
    using the podinit image.

    The image is essentially a wrapper for the wait4x
    utility, found at

    https://github.com/atkrad/wait4x.git

 */

local k = import "k.libsonnet";
local container = k.core.v1.container;
local envSource = k.core.v1.envVarSource;

local PODINIT_IMAGE = 'vsam/stelar-okeanos:podinit';

/************
    Describe option syntax and translation
 */
local flags_map = {
    timeout: {optname: '--timeout', type: 'string'},
    interval: {optname: '--interval', type: 'string'},
    quiet: {optname: '--quiet', type: 'switch'},

    // http flags
    noRedirect: {optname: '--no-redirect', type: 'switch'},
    insecureSkipTlsVerify: {optname: '--insecure-skip-tls-verify', type: 'switch'},
};

local option_pair(key, value)=
    assert std.objectHas(flags_map, key) :  "key does not exist";
    local key_type = flags_map[key].type;
    local key_optname = flags_map[key].optname;
    assert std.type(value)==key_type || (std.type(value)=='boolean' && key_type=='switch') 
        : "key has wrong type";

    if key_type=='switch' then
        if value then
            [key_optname]
        else
            []
    else
        [key_optname, std.toString(value)];



local flags_map_to_array(flags_map, default_map)=

    // In version 0.20  (tk) we could use this...
    // local objpairs = std.objectKeysValues(default_map + flags_map);
    // local arrpairs = [ option_pair(p.key, p.value) for p in objpairs ];
    // std.flattenArrays(arrpairs);
    //
    // Keeping compatibility with Jsonnet v 0.17
    local objKV(m) = [ 
        option_pair(k, m[k])
        for k in std.objectFields(m) 
    ];
    std.flattenArrays(objKV(default_map+flags_map));


/*
    Global defaults: Wait for 10s (interval), try for ever!
*/
local global_default_flags = {
    timeout: '0',
    interval: '10s'
};


{
    _base_container(name)::
        container.new(name, PODINIT_IMAGE),

    // Http endpoints
    wait4_http(name, url, flags={}):
        self._base_container(name)
        + container.withArgs(['http', url]+flags_map_to_array(flags, global_default_flags)),

    // Postgresql databases
    wait4_postgresql(name, pim, config, flags={}):
        self._base_container(name)
        + container.withArgs(['postgresql']+flags_map_to_array(flags, global_default_flags))
        + container.withEnvMap({
            POSTGRES_HOST: pim.db.POSTGRES_HOST,
            POSTGRES_USER: pim.db.CKAN_DB_USER,
            POSTGRES_DB: pim.db.STELAR_DB,
            POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan_db_password_secret).withKey("password"),
        }),

    // redis
    wait4_redis(name, url, flags={}):
        self._base_container(name)
        + container.withArgs(['redis', url]+flags_map_to_array(flags, global_default_flags)),

}
