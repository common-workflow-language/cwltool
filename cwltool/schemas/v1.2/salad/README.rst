|Linux Build Status| |Code coverage| |CII Best Practices|

.. |Linux Build Status| image:: https://github.com/common-workflow-language/schema-salad/actions/workflows/ci-tests.yml/badge.svg?branch=main
   :target: https://github.com/common-workflow-language/schema-salad/actions/workflows/ci-tests.yml
.. |Code coverage| image:: https://codecov.io/gh/common-workflow-language/schema_salad/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/common-workflow-language/schema_salad
.. |CII Best Practices| image:: https://bestpractices.coreinfrastructure.org/projects/1867/badge
   :target: https://bestpractices.coreinfrastructure.org/projects/1867

Schema Salad
------------

Salad is a schema language for describing JSON or YAML structured
linked data documents.  Salad schema describes rules for
preprocessing, structural validation, and hyperlink checking for
documents described by a Salad schema. Salad supports rich data
modeling with inheritance, template specialization, object
identifiers, object references, documentation generation, code
generation, and transformation to RDF_. Salad provides a bridge
between document and record oriented data modeling and the Semantic
Web.

The Schema Salad library is Python 3.6+ only.

Usage
-----

::

   $ pip install schema_salad

To install from source::

  git clone https://github.com/common-workflow-language/schema_salad
  cd schema_salad
  python3 setup.py install

Commands
--------

Schema salad can be used as a command line tool or imported as a Python module::

   $ schema-salad-tool
   usage: schema-salad-tool [-h] [--rdf-serializer RDF_SERIALIZER]
                         [--print-jsonld-context | --print-rdfs | --print-avro
                         | --print-rdf | --print-pre | --print-index
                         | --print-metadata | --print-inheritance-dot
                         | --print-fieldrefs-dot | --codegen language
                         | --print-oneline]
                         [--strict | --non-strict] [--verbose | --quiet
                         | --debug]
                         [--version]
                         [schema] [document]

   $ python
   >>> import schema_salad

Validate a schema::

   $ schema-salad-tool myschema.yml

Validate a document using a schema::

   $ schema-salad-tool myschema.yml mydocument.yml

Generate HTML documentation::

   $ schema-salad-tool myschema.yml > myschema.html

Get JSON-LD context::

   $ schema-salad-tool --print-jsonld-context myschema.yml mydocument.yml

Convert a document to JSON-LD::

   $ schema-salad-tool --print-pre myschema.yml mydocument.yml > mydocument.jsonld

Generate Python classes for loading/generating documents described by the schema::

   $ schema-salad-tool --codegen=python myschema.yml > myschema.py

Display inheritance relationship between classes as a graphviz 'dot' file and
render as SVG::

   $ schema-salad-tool --print-inheritance-dot myschema.yml | dot -Tsvg > myschema.svg


Quick Start
-----------

Let's say you have a 'basket' record that can contain items measured either by
weight or by count.  Here's an example::

   basket:
     - product: bananas
       price: 0.39
       per: pound
       weight: 1
     - product: cucumbers
       price: 0.79
       per: item
       count: 3

We want to validate that all the expected fields are present, the
measurement is known, and that "count" cannot be a fractional value.
Here is an example schema to do that::

   - name: Product
     doc: |
       The base type for a product.  This is an abstract type, so it
       can't be used directly, but can be used to define other types.
     type: record
     abstract: true
     fields:
       product: string
       price: float

   - name: ByWeight
     doc: |
       A product, sold by weight.  Products may be sold by pound or by
       kilogram.  Weights may be fractional.
     type: record
     extends: Product
     fields:
       per:
         type:
           type: enum
           symbols:
             - pound
             - kilogram
         jsonldPredicate: '#per'
       weight: float

   - name: ByCount
     doc: |
       A product, sold by count.  The count must be a integer value.
     type: record
     extends: Product
     fields:
       per:
         type:
           type: enum
           symbols:
             - item
         jsonldPredicate: '#per'
       count: int

   - name: Basket
     doc: |
       A basket of products.  The 'documentRoot' field indicates it is a
       valid starting point for a document.  The 'basket' field will
       validate subtypes of 'Product' (ByWeight and ByCount).
     type: record
     documentRoot: true
     fields:
       basket:
         type:
           type: array
           items: Product

You can check the schema and document in schema_salad/tests/basket_schema.yml
and schema_salad/tests/basket.yml::

   $ schema-salad-tool basket_schema.yml basket.yml
   Document `basket.yml` is valid


Documentation
-------------

See the specification_ and the metaschema_ (salad schema for itself).  For an
example application of Schema Salad see the Common Workflow Language_.


Rationale
---------

The JSON data model is an popular way to represent structured data.  It is
attractive because of it's relative simplicity and is a natural fit with the
standard types of many programming languages.  However, this simplicity comes
at the cost that basic JSON lacks expressive features useful for working with
complex data structures and document formats, such as schemas, object
references, and namespaces.

JSON-LD is a W3C standard providing a way to describe how to interpret a JSON
document as Linked Data by means of a "context".  JSON-LD provides a powerful
solution for representing object references and namespaces in JSON based on
standard web URIs, but is not itself a schema language.  Without a schema
providing a well defined structure, it is difficult to process an arbitrary
JSON-LD document as idiomatic JSON because there are many ways to express the
same data that are logically equivalent but structurally distinct.

Several schema languages exist for describing and validating JSON data, such as
JSON Schema and Apache Avro data serialization system, however none
understand linked data.  As a result, to fully take advantage of JSON-LD to
build the next generation of linked data applications, one must maintain
separate JSON schema, JSON-LD context, RDF schema, and human documentation,
despite significant overlap of content and obvious need for these documents to
stay synchronized.

Schema Salad is designed to address this gap.  It provides a schema language
and processing rules for describing structured JSON content permitting URI
resolution and strict document validation.  The schema language supports linked
data through annotations that describe the linked data interpretation of the
content, enables generation of JSON-LD context and RDF schema, and production
of RDF triples by applying the JSON-LD context.  The schema language also
provides for robust support of inline documentation.

.. _JSON-LD: http://json-ld.org
.. _Avro: http://avro.apache.org
.. _metaschema: https://github.com/common-workflow-language/schema_salad/blob/main/schema_salad/metaschema/metaschema.yml
.. _specification: http://www.commonwl.org/v1.0/SchemaSalad.html
.. _Language: https://github.com/common-workflow-language/common-workflow-language/blob/main/v1.0/CommandLineTool.yml
.. _RDF: https://www.w3.org/RDF/
