import pytest

from bocadillo import API
from bocadillo.validation import SchemaError

BACKENDS = ("jsonschema", "fastjsonschema")


@pytest.mark.parametrize("backend", BACKENDS)
def test_validate_using_jsonschema(jsonapi: API, backend):
    schema = {
        "title": "Product",
        "properties": {"price": {"type": "number"}},
        "required": ["price"],
    }

    @jsonapi.route("/")
    class Products:
        @jsonapi.validate(schema, backend=backend)
        async def post(self, req, res):
            pass

    r = jsonapi.client.post("/", json={})
    assert r.status_code == 400
    json = r.json()
    errors = json["detail"]["errors"]
    assert len(errors) == 1
    assert "price" in errors[0]


@pytest.mark.parametrize("backend", BACKENDS)
def test_jsonschema_schema_is_validated(jsonapi: API, backend):
    with pytest.raises(SchemaError):
        jsonapi.validate({"properties": "fjkh"}, backend=backend)
