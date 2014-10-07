# -*- coding: utf-8 -*-
import pytest
from laconia import ThingFactory
from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL
from rdflib.compare import to_isomorphic
import logging


logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def store():
    g = Graph()
    g.bind("rf", "http://rossfenning.co.uk/#")
    g.bind("foaf", "http://xmlns.com/foaf/0.1/")
    g.bind("rdf", RDF)
    g.bind("owl", OWL)
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


def test_setting_list_property(factory):
    factory("rf_todo",
      rdfs_range=[factory('rdf_List')],
      rdf_type=[factory('owl_FunctionalProperty')],
    )

    ross = factory('rf_me')
    ross.rf_todo = ['a', 'b', 'c']

    assert ['a', 'b', 'c'] == ross.rf_todo


def test_setting_sequence_property(factory):
    factory("rf_todo",
      rdfs_range=[factory('rdf_Seq')],
      rdf_type=[factory('owl_FunctionalProperty')],
    )

    ross = factory('rf_me')
    ross.rf_todo = ['a', 'b', 'c']

    assert ['a', 'b', 'c'] == ross.rf_todo


def test_allows_setting_another_thing_as_attr_value(factory):
    ross = factory('rf_me')
    cheese = factory('http://dbpedia.org/Cheese')
    ross.rf_likes.add(cheese)

    assert cheese in ross.rf_likes


def test_allows_setting_another_thing_as_attr_value_even_when_stores_are_different(factory):
    ross = factory('rf_me')
    factory2 = ThingFactory(Graph())
    cheese = factory2('http://dbpedia.org/Cheese')
    ross.rf_likes.add(cheese)

    assert cheese in ross.rf_likes


def test_relating_things_with_different_stores_unifies_facts(factory):
    ross = factory('rf_me')

    factory2 = ThingFactory(Graph())
    cheese = factory2('http://dbpedia.org/Cheese')
    cheese.rdfs_label.add('Cheese')

    ross.rf_likes.add(cheese)

    # Fact about cheese copies into subject's store
    assert (URIRef('http://dbpedia.org/Cheese'), RDFS.label, Literal('Cheese')) in ross._store


def test_getting_single_valued_uri_object(store):
    store.parse('foaf.rdf')
    factory = ThingFactory(store)

    ross = factory('rf_me')
    male = factory('rf_gender_male')

    ross.foaf_gender = male

    assert str(ross.foaf_gender) == str(male)


def test_creating_anonymous_things(factory):
    logging.info('TEST:\t\tCreating Ross')
    ross = factory('rf_me')
    logging.info('TEST:\t\tCreating Cheese')
    cheese = factory()
    logging.info('TEST:\t\tCalling cheese, cheese')
    cheese.rdfs_label.add('Cheese')

    logging.info('TEST:\t\tSaying Ross likes cheese')
    ross.rf_likes.add(cheese)

    logging.info('TEST:\t\tChecking Ross likes cheese')
    assert 'Cheese' in list(ross.rf_likes)[0].rdfs_label


def test_things_with_same_id_are_equal(factory):
    assert factory('rf_thing') == factory('rf_thing')


def test_things_with_different_ids_are_not_equal(factory):
    assert factory('rf_thing1') != factory('rf_thing2')


def test_things_equal_to_their_uriref(factory):
    uri = 'http://rossfenning.co.uk/#thing'
    thing = factory(uri)

    assert thing == URIRef(uri)


def test_list_all_properties(factory):
    ross = factory('rf_me')
    ross.rdfs_label.add('Ross')
    ross.rf_likes.add('Cheese')

    assert set(ross.properties()) == {factory('rdfs_label'), factory('rf_likes')}
