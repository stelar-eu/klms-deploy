/* 
    A model for creating postgresql database services

    {
        name: service name
        image: image name 

    }
*/

local tanka = import 'github.com/grafana/jsonnet-libs/tanka-util/main.libsonnet';
local helm = tanka.helm.new(std.thisFile);

{
    postgres: helm.template("postgres", "../charts/postgresql", {

    }) 
}