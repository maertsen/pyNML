from rdflib import Graph, URIRef, Namespace, Literal
from rdflib.namespace import RDF
from datetime import date
import hashlib
from urllib import quote
import logging

logging.basicConfig()

class NML(object):
    labelStore = {}
    baseurn = u'urn:ogf:network'
    
    def __init__(self, basename, extras=[]):
        self.setBaseName(basename, extras)
    
        self.graph = Graph()
        self.graph.bind('nml', 'http://schemas.ogf.org/nml/2013/05/base#')

    def setBaseName(self, basename, extras=[]):
        self.basename = ':'.join([self.baseurn, quote(basename), date.today().strftime('%Y')] + [quote(e) for e in extras])
    
    def getURN(self, name, extras=[], randomize=False):
        assert not isinstance(name, URIRef)
        assert len(extras) < 5

        if randomize:
            import random
            import string
            # put 6 character random string into URN to improve uniqueness
            extras.append(''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(6)))

    	return URIRef(':'.join([self.basename, quote(name)] + [quote(e) for e in extras]))

    def getPortURN(self, device, port, direction, name=None, extras=[]):
        if isinstance(device, URIRef):
            device = str(device).split(':')[-1] # ugly hack

        extras = [port]+extras
        # direction always comes last to provide a tiny bit of introspection
        if direction:
            extras += [direction]

        return self.getURN(device, extras)

    def addNode(self, name):
        dev_urn = self.getURN(name)
        
        # type
        self.graph.add( (dev_urn, RDF.type, self.term('Node')) )
        # name
        self.graph.add( (dev_urn, self.term('name'), Literal(name)) )

        return dev_urn

    def addPort(self, device, port, direction, encoding=None, name=None, extras=[]):
        assert not isinstance(port, URIRef)
        assert not isinstance(direction, URIRef)

        port_urn = self.getPortURN(device, port, direction, name, extras=extras)

        self.graph.add( (port_urn, RDF.type, self.term('Port')) )

        if encoding:
            assert isinstance(encoding, URIRef)
            self.graph.add( (port_urn, self.term('encoding'), encoding) )

        if name:
            self.graph.add( (port_urn, self.term('name'), Literal(name)) )

        return port_urn

    def addLink(self, name=None):
        # generate a name to ensure uniqueness
        link_urn = self.getURN('link', [], randomize=True)

        self.graph.add( (link_urn, RDF.type, self.term('Link')) )
        if name:
            self.graph.add( (link_urn, self.term('name'), Literal(name)) )

        return link_urn

    def addTopology(self, name=None):
        if not name: name = []
        topology_urn = self.getURN(name)

        self.graph.add( (topology_urn, RDF.type, self.term('Topology')) )
        self.graph.add( (topology_urn, self.term('version'), Literal(date.today().strftime('%Y%m%d'))) )

        return topology_urn

    def addSwitchingService(self, device, name=None):
        service_urn = self.getURN(device, ['SwitchingService'], randomize=True)

        self.graph.add( (service_urn, RDF.type, self.term('SwitchingService')) )

        if name:
            self.graph.add( (service_urn, self.term('name'), Literal(name)) )

        return service_urn

    def addAdaptationService(self, device, adaptationType, adaptationFunction, name=None):
        assert adaptationType in ['AdaptationService', 'DeadaptationService']
        assert not isinstance(device, URIRef)
        assert isinstance(adaptationFunction, URIRef)

        service_urn = self.getURN(device, [adaptationType], randomize=True)

        self.graph.add( (service_urn, RDF.type, self.term(adaptationType)) )
        self.graph.add( (service_urn, self.term('adaptationFunction'), adaptationFunction) )

        if name:
            self.graph.add( (service_urn, self.term('name'), Literal(name)) )

        return service_urn

    def addLabel(self, node_urn, labelType, labelValue):
        assert isinstance(node_urn, URIRef)
        assert isinstance(labelType, URIRef)

        try:
            label_urn = self.labelStore[labelType][labelValue]
        except KeyError:
            label_urn = self.getURN('label', [], randomize=True)

            self.graph.add( (label_urn, RDF.type, self.term('Label')) )
            self.graph.add( (label_urn, self.term('type'), labelType) )
            self.graph.add( (label_urn, self.term('value'), Literal(labelValue)) )

            self.labelStore.setdefault(labelType, {})[labelValue] = label_urn

        self.relate(node_urn, label_urn, 'hasLabel')

    def addAdaptationPorts(self, adaptationServiceURN, providedPortsURNS):
        assert isinstance(adaptationServiceURN, URIRef)

        for portURN in providedPortsURNS:
            assert isinstance(portURN, URIRef)
            self.relate(adaptationServiceURN, portURN, 'providesPort')

    def addBidirectionalPort(self, device, port, portA, portB, extras=[]):
        assert isinstance(portA, URIRef)
        assert isinstance(portB, URIRef)

        group_urn = self.getURN(device, extras=[port]+extras)

        self.graph.add( (group_urn, RDF.type, self.term('BidirectionalPort')) )
        self.relate(group_urn, portA, 'hasPort')
        self.relate(group_urn, portB, 'hasPort')

        return group_urn

    def relate(self, subj, obj, relation):
        assert isinstance(subj, URIRef)
        assert isinstance(obj, URIRef) or isinstance(obj, Literal)
        assert not isinstance(relation, URIRef)

        self.graph.add( (subj, self.term(relation), obj) )

    def getNML(self):
        return self.graph.serialize(format='pretty-xml')
    
    @staticmethod
    def term(name):
        return Namespace('http://schemas.ogf.org/nml/2013/05/base#').term(name)

    @staticmethod
    def nonStandardizedTerm(name):
        return Namespace('https://rtsn.nl/thesis/nml/').term(name)

    @staticmethod
    def directionToPortType(direction, reverse=False):
        if reverse:
            direction = NML.reverse(direction)

        return {'in':   'hasInboundPort',
                'out':  'hasOutboundPort'}[direction]

    @staticmethod
    def directionToLinkType(direction, reverse=False):
        if reverse:
            direction = NML.reverse(direction)

        return {'in':   'isSink',
                'out':  'isSource'}[direction]

    @staticmethod
    def directionToAdaptationType(direction, reverse=False):
        if reverse:
            direction = NML.reverse(direction)

        return {'in':   'DeadaptationService',
                'out':  'AdaptationService'}[direction]

    @staticmethod
    def reverse(direction):
        return {'in': 'out',
                'out': 'in'}[direction]

    @staticmethod
    def encoding(key):
        return {'duct': NML.nonStandardizedTerm('cable'),
                'fiber': NML.nonStandardizedTerm('photonic')}[key]

    @staticmethod
    def adaptationFunction(key):
        return {'duct': NML.nonStandardizedTerm('duct#fiber')
               ,'fiber': NML.nonStandardizedTerm('fiber#ethernet')
               ,'ethernet': NML.nonStandardizedTerm('ethernet#vlan')
               }[key]

    @staticmethod
    def labelType(key):
        return  {'fibernumber': NML.nonStandardizedTerm('fiber#number')
                ,'vlan':        NML.nonStandardizedTerm('ethernet#vlan')
                }[key]

    @staticmethod
    def splitPort(port):
        assert isinstance(port, URIRef)

        direction = str(port).split(':')[-1]
        port_urn_part = port[:-len(direction)-1]

        return (port_urn_part, direction)
