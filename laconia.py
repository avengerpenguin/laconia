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

from rdflib.term import Identifier as ID, Node
from rdflib import URIRef as URI
from rdflib import BNode, Literal, RDF, RDFS
import logging


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
        logging.debug('__init__:\t\tCreating Laconic factory with store %s and schema store %s and alias map %s',
                      store, schema_store, alias_map)
        self.store = store
        self.schema_store = schema_store or self.store
        self.alias_map = alias_map or {}

    def __call__(self, ident=None, **props):
        """
        ident - either:
            a) None  (creates a new BNode)
            b) rdflib.URIRef.URIRef instance
            c) str in the form prefix_localname
        props - dict of properties and values, to be added. If the value is a list, its
                contents will be added to a ResourceSet.

        returns Thing instance
        """
        logging.debug('__call__:\t\tFactory invoked to create "%s" with props %s', ident, props)
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
        logging.debug('addAlias:\t\tAdding alias %s for URI %s', alias, uri)
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
        logging.debug('__init__:\t\tCreating entity with ident %s' % ident)
        self._store = store
        self._schema_store = schema_store
        self._alias_map = alias_map

        self._id = self._AttrToURI(ident)

        if props is not None:
            logging.debug('__init__:\t\tAdditional props given during entity creation: %s' % props)
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
        logging.debug('__getattr__:\t\tGetting attribute %s for entity %s', attr, self)
        if attr[0] == '_':
            raise AttributeError
        else:
            pred = self._AttrToURI(attr)

            if self._isUniqueObject(pred):
                logging.debug('__getattr__:\t\tPredicate %s is unique. Trying to return single Python value.', pred)
                try:
                    obj = self._store.objects(self._id, pred).next()
                except StopIteration:
                    raise AttributeError
                return self._rdf_to_python(pred, obj)
            else:
                logging.debug('__getattr__:\t\tPredicate %s is multivalued. Returning a ResourceSet.', pred)
                return ResourceSet(self, pred)
                
    def __setattr__(self, attr, obj):
        """
        attr - either:
            a) str starting with _  (normal attribute setting)
            b) str that is a URI
            c) str in the form prefix_localname
        obj - a python data representation or a ResourceSet instance
        """
        logging.debug('__setattr__:\t\tSetting attribute %s to %s', attr, obj)
        if attr[0] == '_':
            self.__dict__[attr] = obj
        else:
            pred = self._AttrToURI(attr)

            if self._isUniqueObject(pred):
                logging.debug('__setattr__:\t\tPredicate %s is unique. Fully overwriting any previous value, if any.', pred)
                self._store.remove((self._id, pred, None))
                obj_rdf = self._python_to_rdf(pred, obj)
                self._store.add((self._id, pred, obj_rdf))
            elif isinstance(obj, ResourceSet) or type(obj) is type(set()):
                logging.debug('__setattr__:\t\tPredicate %s is multivalued. Creating object as a ResourceSet that may be added to.', pred)
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
        
        pred - rdflib.URIRef instance
        obj - rdflib.Identifier instance

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
                    item = self._store.objects(obj, counter).next()
                except StopIteration:
                    return l
                l.append(self._rdf_to_python(counter, item))
                i += 1
        elif isinstance(obj, ID):
            return self.__class__(self._store, self._schema_store, self._alias_map, obj)
        else:
            raise ValueError

    def _python_to_rdf(self, pred, obj, lang=None):
        """
        Given a Python predicate and object, return the equivalent RDF object.
        
        pred - rdflib.URIRef.URIRef instance
        obj - a python data representation
            
        returns rdflib.Identifier.Identifier instance
        """
        logging.debug('_python_to_rdf:\tAttempting to convert Python object %s (type %s) to RDF (predicate %s).', obj, type(obj), pred)

        obj_types = self._getObjectTypes(pred, obj)
        logging.debug('_python_to_rdf:\tInferred objects of predicate %s should be types: %s', pred, obj_types)
        if RDF.List in obj_types:
            logging.debug('_python_to_rdf:\tPredicate %s takes an RDF List; constructing list now.', pred)
            blank = BNode()
            self._pythonToList(blank, obj)   ### this actually stores things... 
            return blank
        elif RDF.Seq in obj_types:  ### so will this
            logging.debug('_python_to_rdf:\tPredicate %s takes an RDF Sequence; constructing list now.', pred)
            blank = BNode()
            i = 1
            for item in obj:
                counter = URI(RDF_SEQi % i)
                self._store.add((blank, counter, self._python_to_rdf(counter, item)))
                i += 1
            return blank
        elif isinstance(obj, self.__class__):
            logging.debug('_python_to_rdf:\tObject seems to be another Thing. Returning %s (type %s)',
                          obj._id, type(obj._id))
            if obj._store is not self._store:
                obj.copyTo(self._store)  ### and this...
            return obj._id
        else:
            logging.debug('_python_to_rdf:\tLeaving RDFlib to determine type of %s (type %s)', obj, type(obj))
            return self._python_to_literal(obj, obj_types, lang=lang)

    def _python_to_literal(self, obj, obj_types, lang=None):
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
            first = self._store.objects(subj, RDF.first).next()
        except StopIteration:
            return []
        try:
            rest = self._store.objects(subj, RDF.rest).next()
        except StopIteration:
            return ValueError
        return [self._rdf_to_python(RDF.first, first)] + self._listToPython(rest)  ### type first?

    def _pythonToList(self, subj, members):
        """
        Given a Python list, store the eqivalent RDF list.
        
        subj - rdflib.Identifier.Identifier instance
        members - list of python data representations
        """
        first = self._python_to_rdf(RDF.first, members[0])
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
        logging.debug('_AttrToURI:\t\tTrying to convert %s to a URI.', attr)
        if isinstance(attr, ID):
            logging.debug('_AttrToURI:\t\tAttr % is already a URI.', attr)
            return attr

        if attr is None:
            logging.debug('_AttrToURI:\t\tAttr %s not set, so using blank node.', attr)
            return BNode()

        if ':' in attr:
            logging.debug('_AttrToURI:\t\tAttr %s contains a colon, so trying as a URI..', attr)
            return URI(attr)

        if attr in self._alias_map:
            logging.debug('_AttrToURI:\t\tAttr %s in alias map, so using URI from there.', attr)
            return URI(self._alias_map[attr])
        else:
            prefix, localname = attr.split("_", 1)
            logging.debug('_AttrToURI:\t\tAttr %s split into %s and %s.', attr, prefix, localname)
            return URI("".join([self._store.namespace_manager.store.namespace(prefix), localname]))


    def _getObjectTypes(self, pred, obj):
        """
        Given a predicate and an object, return a list of the object's types.
        
        pred - rdflib.URIRef instance
        obj - rdflib.Identifier instance
        
        returns list containing rdflib.Identifier instances
        """
        obj_types = list(self._schema_store.objects(pred, RDFS.range))

        if isinstance(obj, URI):
            obj_types += list(self._store.objects(obj, RDF.type))

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
        return str(self._id)
                
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._id == other._id
        elif isinstance(other, ID):
            return self._id == other
    
    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._id)

    def properties(self):
        """
        List unique properties.
        
        returns list containing self.__class__ instances
        """
        return [self.__class__(self._store, self._schema_store, self._alias_map, p)
                for (s, p, o) in self._store.triples((self._id, None, None))]

    def copyTo(self, store):
        """
        Recursively copy statements to the given store.
        
        store - rdflib.Store.Store
        """
        print self._id, list(self._store.triples((None, None, None)))
        for (s, p, o) in self._store.triples((self._id, None, None)):
            logging.debug('Copying %s, %s, %s', s, p, o)
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
        logging.debug('__init__:\t\tCreating ResourceSet for %s, %s', subject, predicate)
        self._subject = subject
        self._predicate = predicate
        self._store = subject._store
        if iterable is not None:
            for obj in iterable:
                logging.debug('__init__:\t\tAdding %s (type %s) to ResourceSet', obj, type(obj))
                self.add(obj)

    def __len__(self):
        return len(list(self._store.objects(self._subject._id, self._predicate)))

    def __contains__(self, obj):
        if isinstance(obj, self._subject.__class__):    
            obj = obj._id
        else: ### doesn't use pythonToRdf because that might store it
            obj_types = self._subject._getObjectTypes(self._predicate, obj) 
            obj = self._subject._python_to_literal(obj, obj_types)
        return (self._subject._id, self._predicate, obj) in self._store

    def __iter__(self):
        for o in self._store.objects(self._subject._id, self._predicate):
            logging.debug('__iter__:\t\tFound object %s (type %s) in ResourceSet', o, type(o))
            if isinstance(o, Literal):
                yield self._subject._rdf_to_python(self._predicate, o)
            else:
                yield self._subject._rdf_to_python(self._predicate, o)

    def copy(self):
        return set(self)

    def add(self, obj):
        logging.debug('add:\t\t\tAdding %s (type %s) to ResourceSet for predicate %s.', obj, type(obj), self._predicate)
        self._store.add((self._subject._id, self._predicate,
          self._subject._python_to_rdf(self._predicate, obj)))

    def remove(self, obj):
        if not obj in self:
            raise KeyError
        self.discard(obj)

    def discard(self, obj):
        if isinstance(obj, self._subject.__class__):
            obj = obj._id
        else: ### doesn't use pythonToRdf because that might store it
            obj_types = self._subject._getObjectTypes(self._predicate, obj)
            obj = self._subject._python_to_literal(obj, obj_types)
        self._store.remove((self._subject._id, self._predicate, obj))

    def clear(self):
        self._store.remove((self._subject, self._predicate, None))
