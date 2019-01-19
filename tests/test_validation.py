import pytest

from bocadillo import API, ValidationError
from bocadillo.validation import UnknownValidationBackend


def test_default_backend(jsonapi: API):
    assert jsonapi.json_validation_backend == "jsonschema"


def test_unknown_backend_raises_error(jsonapi: API):
    with pytest.raises(UnknownValidationBackend) as ctx:
        jsonapi.validate({}, backend="foobar")
    assert ctx.value.args[0] == "foobar"


def test_backend_defaults_to_api_default_backend(jsonapi: API):
    jsonapi.json_validation_backend = "foo"
    with pytest.raises(UnknownValidationBackend) as ctx:
        jsonapi.validate({})
    assert ctx.value.args[0] == "foo"


def test_custom_validation_backend(jsonapi: API):
    # Decorator syntax!
    @jsonapi.json_validation_backend
    def required_fields(schema: list):
        async def validate(req, res, params):
            json = await req.json()
            errors = []
            for field in schema:
                if field not in json:
                    errors.append(f"'{field}' is a required field")
            if errors:
                raise ValidationError(errors)

        return validate

    assert "required_fields" in jsonapi.json_validation_backends

    # The decorator should have registered the declared backend as a default.
    assert jsonapi.json_validation_backend == "required_fields"

    @jsonapi.route("/")
    class Index:
        @jsonapi.validate(["foo", "bar"])
        async def post(self, req, res):
            pass

    r = jsonapi.client.post("/", json={})
    assert r.status_code == 400
    errors = r.json()["detail"]["errors"]
    assert set(errors) == {
        "'foo' is a required field",
        "'bar' is a required field",
    }
