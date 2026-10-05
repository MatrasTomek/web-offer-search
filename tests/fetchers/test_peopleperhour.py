from fetchers import peopleperhour

_SAMPLE_CARD_HTML = """
<li class="list__item⤍List⤚2ytmm">
  <div class="item⤍ListItem⤚1iGUH item--container⤍ListItem⤚2wpiz">
    <div class="pph-row item__top_container⤍ListItem⤚3pRrO">
      <div class="item__container⤍ListItem⤚Fk4RX">
        <div class="pph-col-md-12 pph-col-xs-12">
          <div class="card__meta⤍ListItem⤚3wkEV">
            <div class="u-txt--right card__price⤍ListItem⤚3VxJ9">
              <span class="title-nano"><div><span>$8</span></div></span>
            </div>
          </div>
        </div>
        <div class="pph-col-md-12 pph-col-xs-12">
          <h6 class="item__title⤍ListItem⤚2FRMT">
            <a class="item__url⤍ListItem⤚20ULx"
               href="https://www.peopleperhour.com/freelance-jobs/business/administration-assistance/copy-paste-images-4524971">Copy &amp; Paste Images</a>
          </h6>
          <p class="item__desc⤍ListItem⤚3f4JV">Hello I have a simple project.</p>
        </div>
      </div>
      <div class="card__footer⤍ListItem⤚1KHhv">
        <div class="nano card__footer-left⤍ListItem⤚16Odv">
          <span>6 hours ago</span><span class="u-mgl--1">27 proposals</span>
        </div>
      </div>
    </div>
  </div>
</li>
"""


def test_parse_cards_extracts_fields_despite_hashed_css_module_classes():
    items = peopleperhour._parse_cards(_SAMPLE_CARD_HTML)

    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Copy & Paste Images"
    assert item["description"] == "Hello I have a simple project."
    assert item["budget"] == "$8"
    assert item["date"] == "6 hours ago"
    assert item["link"] == (
        "https://www.peopleperhour.com/freelance-jobs/business/"
        "administration-assistance/copy-paste-images-4524971"
    )


def test_parse_cards_returns_empty_list_for_page_with_no_cards():
    assert peopleperhour._parse_cards("<html><body>no jobs here</body></html>") == []
