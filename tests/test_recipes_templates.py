from bocadillo import API, Recipe
from tests.conftest import TemplateWrapper


def test_use_template_string():
    numbers = Recipe("numbers")
    html = numbers.template_string("<h1>{{ title }}</h1>", title="Numbers")
    assert html == "<h1>Numbers</h1>"


def test_if_templates_dir_is_that_of_api_by_default(api: API):
    numbers = Recipe("numbers")
    api.recipe(numbers)
    assert numbers.templates_dir == api.templates_dir


def test_if_templates_dir_given_then_it_is_used(api: API):
    other_dir = "my_recipe/templates"
    numbers = Recipe("numbers", templates_dir=other_dir)
    api.recipe(numbers)
    assert numbers.templates_dir == other_dir != api.templates_dir


def test_render_template_in_recipe_route(
    template_file: TemplateWrapper, api: API
):
    numbers = Recipe("numbers")

    @numbers.route("/")
    async def get_numbers(req, res):
        res.html = await numbers.template(
            template_file.name, **template_file.context
        )

    api.recipe(numbers)

    response = api.client.get("/numbers/")
    assert response.status_code == 200
    assert response.text == template_file.rendered


def test_render_sync_template_in_recipe_route(
    template_file: TemplateWrapper, api: API
):
    numbers = Recipe("numbers")

    @numbers.route("/sync")
    def get_numbers_sync(req, res):
        res.html = numbers.template_sync(
            template_file.name, **template_file.context
        )

    api.recipe(numbers)

    response = api.client.get("/numbers/sync")
    assert response.status_code == 200
    assert response.text == template_file.rendered


def test_use_url_for(api: API):
    foo = Recipe("foo")

    @foo.route("/bar")
    async def bar(req, res):
        pass

    @foo.route("/fez")
    async def fez(req, res):
        res.html = foo.template_string(
            "<a href=\"{{ url_for('foo:bar') }}\">Fez to bar</a>"
        )

    @api.route("/baz")
    async def baz(req, res):
        res.html = api.template_string(
            "<a href=\"{{ url_for('foo:bar') }}\">Baz to bar</a>"
        )

    api.recipe(foo)

    response = api.client.get("/foo/fez")
    assert response.status_code == 200
    assert response.text == '<a href="/foo/bar">Fez to bar</a>'

    response = api.client.get("/baz")
    assert response.status_code == 200
    assert response.text == '<a href="/foo/bar">Baz to bar</a>'
