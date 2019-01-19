from importlib import import_module
from typing import Dict, List, Optional, Union, Any

from . import hooks
from .errors import HTTPError
from .request import Request
from .response import Response

Validator = hooks.HookFunction
Schema = Dict


class ValidationError(HTTPError):
    """Raised when validating a JSON object has failed.

    This is a subclass of `HTTPError` that uses a `400 Bad Request` status.

    # Parameters
    error (str):
        An error message. If given, it is appended to any
    errors (list of str):
        A list of error messages used as the error `detail`.
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
        if not root:
            mcs.classes.append(cls)
        return cls


class ValidationBackend(metaclass=_Meta):
    """Base validation backend."""

    root = True
    name: str
    module_name: str

    def __init__(self):
        self.module = None
        self.validator: Any = None

    def load(self):
        try:
            self.module = import_module(self.module_name)
        except ImportError as exc:
            raise ImportError(
                f"{self.module_name} must be installed to use the "
                f"'{self.name}' validation backend."
            ) from exc

    def get_validator(self, schema: Schema) -> Any:
        raise NotImplementedError

    def validate(self, json: Union[list, dict]):
        raise NotImplementedError

    def __call__(self, schema: Schema) -> Validator:
        """Build and return a validation hook.

        # Parameters
        schema (dict): a schema compliant with jsonschema-draft4.

        # Returns
        validator (callable): a hook function to be used in a before hook.

        # Raises
        ImportError:
            If `jsonschema` is not installed.
        SchemaError:
            If the provided `schema` is invalid.
        """
        self.load()
        self.validator = self.get_validator(schema)

        async def validate(req: Request, res: Response, params: dict):
            json = await req.json()
            await self.validate(json)

        return validate


class FastJSONSchemaBackend(ValidationBackend):
    """Validation backend backed by `fastjsonschema`."""

    name = module_name = "fastjsonschema"

    def get_validator(self, schema):
        try:
            return self.module.compile(schema)
        except self.module.JsonSchemaDefinitionException as exc:
            raise SchemaError(schema) from exc
        except Exception as exc:
            raise SchemaError(schema) from exc

    def validate(self, json: Union[list, dict]):
        try:
            self.validator(json)
        except self.module.JsonSchemaException as exc:
            raise ValidationError(exc.message) from exc


class JSONSchemaBackend(ValidationBackend):
    """Validation backend backed by `jsonschema`."""

    name = module_name = "jsonschema"

    def get_validator(self, schema: Schema) -> Validator:
        from jsonschema.validators import validators

        draft4 = validators["draft4"]

        try:
            draft4.check_schema(schema)
        except self.module.SchemaError as exc:
            raise SchemaError(schema) from exc

        return draft4(schema)

    def validate(self, json: Union[dict, list]):
        errors = list(self.validator.iter_errors(json))
        if errors:
            raise ValidationError(errors=[e.message for e in errors])


def get_backends() -> Dict[str, ValidationBackend]:
    return {cls.name: cls() for cls in _Meta.classes}


class JSONValidationBackendAttr:
    # Descriptor for the API's `json_validation_backend` attribute.

    def __init__(self):
        self.backend_name: Optional[str] = None

    def __get__(self, obj, obj_type):
        # Return an object that behaves like a string (for reading the value)
        # or a function (for decorating backend functions).
        # Yes, this is outrageously hacky. Yet elegant, I think.
        this = self

        class Decorator(str):
            def __call__(self, value):
                nonlocal this
                obj.json_validation_backends[value.__name__] = value
                this.backend_name = value.__name__
                return value

        return Decorator(self.backend_name)

    def __set__(self, obj, value: str):
        self.backend_name = value
