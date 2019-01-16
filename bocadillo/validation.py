from typing import Awaitable, Callable, List, Dict, Union, Optional

from . import hooks
from .errors import HTTPError
from .request import Request
from .response import Response


Validator = hooks.HookFunction
Schema = Dict
ValidationBackend = Callable[[Schema], Validator]


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


class UnknownValidationBackend(ValueError):
    """Raised when trying to use an unsupported JSON validation backend."""


def jsonschema(schema: Schema) -> Validator:
    """Validation backend backed by `jsonschema`.

    # Parameters
    schema (dict): a schema compliant with jsonschema-draft4.

    # Returns
    validator (callable): a hook function to be used in a before hook.

    # Raises
    ImportError:
        If `jsonschema` is not installed.
    jsonschema.SchemaError:
        If the provided `schema` is invalid.
    """
    try:
        from jsonschema.validators import validators
        from jsonschema import SchemaError
    except ImportError as e:
        raise ImportError(
            "jsonschema must be installed to use the "
            "'jsonschema' validation backend"
        ) from e

    # TODO: watch for more recent drafts when v3.0 comes out.
    validator = validators["draft4"]
    try:
        validator.check_schema(schema)
    except SchemaError:
        raise

    async def validate(req: Request, res: Response, params: dict):
        json = await req.json()
        errors = list(validator(schema).iter_errors(json))
        if errors:
            raise ValidationError(errors=[e.message for e in errors])

    return validate


class JSONValidationBackend:
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
