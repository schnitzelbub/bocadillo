from typing import Awaitable, Callable, List

from . import hooks
from .errors import HTTPError
from .request import Request
from .response import Response


class ValidationError(HTTPError):
    """Raised when validating a JSON object has failed."""

    def __init__(self, errors: List[str]):
        super().__init__(400, detail={"errors": errors})


class UnknownValidationBackend(ValueError):
    """Raised when not using a supported JSON validation backend."""


Validator = Callable[[Request, Response, dict], Awaitable[None]]


class Validators:
    """Validator backend factories."""

    @staticmethod
    def jsonschema(schema: dict) -> Validator:
        """Factory for `jsonschema` validators.

        # Parameters
        schema (dict): a schema compliant with jsonschema-draft7.

        # Returns
        validator (callable)

        # Raises
        jsonschema.SchemaError:
            If the provided `schema` is invalid.
        """
        try:
            from jsonschema.validators import Draft7Validator
            from jsonschema import SchemaError
        except ImportError as e:
            raise ImportError(
                "jsonschema must be installed to use the "
                "'jsonschema' validation backend"
            ) from e

        try:
            Draft7Validator.check_schema(schema)
        except SchemaError:
            raise

        async def validate(req, res, params):
            json = await req.json()
            errors = list(Draft7Validator(schema).iter_errors(json))
            if errors:
                raise ValidationError(errors=[e.message for e in errors])

        return validate


def validate(schema: dict, backend: str):
    try:
        validator_factory = getattr(Validators, backend)
    except AttributeError:
        raise UnknownValidationBackend(backend)
    else:
        validator = validator_factory(schema)
        return hooks.before(validator)
