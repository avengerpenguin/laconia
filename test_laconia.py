# -*- coding: utf-8 -*-
import unittest
from laconia import ThingFactory
from rdflib import Graph, URIRef
from rdflib.compare import to_isomorphic


class TestLaconia(unittest.TestCase):
    def setUp(self):
        self.store = Graph()
        self.store.bind("rf", "http://rossfenning.co.uk/#")
        self.store.bind("foaf", "http://xmlns.com/foaf/0.1/")
        self.Thing = ThingFactory(self.store)

    def test_creates_entity_with_type(self):
        ross = self.Thing("rf_me")
        ross.rdf_type.add(self.Thing("foaf_Person"))

        expected = Graph()
        expected.add((
            URIRef('http://rossfenning.co.uk/#me'),
            URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'),
            URIRef('http://xmlns.com/foaf/0.1/Person')))

        self.assertEqual(to_isomorphic(self.store), to_isomorphic(expected))
