#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
laconia.py - a Simple API for RDF

Laconia (née Sparta) is a simple API for RDF that binds RDF nodes to Python
objects and RDF arcs to attributes of those Python objects. As 
such, it can be considered a "data binding" from RDF to Python.

Requires rdflib <http://www.rdflib.net/> version 2.3.1+.
"""

__license__ = """
Portions post-fork Copyright (c) 2014 Ross Fenning <ross.fenning@gmail.com>

Forked changes licensed under GPL v3+ (see LICENCE).

Original licence for Sparta pre-fork:

Copyright (c) 2001-2006 Mark Nottingham <mnot@pobox.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__version__ = "0.1.0"

from rdflib.term import Identifier as ID
from rdflib import URIRef as URI
from rdflib import BNode
from rdflib import Literal
from rdflib import RDF, RDFS

RDF_SEQi = "http://www.w3.org/1999/02/22-rdf-syntax-ns#_%s"
MAX_CARD = URI("http://www.w3.org/2002/07/owl#maxCardinality")
CARD = URI("http://www.w3.org/2002/07/owl#cardinality")
RESTRICTION = URI("http://www.w3.org/2002/07/owl#Restriction")
FUNC_PROP = URI("http://www.w3.org/2002/07/owl#FunctionalProperty")
ON_PROP = URI("http://www.w3.org/2002/07/owl#onProperty")
ONE = Literal("1")



class ThingFactory(object):
    """
    Fed a store, return a factory that can be used to instantiate
    Things into that world.
    """
    def __init__(self, store, schema_store=None, alias_map=None):
        """
        store - rdflib.Graph.Graph instance
        schema_store - rdflib.Graph.Graph instance; defaults to store
        """
        self.store = store
        self.schema_store = schema_store or self.store
        self.alias_map = alias_map or {}

    def __call__(self, ident, **props):
        """
        ident - either:
            a) None  (creates a new BNode)
            b) rdflib.URIRef.URIRef instance
            c) str in the form prefix_localname
        props - dict of properties and values, to be added. If the value is a list, its
                contents will be added to a ResourceSet.

        returns Thing instance
        """
        return Thing(self.store, self.schema_store, self.alias_map, ident, props)

    def addAlias(self, alias, uri):
        """
        Add an alias for an pythonic name to a URI, which overrides the 
        default prefix_localname syntax for properties and object names. Intended to 
        be used for URIs which are unmappable.
        
        E.g., 
          .addAlias("foobar", "http://example.com/my-unmappable-types#blah-type")
        will map the .foobar property to the provided URI.
        """
        self.alias_map[alias] = uri
    
