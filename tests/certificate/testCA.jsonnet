local cert = (import "certificate.libsonnet");



[
    #cert.selfSigned_issuer('fooCA-secret-issuer'),

    #cert.ca_certificate(
    #    'fooCA-certificate', 
    #    'fooCA-secret', 
    #    cert.issuerRef('fooCA-secret-issuer')),

    // Secret must pre-exist
    #cert.CertificateAuthority('fooCA', true, 'fooCA-secret', null).manifests(),
    #cert.CertificateAuthority('fooCA', false, 'fooCA-secret', null).manifests(),
    
    // Secret by self-signed certificate
    #cert.CertificateAuthority('fooCA').manifests(),
    #cert.CertificateAuthority('fooCA', true).manifests(),
    #cert.CertificateAuthority('fooCA', false).manifests(),

    // Provided issuer
    cert.CertificateAuthority('fooCA', false, issuerRef=cert.issuerRef('my-issuer')).manifests(),


]