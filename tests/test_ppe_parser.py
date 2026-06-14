from application.services.domain_parsers import domain_parser_registry
from application.services.domain_parsers.ppe import PPEParser


def test_ppe_parser_matches_ppe_domains() -> None:
    parser = PPEParser()

    assert parser.can_handle("ppe.pl") is True
    assert parser.can_handle("www.ppe.pl") is True
    assert parser.can_handle("assets.ppe.pl") is True
    assert parser.can_handle("example.com") is False


def test_ppe_parser_extracts_news_body_and_preserves_lazy_media() -> None:
    parser = PPEParser()
    html = """
    <html>
      <body>
        <nav>Site navigation</nav>
        <article class="news-section">
          <div class="news-top-wrapper">
            <h1>Repeated article title</h1>
            <div class="news-image-bottom">Author metadata</div>
          </div>
          <div class="content news" data-controller="achievementsHandler">
            <p>
              This is the first real paragraph of a PPE news article with enough
              useful prose to pass validation and represent the readable story.
            </p>
            <div id="article-1"></div>
            <div class="onnetwork">
              <span>Dalsza część tekstu pod wideo</span>
              <div class="optad360-player"></div>
            </div>
            <figure>
              <picture>
                <source
                  srcset="data:image/png;base64,placeholder"
                  data-srcset="https://pliki.ppe.pl/example-webp-800w.webp 800w"
                  data-sizes="100vw"
                />
                <img
                  src="data:image/png;base64,placeholder"
                  data-src="https://pliki.ppe.pl/storage/example/example.jpg"
                  alt="Useful image"
                  data-controller="image"
                />
              </picture>
              <figcaption>Useful image caption</figcaption>
              <div class="resize-icon">
                <img
                  src="/build/client/images/icons/resize-icon.e1e9c338.svg"
                  class="resize-icon__icon"
                  alt="resize icon"
                />
              </div>
            </figure>
            <div class="content-array__media-expert">
              <span>Wybrane okazje dla Ciebie</span>
              <a>Kup teraz</a>
            </div>
            <p>
              A second meaningful paragraph remains in the extracted content so
              the parser keeps enough context for the reader page and EPUB export.
            </p>
            <p class="content__source">Źródło: example</p>
          </div>
        </article>
        <div id="comments-box">Comment thread</div>
      </body>
    </html>
    """

    result = parser.extract(html, "https://www.ppe.pl/news/123/story.html")

    assert result is not None
    assert "This is the first real paragraph" in result
    assert "A second meaningful paragraph" in result
    assert "Useful image caption" in result
    assert "https://pliki.ppe.pl/storage/example/example.jpg" in result
    assert "example-webp-800w.webp 800w" in result
    assert "Site navigation" not in result
    assert "Repeated article title" not in result
    assert "Dalsza część tekstu pod wideo" not in result
    assert "Wybrane okazje dla Ciebie" not in result
    assert "Źródło:" not in result
    assert "Comment thread" not in result
    assert "resize-icon" not in result
    assert "resize icon" not in result
    assert "data-controller" not in result


def test_ppe_parser_uses_full_guide_content() -> None:
    parser = PPEParser()
    html = """
    <html>
      <body>
        <div class="table-of-contents">
          <a href="/poradniki/123/other.html">Large guide navigation</a>
        </div>
        <main>
          <div class="content guide">
            <p>
              Short intro paragraph that should not be preferred over the full
              guide content when the dedicated guide container is present.
            </p>
          </div>
          <div class="guide-content text-content">
            <h2>Mission walkthrough</h2>
            <p>
              This full PPE guide section contains the first real walkthrough
              paragraph with enough useful prose to pass parser validation.
            </p>
            <ul>
              <li>Find the objective marker and inspect the surrounding area.</li>
              <li>Return to the quest giver after finishing the mission.</li>
            </ul>
            <p>
              Another full guide paragraph remains available for long-form
              reading, instead of only returning the short introduction block.
            </p>
          </div>
        </main>
      </body>
    </html>
    """

    result = parser.extract(
        html,
        "https://www.ppe.pl/poradniki/123/example-guide.html",
    )

    assert result is not None
    assert "Mission walkthrough" in result
    assert "Find the objective marker" in result
    assert "Another full guide paragraph" in result
    assert "Short intro paragraph" not in result
    assert "Large guide navigation" not in result


def test_ppe_parser_extracts_journalism_and_removes_media_expert_ads() -> None:
    parser = PPEParser()
    html = """
    <html>
      <body>
        <div class="review-img">
          <h1>Repeated journalism title</h1>
        </div>
        <div class="review-content">
          <div class="single-gallery">Gallery overlay</div>
          <div class="content journalism" data-controller="achievementsHandler">
            <p>
              This PPE journalism article starts with a meaningful paragraph about
              games and culture, long enough to validate as readable article body.
            </p>
            <div class="onnetwork">
              <span>Dalsza część tekstu pod wideo</span>
            </div>
            <h2>Serce z Kamienia</h2>
            <div class="content-array__media-expert">
              <div class="content-array__media-expert-header">
                <span>Wybrane okazje dla Ciebie</span>
                <span>Reklama</span>
              </div>
              <a
                class="media-expert-card"
                href="https://ad.doubleclick.net/ddm/trackclk/example"
              >
                <span>Konsola SONY PlayStation 5 Slim E-chassis</span>
                <span>Kup teraz</span>
                <img
                  src="https://www.mediaexpert.pl/media/cache/product.jpg"
                  alt="Sponsored product"
                />
              </a>
            </div>
            <p>
              The paragraph after the sponsored Media Expert widget must remain,
              proving that only the advertisement block is removed from content.
            </p>
          </div>
        </div>
      </body>
    </html>
    """

    result = parser.extract(
        html,
        "https://www.ppe.pl/publicystyka/413175/example.html",
    )

    assert result is not None
    assert "This PPE journalism article starts" in result
    assert "Serce z Kamienia" in result
    assert "paragraph after the sponsored" in result
    assert "Repeated journalism title" not in result
    assert "Gallery overlay" not in result
    assert "Dalsza część tekstu pod wideo" not in result
    assert "Wybrane okazje dla Ciebie" not in result
    assert "Media Expert" not in result
    assert "PlayStation 5" not in result
    assert "doubleclick.net" not in result
    assert "mediaexpert.pl" not in result


def test_domain_registry_returns_ppe_parser() -> None:
    parser = domain_parser_registry.get_parser("www.ppe.pl")

    assert isinstance(parser, PPEParser)