class Thing(object):
    """ An RDF resource, as uniquely identified by a URI. Properties
        of the resource are available as attributes; for example:
        .prefix_localname is the property in the namespace mapped 
        to the "prefix" prefix, with the localname "localname".
        
        A "python literal datatype" is a datatype that maps to a Literal type; 
        e.g., int, float, bool.

        A "python data representation" is one of:
            a) a python literal datatype
            b) a self.__class__ instance
            c) a list containing a and/or b
    """
    
    def __init__(self, store, schema_store, alias_map, ident=None, props=None):
        """
        store - rdflib.Graph.Graph
        schema_store - rdflib.Graph.Graph
        ident - either:
            a) None  (creates a new BNode)
            b) rdflib.URIRef.URIRef instance
            c) str in the form prefix_localname
        props - dict of properties and values, to be added. If the value is a list, its
                contents will be added to a ResourceSet.
        """
        self._store = store
        self._schema_store = schema_store
        self._alias_map = alias_map

        self._id = self._AttrToURI(ident)

        if props is not None:
            for attr, obj in props.items():
                if isinstance(obj, list):
                    for o in obj:
                        self.__getattr__(attr).add(o)
                else:
                    self.__setattr__(attr, obj)
        
    def __getattr__(self, attr):
        """
        attr - either:
            a) str starting with _  (normal attribute access)
            b) str that is a URI
            c) str in the form prefix_localname

        returns a python data representation or a ResourceSet instance
        """
        if attr[0] == '_':
            raise AttributeError
        else:
            pred = self._AttrToURI(attr)

            if self._isUniqueObject(pred):
                try:
                    obj = self._store.objects(self._id, pred).next()
                except StopIteration:
                    raise AttributeError
                return self._rdf_to_python(pred, obj)
            else:
                return ResourceSet(self, pred)
                
    def __setattr__(self, attr, obj):
        """
        attr - either:
            a) str starting with _  (normal attribute setting)
            b) str that is a URI
            c) str in the form prefix_localname
        obj - a python data representation or a ResourceSet instance
        """
        if attr[0] == '_':
            self.__dict__[attr] = obj
        else:
            pred = self._AttrToURI(attr)

            if self._isUniqueObject(pred):
                self._store.remove((self._id, pred, None))
                self._store.add((self._id, pred, self._pythonToRdf(pred, obj)))
            elif isinstance(obj, ResourceSet) or type(obj) is type(set()):
                ResourceSet(self, pred, obj.copy())
            else:
                raise TypeError

    def __delattr__(self, attr):
        """
        attr - either:
            a) str starting with _  (normal attribute deletion)
            b) str that is a URI
            c) str in the form prefix_localname
        """        
        if attr[0] == '_':
            del self.__dict__[attr]
        else:
            self._store.remove((self._id, self._AttrToURI(attr), None))

    def _rdf_to_python(self, pred, obj):
        """
        Given a RDF predicate and object, return the equivalent Python object.
        
        pred - rdflib.URIRef.URIRef instance
        obj - rdflib.Identifier.Identifier instance

        returns a python data representation
        """ 
        obj_types = self._getObjectTypes(pred, obj)
        if isinstance(obj, Literal):  # typed literals
            return obj.toPython()
        elif RDF.List in obj_types:
            return self._listToPython(obj)
        elif RDF.Seq in obj_types:
            l, i = [], 1
            while True:
                counter = URI(RDF_SEQi % i)
                try:
                    item = self._store.triples((obj, counter, None)).next()[2]
                except StopIteration:
                    return l
                l.append(self._rdf_to_python(counter, item))
                i += 1
        elif isinstance(obj, ID):
            return self.__class__(self._store, self._schema_store, self._alias_map, obj)
        else:
            raise ValueError

    def _pythonToRdf(self, pred, obj, lang=None):
        """
        Given a Python predicate and object, return the equivalent RDF object.
        
        pred - rdflib.URIRef.URIRef instance
        obj - a python data representation
            
        returns rdflib.Identifier.Identifier instance
        """
        obj_types = self._getObjectTypes(pred, obj)
        if RDF.List in obj_types:
            blank = BNode()
            self._pythonToList(blank, obj)   ### this actually stores things... 
            return blank
        elif RDF.Seq in obj_types:  ### so will this
            blank = BNode()
            i = 1
            for item in obj:
                counter = URI(RDF_SEQi % i)
                self._store.add((blank, counter, self._pythonToRdf(counter, item)))
                i += 1
            return blank
        elif isinstance(obj, self.__class__):
            if obj._store is not self._store:
                obj.copyTo(self._store)  ### and this...
            return obj._id
        else:
            return self._pythonToLiteral(obj, obj_types, lang=lang)

    def _pythonToLiteral(self, obj, obj_types, lang=None):
        """
        obj - a python literal datatype
        obj_types - iterator yielding rdflib.URIRef instances
        
        returns rdflib.Literal.Literal instance
        """
        for obj_type in obj_types:
            return Literal(obj, datatype=obj_type, lang=lang)
        return Literal(obj, lang=lang)

    def _listToPython(self, subj):
        """
        Given a RDF list, return the equivalent Python list.
        
        subj - rdflib.Identifier instance

        returns list of python data representations
        """
        try:
            first = self._store.triples((subj, RDF.first, None)).next()[2]
        except StopIteration:
            return []
        try:
            rest = self._store.triples((subj, RDF.rest, None)).next()[2]
        except StopIteration:
            return ValueError
        return [self._rdf_to_python(RDF.first, first)] + self._listToPython(rest)  ### type first?

    def _pythonToList(self, subj, members):
        """
        Given a Python list, store the eqivalent RDF list.
        
        subj - rdflib.Identifier.Identifier instance
        members - list of python data representations
        """
        first = self._pythonToRdf(RDF.first, members[0])
        self._store.add((subj, RDF.first, first))
        if len(members) > 1:
            blank = BNode()
            self._store.add((subj, RDF.rest, blank))
            self._pythonToList(blank, members[1:])
        else:
            self._store.add((subj, RDF.rest, RDF.nil))
            
    def _AttrToURI(self, attr):
        """
        Given an attribute, return a URIRef.
        
        attr - str in the form prefix_localname
        
        returns rdflib.URIRef.URIRef instance
        """
        if isinstance(attr, ID):
            return attr

        if attr is None:
            return BNode()

        if ':' in attr:
            return URI(attr)

        if attr in self._alias_map:
            return URI(self._alias_map[attr])
        else:
            prefix, localname = attr.split("_", 1)
            return URI("".join([self._store.namespace_manager.store.namespace(prefix), localname]))

    def _URIToAttr(self, uri):
        """
        Given a URI, return an attribute.
        
        uri - str that is a URI
        
        returns str in the form prefix_localname. Not the most efficient thing around.
        """
        for alias, alias_uri in self._alias_map.items():
            if uri == alias_uri:
                return alias
        for ns_prefix, ns_uri in self._store.namespace_manager.namespaces():
            if ns_uri == uri[:len(ns_uri)]:
                return "_".join([ns_prefix, uri[len(ns_uri):]])
        raise ValueError

    def _getObjectTypes(self, pred, obj):
        """
        Given a predicate and an object, return a list of the object's types.
        
        pred - rdflib.URIRef.URIRef instance
        obj - rdflib.Identifier.Identifier instance
        
        returns list containing rdflib.Identifier.Identifier instances
        """
        obj_types = [o for (s, p, o) in self._schema_store.triples((pred, RDFS.range, None))]

        if isinstance(obj, URI):
            obj_types += [o for (s, p, o) in self._store.triples((obj, RDF.type, None))]
        return obj_types

    def _isUniqueObject(self, pred):
        """
        Given a predicate, figure out if the object has a cardinality greater than one.
        
        pred - rdflib.URIRef.URIRef instance
        
        returns bool
        """
        # pred rdf:type owl:FunctionalProperty - True
        if (pred, RDF.type, FUNC_PROP) in self._schema_store:
            return True
        # subj rdf:type [ rdfs:subClassOf [ a owl:Restriction; owl:onProperty pred; owl:maxCardinality "1" ]] - True
        # subj rdf:type [ rdfs:subClassOf [ a owl:Restriction; owl:onProperty pred; owl:cardinality "1" ]] - True
        subj_types = [o for (_, _, o) in self._store.triples((self._id, RDF.type, None))]
        for type in subj_types:
            superclasses = [o for (s, p, o) in \
              self._schema_store.objects(type, RDFS.subClassOf)]
            for superclass in superclasses:
                if (
                    (superclass, RDF.type, RESTRICTION) in self._schema_store and
                    (superclass, ON_PROP, pred) in self._schema_store
                   ) and \
                   (
                    (superclass, MAX_CARD, ONE) in self._schema_store or 
                    (superclass, CARD, ONE) in self._schema_store
                   ): return True
        return False

    def __repr__(self):
        return self._id
        
    def __str__(self):
        try:
            return self._URIToAttr(self._id)
        except ValueError:
            return str(self._id)
                
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._id == other._id
        elif isinstance(other, ID):
            return self._id == other
    
    def __ne__(self, other):
        if self is other: return False
        else: return True
        
    def properties(self):
        """
        List unique properties.
        
        returns list containing self.__class__ instances
        """
        return [self.__class__(self._store, self._schema_store, self._alias_map, p) 
          for (s,p,o) in self._store.triples((self._id, None, None))]

    def copyTo(self, store):
        """
        Recursively copy statements to the given store.
        
        store - rdflib.Store.Store
        """
        for (s, p, o) in self._store.triples((self._id, None, None)):
            store.add((s, p, o))
            if isinstance(o, (URI, BNode)):
                self.__class__(self._store, self._schema_store, self._alias_map, o).copyTo(store)
        
        
