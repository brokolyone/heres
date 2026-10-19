import pytest

from tests.telegram_rules import TelegramRuleError, check_html


@pytest.mark.parametrize("bad", ["<b>x", "a < b", "Tom & Jerry", "<div>x</div>", "<b><i>x</b></i>", "x</b>"])
def test_validator_rejects_what_telegram_rejects(bad):
    with pytest.raises(TelegramRuleError):
        check_html(bad)


@pytest.mark.parametrize("good", ["<b>x</b>", "a &lt; b &amp; c", "<code>1</code>\n<i>2</i>", "₭ ▰▱ ⟦ ⟧", "&#123;"])
def test_validator_accepts_valid(good):
    check_html(good)
