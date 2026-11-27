from app.market_data.book_validation import check_book, normalize_levels


def test_dict_levels_are_parsed_and_sorted():
    levels = normalize_levels([{"price": "0.40", "size": "5"}, {"price": "0.30", "size": "2"}], descending=True)
    assert levels == [(0.40, 5.0), (0.30, 2.0)]


def test_healthy_book_is_ok():
    book = {"bids": [{"price": "0.48", "size": "100"}], "asks": [{"price": "0.52", "size": "80"}]}
    check = check_book(book)
    assert check.ok is True
    assert check.best_bid == 0.48 and check.best_ask == 0.52
    assert round(check.spread, 4) == 0.04


def test_crossed_book_is_rejected():
    book = {"bids": [[0.50, 10]], "asks": [[0.48, 10]]}
    assert check_book(book).reason == "crossed_book"


def test_locked_book_is_rejected():
    book = {"bids": [[0.50, 10]], "asks": [[0.50, 10]]}
    assert check_book(book).reason == "crossed_book"


def test_empty_sides():
    assert check_book({"bids": [[0.4, 1]], "asks": []}).reason == "empty_asks"
    assert check_book({"bids": [], "asks": [[0.5, 1]]}).reason == "empty_bids"
    assert check_book({"bids": [], "asks": [[0.5, 1]]}, require_bids=False).ok is True


def test_prices_outside_zero_one_are_invalid():
    assert check_book({"bids": [[0.4, 1]], "asks": [[0.0, 5], [1.0, 5], [-0.2, 5]]}).reason == "invalid_prices"
    assert check_book({"bids": [[0.4, 1]], "asks": [[float("nan"), 5]]}).reason == "invalid_prices"


def test_zero_or_negative_size_is_dropped():
    assert normalize_levels([[0.5, 0], [0.5, -1], [0.6, 3]], descending=False) == [(0.6, 3.0)]


def test_stale_book_only_when_age_limit_given():
    book = {"bids": [[0.4, 1]], "asks": [[0.5, 1]], "timestamp": "1700000000000"}  # milliseconds
    assert check_book(book).ok is True
    assert check_book(book, max_age_seconds=60, now=1700000000 + 600).reason == "stale_book"
    assert check_book(book, max_age_seconds=60, now=1700000000 + 30).ok is True


def test_non_dict_book_is_invalid():
    assert check_book(None).reason == "invalid_book"
