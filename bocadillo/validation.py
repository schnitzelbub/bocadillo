from importlib import import_module
from typing import Dict, List, Optional, Union, Any

from . import hooks
from .errors import HTTPError
from .request import Request

Validator = hooks.HookFunction
Schema = Dict


class ValidationError(HTTPError):
    """Raised when validating a JSON object has failed.

    This is a subclass of [HTTPError] that uses a `400 Bad Request` status.

    [HTTPError]: ./errors.md#httperror

    # Parameters
    errors (str or list of str):
        A list of error messages used as the error `detail`. If a single
        string is given, it is converted to a list or one error message.
    """

    def __init__(self, errors: Union[str, List[str]]):
        if isinstance(errors, str):
            errors = [errors]
        super().__init__(400, detail={"errors": errors})


class SchemaError(ValueError):
    """Raised when validating the schema itself fails."""


class UnknownValidationBackend(ValueError):
    """Raised when trying to use an unsupported JSON validation backend."""


class _Meta(type):

    classes = []

    def __new__(mcs, name, bases, namespace):
        root = namespace.pop("root", False)
        cls = super().__new__(mcs, name, bases, namespace)
        if cls.dependency is not None and cls.name is None:
            cls.name = cls.dependency
        if not root:
            mcs.classes.append(cls)
        return cls


class ValidationBackend(metaclass=_Meta):
    """Base class for validation backends.

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
    
    # Attributes
    name (str): the name of the validation backend.
    dependency (str):
        The name of a module which the backend depends on.
    module (any or None):
        The lazy-loaded dependency module.
        Non-`None` once `.load()` has been called.
    """

    root = True
    name: str = None
    dependency: str = None

    def __init__(self):
        self.module: Any = None

    def load(self):
        """Load the `dependency`, if set.

        # Raises
        ImportError:
            If the module named after `dependency` could not be imported and
            is most likely not installed.
        """
        if self.dependency is None or self.module is not None:
            return
        try:
            self.module = import_module(self.dependency)
        except ImportError as exc:
            raise ImportError(
                f"{self.dependency} must be installed to use the "
                f"'{self.name}' validation backend."
            ) from exc

    def compile(self, schema: Schema) -> Any:
        """Compile and return a schema validator.

        This is decoupled from `.validate()` to prevent compiling the
        validator for each request. This induces performance benefits if
        this operation is expensive.

        The type of the returned value is not specified and may depend
        on the underlying dependency.

        Must be implemented by subclasses.
    
        # Parameters
        schema (dict): a validation schema.

        # Raises
        SchemaError:
            If the provided `schema` is invalid.
        """
        raise NotImplementedError

    def validate(self, compiled: Any, json: Union[list, dict]):
        """Validate inbound JSON data.

        Must be implemented by subclasses.

        # Parameters
        compiled (any): the return value of `.compile()`.
        json (list or dict): JSON data.

        # Raises
        ValidationError: if `json` has failed validation.
        """
        raise NotImplementedError

    def __call__(self, schema: Schema) -> Validator:
        """Build and return a validation hook.

        # Parameters
        schema (dict): a schema compliant with jsonschema-draft4.

        # Returns
        validator (callable): a hook function to be used in a before hook.

        # Raises
        ImportError:
            If the dependency as specified by `module_name` is not installed.
        SchemaError:
            If the provided `schema` is invalid.
        """
        self.load()
        compiled = self.compile(schema)

        async def validate(req: Request, _, __):
            json = await req.json()
            await self.validate(compiled, json)

        return validate


class FastJSONSchemaBackend(ValidationBackend):
    """Validation backend backed by [fastjsonschema].
    
    [fastjsonschema]: https://github.com/horejsek/python-fastjsonschema
    """

    dependency = "fastjsonschema"

    def compile(self, schema: Schema):
        try:
            return self.module.compile(schema)
        except Exception as exc:
            # fastjsonschema provides a `JsonSchemaDefinitionException`, but
            # `.compile()` may throw other kinds of exceptions.
            raise SchemaError(schema) from exc

    def validate(self, compiled, json: Union[list, dict]):
        try:
            compiled(json)
        except self.module.JsonSchemaException as exc:
            raise ValidationError(exc.message) from exc


class JSONSchemaBackend(ValidationBackend):
    """Validation backend backed by [jsonschema].

    [jsonschema]: https://github.com/Julian/jsonschema
    """

    dependency = "jsonschema"
    version = "draft4"

    def compile(self, schema: Schema):
        from jsonschema.validators import validators

        validator = validators[self.version]

        try:
            validator.check_schema(schema)
        except self.module.SchemaError as exc:
            raise SchemaError(schema) from exc

        return validator(schema)

    def validate(self, compiled, json: Union[dict, list]):
        errors = list(compiled.iter_errors(json))
        if errors:
            raise ValidationError(errors=[e.message for e in errors])


def get_backends() -> Dict[str, ValidationBackend]:
    """Return a dictionary containing the registered validation backends.

    # Returns
    backends (dict): a mapping of backend names to backend instances.
    """
    return {cls.name: cls() for cls in _Meta.classes}


class BackendAttr:
    # Descriptor for a hybrid validation backend attribute.

    def __init__(self, store: str):
        self.backend_name: Optional[str] = None
        self.store = store

    def __get__(self, obj, obj_type):
        # Return an object that behaves like a string (for reading the value)
        # or a function (for decorating backend functions).
        # Yes, this is outrageously hacky. Yet elegant, I think.
        this = self

        class Decorator(str):
            def __call__(self, backend):
                nonlocal this
                getattr(obj, this.store)[backend.__name__] = backend
                this.backend_name = backend.__name__
                return backend

        return Decorator(self.backend_name)

    def __set__(self, obj, value: str):
        self.backend_name = value
