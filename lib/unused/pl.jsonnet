local k = import "../util/k.libsonnet";

local secret = k.core.v1.secret;
local c = import "../util/certificate.libsonnet";


{
    issuer: c.selfSigned_issuer('foobar'),

    cert: c.dns_certificate('foo-cert', 
        issuerRef=c.issuerRef('foobar'), 
        dnsName='foo.vsamtuc.top',
        ),

}
