from scrapper.enrichment.extractor import extract_emails, extract_socials


def test_extracts_basic_email():
    html = "<p>Reach us at hello@acme.com today.</p>"
    found = extract_emails(html)
    assert len(found) == 1
    assert found[0].value == "hello@acme.com"
    assert found[0].is_role_based is True


def test_drops_placeholder_emails():
    html = "<p>name@example.com noreply@foo.com bob@yourdomain.com</p>"
    found = extract_emails(html)
    assert all(c.value not in {"name@example.com", "bob@yourdomain.com"} for c in found)
    assert all(not c.value.startswith("noreply") for c in found)


def test_role_based_detection():
    html = "info@store.io and john.doe@store.io"
    by_local = {c.value: c.is_role_based for c in extract_emails(html)}
    assert by_local["info@store.io"] is True
    assert by_local["john.doe@store.io"] is False


def test_extracts_socials():
    html = """
      <a href="https://www.linkedin.com/company/acme">LinkedIn</a>
      <a href="https://instagram.com/acme">Instagram</a>
      <a href="https://x.com/acme">Twitter</a>
      <a href="https://facebook.com/sharer.php?u=foo">Share</a>
    """
    found = extract_socials(html)
    kinds = {c.kind for c in found}
    assert "linkedin" in kinds
    assert "instagram" in kinds
    assert "twitter" in kinds
    # The /sharer.php URL has 'share' in the path and should be filtered out
    assert not any("sharer" in c.value for c in found)
