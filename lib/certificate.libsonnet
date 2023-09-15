/*
    Code related to cert-manager resources
 */

local k = import "k.libsonnet";

/* **************************************************
    Constants related to the cert-manager API.
 */
local cm = {

    header: {
        apiVersion: "cert-manager.io/v1"
    },
    Issuer: self.header {
        kind: 'Issuer'
    },
    ClusterIssuer: self.header {
        kind: 'ClusterIssuer'
    },
    SelfSignedSpec: {
        selfSigned: {}
    },

    Certificate: self.header {
        kind: 'Certificate'
    },

    // Private key encodings (default: PKCS1)
    PK_ENCODING: ['PKCS1', 'PKCS8'],

    // Choice of algorithms in PKI spec
    PK_ALGORITHM: ['RSA', 'ECDSA', 'Ed25519', ],

    // Certificate usages 
    USAGES: [ 
        'signing', 'digital signature', 'content commitment', 'key encipherment',
        'key agreement', 'data encipherment', 'cert sign', 'crl sign', 'encipher only',
        'decipher only', 'any', 'server auth', 'client auth', 'code signing', 'email protection',
        's/mime', 'ipsec end system', 'ipsec tunnel', 'ipsec user', 'timestamping', 'ocsp signing',
        'microsoft sgc', 'netscape sgc',
    ],

};


/**
    Used to check parameters taking enum values
 */
local assert_member(enum, val, param_name) =
    assert std.member(enum, val) : "value '%s' for %s not in %s" % [val, param_name, enum];
    true;



/**
    Return a K8s manifest for a cert-manager self-signed Issuer.
 */
local selfSigned_issuer(name) = cm.Issuer {
    metadata: {
        name: name
    },
    spec: cm.SelfSignedSpec
};



/**
    Construct the 'spec.privateKey' portion of a certificate spec.
 */
local certificate_privateKey(algorithm, size=null, encoding='PKCS1', rotationPolicy='Never') = {
    assert assert_member(cm.PK_ALGORITHM, algorithm, 'algorithm'), 
    assert assert_member(cm.PK_ENCODING, encoding, 'encoding'),
    assert assert_member(['Never', 'Always'], rotationPolicy, 'rotationPolicy'),
    algorithm: algorithm,
};


/**
    Three routines to generate issuerRef
 */
local _all_issuerRef(name) = {
    group: 'cert-manager.io',
    name: name
};
local issuerRef(name) = _all_issuerRef(name) {
    kind: 'Issuer'
};
local clusterIssuerRef(name) = _all_issuerRef(name) {
    kind: 'ClusterIssuer'
};




/*
    Certificate information:

    Who issues
    ----------
    issuer

    Spec for PK
    ------------
    private key
    
    Secret generated for certificate
    ---------------------------------
    secret (k8s)
        . secretName
        . secretTemplate
        . keystores

    subject
        X509 qualified name
    
    Duration and renewal time
    --------------------------
    duration
    renewBefore

    Contents ending up in the "subjectAltNames" section of the certificate
    These are all arrays of strings.
    - dnsNames
    - ipAddresses
    - uris
    If none is provided, a 'commonName' should be provided (e.g., a FQDN)

    usages: array of strings from cm.USAGES
    encodeUsagesInRequest: (bool)
    isCA:  add 'cert sign' in usages
*/


local dns_certificate(name, issuerRef, dnsName) = cm.Certificate {
    // See 
    // https://cert-manager.io/docs/reference/api-docs/#cert-manager.io/v1.CertificateSpec

    metadata: {
        name: name
    },

    spec: {
        duration: '2160h',      // 90d
        renewBefore: '360h',    // 15d
        issuerRef: issuerRef,
        dnsNames: [dnsName],
        privateKey: certificate_privateKey('RSA', 2048),
        secretName: name,
        usages: [
            'server auth', 
            'digital signature',
            'key encipherment'

        ],
    }

};




/**
    Export functions
 */

{
    selfSigned_issuer: selfSigned_issuer,
    certificate_privateKey: certificate_privateKey,
    issuerRef: issuerRef,
    clusterIssuerRef: clusterIssuerRef,
    dns_certificate: dns_certificate, 
}