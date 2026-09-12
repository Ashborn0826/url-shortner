from app.shortcode import BASE62_ALPHABET, DEFAULT_LENGTH, generate_code


def test_default_length_is_seven():
    assert len(generate_code()) == DEFAULT_LENGTH == 7


def test_uses_only_base62_alphabet():
    code = generate_code()
    assert all(c in BASE62_ALPHABET for c in code)


def test_custom_length():
    assert len(generate_code(length=12)) == 12


def test_uniqueness_over_10k_codes():
    """10k base62-7 codes have ~1.4e-8 collision probability per pair.
    Expect zero collisions over 10k draws."""
    codes = {generate_code() for _ in range(10_000)}
    assert len(codes) == 10_000


def test_uniqueness_under_load_50k():
    """50k draws into base62-7: still expect zero collisions (3.5T keyspace)."""
    codes = {generate_code() for _ in range(50_000)}
    assert len(codes) == 50_000