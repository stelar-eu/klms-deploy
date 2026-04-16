/*
    Code related to image management
 */

local k = import "k.libsonnet";


/*
    An image spec contains the following fields:

    {
        image: <name>
        pullPolicy: <Always|Never|IfNotPresent>
    }

    When the spec is a plain string, the pullPolicy is assumed to be 'Always'

    N.B. This stuff may be updated when we integrate our private image registry.

*/

{
    // 
    image_name: function (imgspec) 
        if std.isString(imgspec) then
            imgspec
        else if std.isObject(imgspec) then 
            imgspec.image
        else 
            error "Wrong type for imgspec: "+std.type(imgspec),
            

    pull_policy: function(imgspec)
        if std.isString(imgspec) then
            "Always"
        else
            imgspec.pullPolicy
}