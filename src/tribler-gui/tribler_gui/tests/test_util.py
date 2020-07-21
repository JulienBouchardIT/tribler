from urllib.parse import unquote_plus

from tribler_gui.utilities import compose_magnetlink, quote_plus_unicode, unicode_quoter


def test_quoter_char():
    """
    Test if an ASCII character is quoted correctly
    """
    char = u'A'

    encoded = unicode_quoter(char)

    assert char == unquote_plus(encoded)


def test_quoter_unichar():
    """
    Test if a unicode character is quoted correctly
    """
    char = u'\u9b54'

    encoded = unicode_quoter(char)

    assert char == unquote_plus(encoded)


def test_quoter_reserved():
    """
    Test if a URI reserved character is quoted correctly
    """
    char = u'+'

    encoded = unicode_quoter(char)

    assert char != encoded
    assert char == unquote_plus(encoded)


def test_quote_plus_unicode_char():
    """
    Test if a ASCII characters are quoted correctly
    """
    s = u'Ab09'

    encoded = quote_plus_unicode(s)

    assert s == unquote_plus(encoded)


def test_quote_plus_unicode_unichar():
    """
    Test if unicode characters are quoted correctly
    """
    s = u'\u9b54\u11b3\uaf92\u1111'

    encoded = quote_plus_unicode(s)

    assert s == unquote_plus(encoded)


def test_quote_plus_unicode_reserved():
    """
    Test if a URI reserved characters are quoted correctly
    """
    s = u'+ &'

    encoded = quote_plus_unicode(s)

    assert s != encoded
    assert s == unquote_plus(encoded)


def test_quote_plus_unicode_compound():
    """
    Test if a jumble of unicode, reserved and normal chars are quoted correctly
    """
    s = u'\u9b54\u11b3+ A5&\uaf92\u1111'

    encoded = quote_plus_unicode(s)

    assert s != encoded
    assert s == unquote_plus(encoded)


def test_compose_magnetlink():
    infohash = "DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    name = "Some torrent name"
    trackers = ['http://tracker1.example.com:8080/announce', 'http://tracker1.example.com:8080/announce']

    expected_link0 = ""
    expected_link1 = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
    expected_link2 = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A&dn=Some+torrent+name"
    expected_link3 = (
        "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A&dn=Some+torrent+name"
        "&tr=http://tracker1.example.com:8080/announce&tr=http://tracker1.example.com:8080/announce"
    )

    composed_link0 = compose_magnetlink(None)
    composed_link1 = compose_magnetlink(infohash)
    composed_link2 = compose_magnetlink(infohash, name=name)
    composed_link3 = compose_magnetlink(infohash, name=name, trackers=trackers)

    assert composed_link0 == expected_link0
    assert composed_link1 == expected_link1
    assert composed_link2 == expected_link2
    assert composed_link3 == expected_link3