class ResourceSet:
    """
    A set interface to the object(s) of a non-unique RDF predicate. Interface is a subset
    (har, har) of set().copy() returns a set.
    """
    def __init__(self, subject, predicate, iterable=None):
        """
        subject - rdflib.Identifier.Identifier instance
        predicate -  rdflib.URIRef.URIRef instance
        iterable - 
        """
        self._subject = subject
        self._predicate = predicate
        self._store = subject._store
        if iterable is not None:
            for obj in iterable:
                self.add(obj)
    def __len__(self):
        return len(list(
          self._store.triples((self._subject._id, self._predicate, None))))
    def __contains__(self, obj):
        if isinstance(obj, self._subject.__class__):    
            obj = obj._id
        else: ### doesn't use pythonToRdf because that might store it
            obj_types = self._subject._getObjectTypes(self._predicate, obj) 
            obj = self._subject._pythonToLiteral(obj, obj_types)
        return (self._subject._id, self._predicate, obj) in self._store
    def __iter__(self):
        for (s, p, o) in \
          self._store.triples((self._subject._id, self._predicate, None)):
            yield self._subject._pythonToRdf(self._predicate, o, lang=o.language)
    def copy(self):
        return set(self)
    def add(self, obj):
        self._store.add((self._subject._id, self._predicate, 
          self._subject._pythonToRdf(self._predicate, obj)))
    def remove(self, obj):
        if not obj in self:
            raise KeyError
        self.discard(obj)
    def discard(self, obj):
        if isinstance(obj, self._subject.__class__):
            obj = obj._id
        else: ### doesn't use pythonToRdf because that might store it
            obj_types = self._subject._getObjectTypes(self._predicate, obj)
            obj = self._subject._pythonToLiteral(obj, obj_types)
        self._store.remove((self._subject._id, self._predicate, obj))
    def clear(self):
        self._store.remove((self._subject, self._predicate, None))
