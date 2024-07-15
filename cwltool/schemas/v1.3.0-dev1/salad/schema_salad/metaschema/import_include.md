## Import

During preprocessing traversal, an implementation must resolve `$import`
directives.  An `$import` directive is an object consisting of exactly one
field `$import` specifying resource by URI string.  It is an error if there
are additional fields in the `$import` object, such additional fields must
be ignored.

The URI string must be resolved to an absolute URI using the link
resolution rules described previously.  Implementations must support
loading from `file`, `http` and `https` resources.  The URI referenced by
`$import` must be loaded and recursively preprocessed as a Salad document.
The external imported document does not inherit the context of the
importing document, and the default base URI for processing the imported
document must be the URI used to retrieve the imported document.  If the
`$import` URI includes a document fragment, the fragment must be excluded
from the base URI used to preprocess the imported document.

Once loaded and processed, the `$import` node is replaced in the document
structure by the object or array yielded from the import operation.

URIs may reference document fragments which refer to specific an object in
the target document.  This indicates that the `$import` node must be
replaced by only the object with the appropriate fragment identifier.

It is a fatal error if an import directive refers to an external resource
or resource fragment which does not exist or is not accessible.

### Import example

import.json:
```
{
  "hello": "world"
}

```

parent.json:
```
{
  "form": {
    "bar": {
      "$import": "import.json"
      }
  }
}

```

This becomes:

```
{
  "form": {
    "bar": {
      "hello": "world"
    }
  }
}
```

## Include

During preprocessing traversal, an implementation must resolve `$include`
directives.  An `$include` directive is an object consisting of exactly one
field `$include` specifying a URI string.  It is an error if there are
additional fields in the `$include` object, such additional fields must be
ignored.

The URI string must be resolved to an absolute URI using the link
resolution rules described previously.  The URI referenced by `$include` must
be loaded as a text data.  Implementations must support loading from
`file`, `http` and `https` resources.  Implementations may transcode the
character encoding of the text data to match that of the parent document,
but must not interpret or parse the text document in any other way.

Once loaded, the `$include` node is replaced in the document structure by a
string containing the text data loaded from the resource.

It is a fatal error if an import directive refers to an external resource
which does not exist or is not accessible.

### Include example

parent.json:
```
{
  "form": {
    "bar": {
      "$include": "include.txt"
      }
  }
}

```

include.txt:
```
hello world

```

This becomes:

```
{
  "form": {
    "bar": "hello world"
  }
}
```
