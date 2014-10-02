# -*- coding: utf-8 -*-
import pytest
from laconia import ThingFactory
from rdflib import Graph, URIRef, Literal
from rdflib.compare import to_isomorphic


@pytest.fixture
def store():
    g = Graph()
    g.store.bind("rf", "http://rossfenning.co.uk/#")
    g.bind("foaf", "http://xmlns.com/foaf/0.1/")
    return g


@pytest.fixture
def factory(store):
    return ThingFactory(store)


def test_creates_entity_with_type(factory):
    ross = factory("rf_me")
    ross.rdf_type.add(factory('foaf_Person'))

    expected = Graph()
    expected.add((
        URIRef('http://rossfenning.co.uk/#me'),
        URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'),
        URIRef('http://xmlns.com/foaf/0.1/Person')))

    assert to_isomorphic(factory.store) == to_isomorphic(expected)


def test_uses_alias(factory):
    factory.addAlias('favourite_cheese', 'http://rossfenning.co.uk/#favourite-cheese')

    ross = factory("rf_me")
    ross.favourite_cheese.add('Stinking Bishop')

    expected = Graph()
    expected.add((
        URIRef('http://rossfenning.co.uk/#me'),
        URIRef('http://rossfenning.co.uk/#favourite-cheese'),
        Literal('Stinking Bishop')))

    assert to_isomorphic(factory.store) == to_isomorphic(expected)


def test_adds_props_during_construction(store):
    factory = ThingFactory(store)

    # We must use a list for the value as name is not a functional property (can only have one value)
    _ = factory("rf_me", foaf_name=['Ross Fenning'])

    expected = Graph()
    expected.add((
        URIRef('http://rossfenning.co.uk/#me'),
        URIRef('http://xmlns.com/foaf/0.1/name'),
        Literal('Ross Fenning')))

    assert to_isomorphic(store) == to_isomorphic(expected)


def test_adds_unique_prop_during_construction(store):
    # Add the FOAF schema
    store.parse('foaf.rdf')
    factory = ThingFactory(store)

    # The FOAF schema tells us gender has only one value (we don't need to use a list)
    ross = factory("rf_me", foaf_gender='male')

    gender_fact = (
        URIRef('http://rossfenning.co.uk/#me'),
        URIRef('http://xmlns.com/foaf/0.1/gender'),
        Literal('male'))

    assert str(ross.foaf_gender) == 'male'


def test_rejects_attempts_to_access_unknown_private_attributes(factory):
    ross = factory('rf_me')
    with pytest.raises(AttributeError):
        ross._badger


def test_attribute_error_when_asking_for_unique_property_without_value(factory):
    ross = factory("rf_me")
    factory.store.parse('foaf.rdf')
    with pytest.raises(AttributeError):
        print ross.foaf_birthday


def test_setting_property_with_set(factory):
    ross = factory('rf_me')
    ross.foaf_myersBriggs = {'ENTP'}
    assert 'ENTP' in ross.foaf_myersBriggs


def test_rejects_setting_properties_as_weird_things(factory):
    ross = factory("rf_me")
    with pytest.raises(TypeError):
        ross.rf_dict = dict(this_will='fail')


def test_allows_setting_and_deleting_of_private_attributes(factory):
    ross = factory('rf_me')
    ross._badger = 'foo'
    assert ross._badger == 'foo'
    del ross._badger
    with pytest.raises(AttributeError):
        ross._badger


def test_allows_deleting_of_properties(factory):
    ross = factory('rf_me')

    ross.foaf_name.add('Ross Fenning')
    assert 'Ross Fenning' in ross.foaf_name

    del ross.foaf_name
    assert 'Ross Fenning' not in ross.foaf_name


def test_allows_deleting_of_properties_with_multiple_values(factory):
    ross = factory('rf_me')

    ross.foaf_name.add('Ross Fenning')
    ross.foaf_name.add('Miguel Sanchez')
    assert 'Ross Fenning' in ross.foaf_name
    assert 'Miguel Sanchez' in ross.foaf_name

    del ross.foaf_name
    assert 'Ross Fenning' not in ross.foaf_name
    assert 'Miguel Sanchez' not in ross.foaf_name
