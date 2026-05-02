/*
    Service configuration and generation

 */

local k = import "k.libsonnet";


/* K8S API MODEL */
local deploy = k.apps.v1.deployment;
local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local servicePort = k.core.v1.servicePort;
local volumeMount = k.core.v1.volumeMount;
local pod = k.core.v1.pod;
local vol = k.core.v1.volume;
local service = k.core.v1.service;
local cm = k.core.v1.configMap;
local secret = k.core.v1.secret;


{

    /**
        Used to create headless services
    */
    headlessService: {
        /*
            Return a manifest for a headless Service.

            Headless services are 

            name(str): the name of the resource
            component(str): annotation value for 'app.kubernetes.io/component' to select on
            port(int): the port of the service
            portName(str, optional): the name of the port
        */
        new(name, component, port, portName=null):: service.new(name, {
                'app.kubernetes.io/component': component
            },
            [
                if portName != null then
                    servicePort.newNamed(portName, port, port)
                else
                    servicePort.new(port, port)
            ]
        )
        + service.spec.withClusterIP("None")
    },


    // serviceFor create service for a given deployment.
    serviceFor(deployment, ignored_labels=[], nameFormat='%(container)s-%(port)s')::
        
        local ports = [
            servicePort.newNamed(
                name=(nameFormat % { container: c.name, port: port.name }),
                port=port.containerPort,
                targetPort=port.containerPort
        ) 
        +
        if std.objectHas(port, 'protocol')
        then servicePort.withProtocol(port.protocol)
        else {}
        
        for c in deployment.spec.template.spec.containers
        for port in (c + container.withPortsMixin([])).ports
        ];
        
        local labels = {
            [x]: deployment.spec.template.metadata.labels[x]
            for x in std.objectFields(deployment.spec.template.metadata.labels)
            if std.count(ignored_labels, x) == 0
        };

        service.new(
            deployment.metadata.name,  // name
            labels,  // selector
            ports,
        ) 
        + service.mixin.metadata.withLabels({ name: deployment.metadata.name })
        ,


    // serviceFor create service for a given deployment.
    serviceForPod(thepod, ignored_labels=[], nameFormat='%(container)s-%(port)s')::
        
        local ports = [
            servicePort.newNamed(
                name=(nameFormat % { container: c.name, port: port.name }),
                port=port.containerPort,
                targetPort=port.containerPort
        ) 
        +
        if std.objectHas(port, 'protocol')
        then servicePort.withProtocol(port.protocol)
        else {}
        
        for c in thepod.spec.containers
        for port in (c + container.withPortsMixin([])).ports
        ];
        
        local labels = {
            [x]: thepod.metadata.labels[x]
            for x in std.objectFields(thepod.metadata.labels)
            if std.count(ignored_labels, x) == 0
        };

        service.new(
            thepod.metadata.name,  // name
            labels,  // selector
            ports,
        ) 
        + service.mixin.metadata.withLabels({ name: thepod.metadata.name })
        ,



}