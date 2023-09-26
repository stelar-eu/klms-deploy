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

    Parameters:
    -----------
    name (str): the name of the resource.
 */
local selfSigned_issuer(name) = cm.Issuer {
    metadata: {
        name: name
    },
    spec: cm.SelfSignedSpec
};



/**
    Return a K8s manifest for a cert-manager self-signed Issuer.

    Parameters:
    -----------
    name (str): the name of the resource.
 */
local selfSigned_clusterissuer(name) = cm.ClusterIssuer {
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

    // Constraint for RSA sizes
    assert size==null || algorithm!='RSA' || std.member([2048, 4096, 8192], size) : 
    "size for RSA algorithm must be one of 2048, 4096 or 8192",
    // Constraint for ECDSA sizes
    assert size==null || algorithm!='ECDSA' || std.member([256, 384, 521], size) :
    "size for ECDSA algorithm must be one of 256, 384 or 512",

    algorithm: algorithm,
    [if size!=null then 'size']: size,
    encoding: encoding,
    rotationPolicy: rotationPolicy,    
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



/*
    CA certificates request a CA key pair from a selfSigned issuer

    
 */
local ca_certificate(name, signing_secret, signing_issuerRef) = cm.Certificate {

    metadata: {
        name: name,
        // NOTE: namespace may need to be fixed to 'cert-manager'
    },

    spec: {
        isCA: true, 
        commonName: name,
        secretName: signing_secret,
        privateKey: certificate_privateKey('ECDSA', 256),
        issuerRef: signing_issuerRef,
    }

};


/*
    A CA specification contains the following fields:
    - name: string  -- the name of the CA issuer
    
    - namespaced: bool --  whether the issuer will be namespaced or a cluster issuer
    
    - secret: string|null -- the name of the secret with which to sign certificates.
    
    - issuerRef:  object|null -- an issuer to issue the CA signing certificate. 
        or none, in which case the secret is expected to exist.

    issuer         has value         null
    -------------------------------------------------
    secret
    -----          use issuer       secret must pre-exist
    has value                        
    -------------------------------------------------
    null           use issuer       self-signed issuer
                    secret_name = <name>-secret

    The returned object
*/
local CertificateAuthority(name, namespaced=false, secret=null, issuerRef=null) = {

    name: name,
    namespaced: namespaced,
    secret: secret,
    issuerRef: issuerRef,
    selfsignedsecret: (
        secret == null && issuerRef == null
    ),


    manifests(): {

        local issuer_kind = (
            if namespaced 
            then cm.Issuer 
            else cm.ClusterIssuer),

        local secret_name = (
            if secret==null 
            then name+'-secret' 
            else secret),

        ca_issuer:  issuer_kind + {

            metadata: {
                name: name,
            },

            spec: {
                ca: {
                    secretName: secret_name,
                }
            }
        },

        [if (secret == null && issuerRef == null) then 'secret_issuer']: selfSigned_clusterissuer(name+"-secret-issuer"),

        local ca_certificate_namespace = (if namespaced then {} else {namespace: 'cert-manager'}),

        [if (secret == null && issuerRef == null) then 'secret_cert']: 
            ca_certificate(name+'-certificate', secret_name, clusterIssuerRef(name+'-secret-issuer'))
            + {metadata+: ca_certificate_namespace }
            ,
        
        [if issuerRef != null then 'secret_cert']:
            ca_certificate(name+'-certificate', secret_name, issuerRef),

    }

};




/**
    Export functions
 */

{
    // Manifests for self-signed issuers
    selfSigned_issuer: selfSigned_issuer,
    selfSigned_clusterissuer: selfSigned_clusterissuer,

    // Fragment returning a private key spec for certificate objects
    certificate_privateKey: certificate_privateKey,

    // Fragments designating issuer/clusterissuer
    issuerRef: issuerRef,
    clusterIssuerRef: clusterIssuerRef,

    // Certificate manifest, for DNS authentication certificates.
    // Used for server auth, digital sigs and key encjpherment
    dns_certificate: dns_certificate, 

    // CA certificate manifest, this certificate is used to issue
    // a CA signing secret
    ca_certificate: ca_certificate,

    // A certificate authority consists of 
    // 1. a secret (for signing certificates), and
    // 2. The CA issuer / clusterissuer
    CertificateAuthority: CertificateAuthority,
}


/*

The following is an example of a CA issuer


apiVersion: v1
kind: Namespace
metadata:
  name: sandbox
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: my-selfsigned-ca
  namespace: cert-manager
spec:
  isCA: true
  commonName: my-selfsigned-ca
  secretName: root-secret
  privateKey:
    algorithm: ECDSA
    size: 256
  issuerRef:
    name: selfsigned-issuer
    kind: ClusterIssuer
    group: cert-manager.io
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: my-ca-issuer
spec:
  ca:
    secretName: root-secret


 */
