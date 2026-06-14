from application.services.domain_parsers import domain_parser_registry
from application.services.domain_parsers.substack import SubstackParser


def test_substack_parser_matches_substack_domains() -> None:
    parser = SubstackParser()

    assert parser.can_handle("substack.com") is True
    assert parser.can_handle("example.substack.com") is True
    assert parser.can_handle("deep.example.substack.com") is True
    assert parser.can_handle("example.com") is False


def test_substack_parser_extracts_body_and_removes_platform_chrome() -> None:
    parser = SubstackParser()
    html = """
    <html>
      <body>
        <header>Site navigation</header>
        <article class="post">
          <div class="post-header">
            <h1>Repeated article title</h1>
            <div class="post-meta">Author metadata</div>
          </div>
          <div class="body markup">
            <p>
              This is the first real paragraph of a Substack article with enough
              useful prose to pass validation and represent the readable story.
            </p>
            <figure>
              <img src="https://example.substack.com/image.png" />
              <figcaption>Useful image caption</figcaption>
            </figure>
            <pre><code>print("hello")</code></pre>
            <div class="subscription-widget-wrap">
              Thanks for reading Example! Subscribe to receive new posts.
            </div>
            <p>This post is public so feel free to share it.</p>
            <div class="comments">Comment thread</div>
            <p>
              A second meaningful paragraph remains in the extracted content so
              the parser keeps enough context for the reader page and EPUB export.
            </p>
          </div>
        </article>
        <footer>Footer links</footer>
      </body>
    </html>
    """

    result = parser.extract(html, "https://example.substack.com/p/story")

    assert result is not None
    assert "This is the first real paragraph" in result
    assert "A second meaningful paragraph" in result
    assert "Useful image caption" in result
    assert "<img" in result
    assert "<code>" in result
    assert "Site navigation" not in result
    assert "Repeated article title" not in result
    assert "Subscribe to receive new posts" not in result
    assert "This post is public" not in result
    assert "Comment thread" not in result
    assert "Footer links" not in result


def test_domain_registry_returns_substack_parser() -> None:
    parser = domain_parser_registry.get_parser("example.substack.com")

    assert isinstance(parser, SubstackParser)
