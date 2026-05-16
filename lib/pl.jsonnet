local k = import "k.libsonnet";

local secret = k.core.v1.secret;
local c = import "certificate.libsonnet";


{
    issuer: c.selfSigned_issuer('foobar'),

    cert: c.dns_certificate('foo-cert', 
        issuerRef=c.issuerRef('foobar'), 
        dnsName='foo.vsamtuc.top',
        ),

}
