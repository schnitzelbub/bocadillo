# ValidationError
```python
ValidationError(self, errors: Union[str, List[str]])
```
Raised when validating a JSON object has failed.

This is a subclass of [HTTPError] that uses a `400 Bad Request` status.

[HTTPError]: ./errors.md#httperror

__Parameters__

- __errors (str or list of str)__:
    A list of error messages used as the error `detail`. If a single
    string is given, it is converted to a list or one error message.

# SchemaError
```python
SchemaError(self, /, *args, **kwargs)
```
Raised when validating the schema itself fails.
# ValidationBackend
```python
ValidationBackend(self)
```
Base class for validation backends.

A validation backend is essentially a callable that takes a `schema` as
input and returns a [before hook].

This base class also includes a lazy dependency loading mechanism.
You may change this behavior by overriding `.load()`.

::: warning
Validation backends should be stateless to be reusable for various
schemas.
:::

::: tip
Subclasses of this base class are registered and made available
through [get_backends()](#get-backends).
:::

[before hook]: ../guides/http/hooks.md

__Attributes__

- `name (str)`: the name of the validation backend.
- `dependency (str)`:
    The name of a module which the backend depends on.
- `module (any or None)`:
    The lazy-loaded dependency module.
    Non-`None` once `.load()` has been called.

## load
```python
ValidationBackend.load(self)
```
Load the `dependency`, if set.

__Raises__

- `ImportError`:
    If the module named after `dependency` could not be imported and
    is most likely not installed.

## compile
```python
ValidationBackend.compile(self, schema: Dict) -> Any
```
Compile and return a schema validator.

This is decoupled from `.validate()` to prevent compiling the
validator for each request. This induces performance benefits if
this operation is expensive.

The type of the returned value is not specified and may depend
on the underlying dependency.

Must be implemented by subclasses.

__Parameters__

- __schema (dict)__: a validation schema.

__Raises__

- `SchemaError`:
    If the provided `schema` is invalid.

## validate
```python
ValidationBackend.validate(self, compiled: Any, json: Union[list, dict])
```
Validate inbound JSON data.

Must be implemented by subclasses.

__Parameters__

- __compiled (any)__: the return value of `.compile()`.
- __json (list or dict)__: JSON data.

__Raises__

- `ValidationError`: if `json` has failed validation.

# FastJSONSchemaBackend
```python
FastJSONSchemaBackend(self)
```
Validation backend backed by [fastjsonschema].

[fastjsonschema]: https://github.com/horejsek/python-fastjsonschema

# JSONSchemaBackend
```python
JSONSchemaBackend(self)
```
Validation backend backed by [jsonschema].

[jsonschema]: https://github.com/Julian/jsonschema

# get_backends
```python
get_backends() -> Dict[str, bocadillo.validation.ValidationBackend]
```
Return a dictionary containing the registered validation backends.

__Returns__

`backends (dict)`: a mapping of backend names to backend instances.

