from bs4 import BeautifulSoup, Tag

from application.services.domain_parsers import domain_parser_registry
from application.services.domain_parsers.tjll import TJLLBlogParser


def test_tjll_parser_matches_blog_domain() -> None:
    parser = TJLLBlogParser()

    assert parser.can_handle("blog.tjll.net") is True
    assert parser.can_handle("www.blog.tjll.net") is False
    assert parser.can_handle("tjll.net") is False
    assert parser.can_handle("example.com") is False


def test_tjll_parser_extracts_article_body_and_removes_page_chrome() -> None:
    parser = TJLLBlogParser()
    html = """
    <html>
      <body>
        <header class="container">Site navigation</header>
        <main class="container post">
          <hgroup>
            <h3><a class="nav" href="/prev/">&laquo;</a> Repeated title</h3>
            <div class="sub">
              <ul id="post-details"><li>5 May, 2026</li></ul>
            </div>
          </hgroup>
          <section id="content">
            <div class="figure">
              <p>
                <img
                  src="https://blog.tjll.net/assets/images/cave.png"
                  alt="cave.png"
                  class="mainline"
                />
              </p>
              <p><span class="figure-number">Figure 1: </span>Useful caption</p>
            </div>
            <p>
              This is the first real paragraph of a Tyblog article with enough
              useful prose to pass validation and represent the readable story.
            </p>
            <div id="outline-container-real-heading" class="outline-4">
              <h4 id="real-heading">Real article heading</h4>
              <div class="outline-text-4">
                <p>
                  This paragraph belongs under a real article heading and should
                  remain part of the extracted article content.
                </p>
                <div id="outline-container-nested-heading" class="outline-5">
                  <h5 id="nested-heading">Nested article heading</h5>
                  <div class="outline-text-5">
                    <p>
                      This paragraph belongs under a nested article heading and
                      should keep its section hierarchy.
                    </p>
                  </div>
                </div>
              </div>
            </div>
            <span class="org-src-tab"><span>Systemd</span></span>
            <div class="org-src-legend">
              <ul><li>Font used to highlight strings.</li></ul>
            </div>
            <div class="org-src-container">
              <pre class="src src-systemd"><code><code><span class="org-type">[Unit]</span></code>
<code><span class="org-keyword">Description</span>=example service</code></code></pre>
            </div>
            <span class="org-src-tab"><span>shell</span></span>
            <div class="org-src-container">
              <pre class="src src-shell"><code><code>systemctl list-timers</code></code></pre>
            </div>
            <p>
              A second meaningful paragraph remains in the extracted content so
              the parser keeps enough context for the reader page and EPUB export.
            </p>
            <div id="footnotes">
              <h2 class="footnotes">Footnotes:</h2>
              <div class="footdef">
                <sup><a id="fn.example" href="#fnr.example">1</a></sup>
                <div class="footpara"><p>Useful footnote text.</p></div>
              </div>
            </div>
            <hr/>
            <div id="page-nav" class="grid">
              <a href="/prev/">Previous post</a>
              <a href="/next/">Next post</a>
            </div>
            <hr/>
            <div id="discourse-comments">Comment placeholder</div>
            <script>DiscourseEmbed = {};</script>
          </section>
        </main>
        <footer class="container">Footer links</footer>
      </body>
    </html>
    """

    result = parser.extract(html, "https://blog.tjll.net/example-post/")

    assert result is not None
    result_soup = BeautifulSoup(result, "html.parser")
    systemd_block = result_soup.find("pre", attrs={"data-language": "systemd"})
    shell_block = result_soup.find("pre", attrs={"data-language": "shell"})
    real_heading = result_soup.find("h2", id="real-heading")
    nested_heading = result_soup.find("h3", id="nested-heading")

    assert isinstance(systemd_block, Tag)
    assert isinstance(shell_block, Tag)
    assert isinstance(real_heading, Tag)
    assert isinstance(nested_heading, Tag)
    assert systemd_block.get_text() == "[Unit]\nDescription=example service"
    assert shell_block.get_text() == "systemctl list-timers"
    assert "This is the first real paragraph" in result
    assert "Real article heading" in result
    assert "Nested article heading" in result
    assert "paragraph belongs under a real article heading" in result
    assert "paragraph belongs under a nested article heading" in result
    assert "A second meaningful paragraph" in result
    assert "Useful caption" in result
    assert "https://blog.tjll.net/assets/images/cave.png" in result
    assert "Description=example service" in result
    assert "systemctl list-timers" in result
    assert "Useful footnote text" in result
    assert "Site navigation" not in result
    assert "Repeated title" not in result
    assert "5 May, 2026" not in result
    assert "Systemd" not in result
    assert ">shell<" not in result
    assert "Font used to highlight strings" not in result
    assert "org-keyword" not in result
    assert "src-systemd" not in result
    assert "src-shell" not in result
    assert "Previous post" not in result
    assert "Next post" not in result
    assert "Comment placeholder" not in result
    assert "DiscourseEmbed" not in result
    assert "Footer links" not in result


def test_tjll_parser_cleans_rss_description_fragment() -> None:
    parser = TJLLBlogParser()
    html = """
    <p>
      On a Linux host with systemd operational, placing the following unit
      contents installs a service with enough prose to pass parser validation.
    </p>
    <span class="org-src-tab"><span>Systemd</span></span>
    <div class="org-src-legend">
      <ul>
        <li><span class="org-string">Font used to highlight strings.</span></li>
        <li><span class="org-keyword">Font used to highlight keywords.</span></li>
      </ul>
    </div>
    <div class="org-src-container">
      <pre class="src src-systemd"><code><code><span class="org-type">[Unit]</span></code>
<code><span class="org-keyword">Description</span>=1 in 10 chance</code>
<code></code>
<code><span class="org-type">[Service]</span></code>
<code><span class="org-keyword">ExecStart</span>=/usr/bin/env bash -c 'echo LIVE'</code></code></pre>
    </div>
    <div id="outline-container-bird-s-eye-countdown" class="outline-5">
      <h5 id="bird-s-eye-countdown">Bird's-Eye Countdown</h5>
      <div class="outline-text-5">
        <p>
          This section should be promoted to a reader heading instead of being
          displayed like ordinary paragraph text.
        </p>
      </div>
    </div>
    """

    result = parser.extract(html, "https://blog.tjll.net/example-post/")

    assert result is not None
    result_soup = BeautifulSoup(result, "html.parser")
    systemd_block = result_soup.find("pre", attrs={"data-language": "systemd"})
    heading = result_soup.find("h3", id="bird-s-eye-countdown")

    assert isinstance(systemd_block, Tag)
    assert isinstance(heading, Tag)
    assert systemd_block.get_text() == (
        "[Unit]\n"
        "Description=1 in 10 chance\n\n"
        "[Service]\n"
        "ExecStart=/usr/bin/env bash -c 'echo LIVE'"
    )
    assert "Bird's-Eye Countdown" in result
    assert "Systemd" not in result
    assert "Font used to highlight" not in result
    assert "org-keyword" not in result
    assert "src-systemd" not in result


def test_domain_registry_returns_tjll_parser() -> None:
    parser = domain_parser_registry.get_parser("blog.tjll.net")

    assert isinstance(parser, TJLLBlogParser)
