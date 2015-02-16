#!/usr/bin/env python

from distutils.core import setup

setup(name='laconia',
		version = '0.2.11',
		py_modules = ['laconia'],
		author = 'Ross Fenning',
		author_email = 'ross.fenning@gmail.com',
		url = 'http://github.com/avengerpenguin/laconia',
		description = 'Simple API for RDF',
		long_description = """Laconia is a Python API for RDF that is designed
to help easily learn and navigate the Semantic Web programmatically. 
Unlike other RDF interfaces, which are generally triple-based, Laconia
binds RDF nodes to Python objects and RDF arcs to attributes of those 
Python objects.""",
		license = 'GPLv3+',
		classifiers = [
		  'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
		  'Operating System :: OS Independent',
		  'Programming Language :: Python',
		  'Topic :: Software Development :: Libraries :: Python Modules',
		],
	)
