import pytest
from bocadillo import API, ValidationError, HTTPError
from bocadillo.error_handlers import error_to_media
from bocadillo.validation import UnknownValidationBackend
from jsonschema import SchemaError


@pytest.fixture
def schema():
    return {
        "title": "Product",
        "properties": {"price": {"type": "number"}},
        "required": ["price"],
    }


@pytest.fixture
def json_api(api: API):
    # NOTE: using JSON validation does not enforce that
    # HTTP errors are returned as media.
    api.add_error_handler(HTTPError, error_to_media)
    return api


def test_backend_defaults_to_api_default_backend(json_api: API):
    json_api.json_validation_backend = "foo"
    with pytest.raises(UnknownValidationBackend) as ctx:
        json_api.validate({})
    assert ctx.value.args[0] == "foo"


def test_backend_is_json_schema_by_default(json_api: API):
    assert json_api.json_validation_backend == "jsonschema"


def test_unknown_backend_raises_error(json_api: API):
    with pytest.raises(UnknownValidationBackend) as ctx:
        json_api.validate({}, backend="foobar")
    assert ctx.value.args[0] == "foobar"


def test_validate_from_json_schema(json_api: API, schema):
    @json_api.route("/")
    class Products:
        @json_api.validate(schema, backend="jsonschema")
        async def post(self, req, res):
            pass

    r = json_api.client.post("/", json={})
    assert r.status_code == 400
    json = r.json()
    errors = json["detail"]["errors"]
    assert len(errors) == 1
    assert all(s in errors[0] for s in ("price", "required"))


def test_jsonschema_schema_is_validated(json_api: API, schema):
    with pytest.raises(SchemaError):
        json_api.validate({"properties": "fjkh"}, backend="jsonschema")


def test_custom_validation_backend(json_api: API):
    # Decorator syntax!
    @json_api.json_validation_backend
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

    assert "required_fields" in json_api.json_validation_backends

    # The decorator should have registered the declared backend as a default.
    assert json_api.json_validation_backend == "required_fields"

    @json_api.route("/")
    class Index:
        @json_api.validate(["foo", "bar"])
        async def post(self, req, res):
            pass

    r = json_api.client.post("/", json={})
    assert r.status_code == 400
    errors = r.json()["detail"]["errors"]
    assert set(errors) == {
        "'foo' is a required field",
        "'bar' is a required field",
    }
