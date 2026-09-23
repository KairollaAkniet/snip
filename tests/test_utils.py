from app.utils import generate_code, parse_user_agent, referrer_domain


def test_generate_code():
    code = generate_code(7)
    assert len(code) == 7 and code.isalnum()


def test_parse_user_agent():
    edge = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/128.0 Safari/537.36 Edg/128.0"
    android = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/128.0 Mobile Safari/537.36"
    assert parse_user_agent(edge) == ("Desktop", "Edge", "Windows")
    assert parse_user_agent(android) == ("Mobile", "Chrome", "Android")
    assert parse_user_agent("curl/8.4.0")[0] == "Bot"
    assert parse_user_agent("") == ("Desktop", "Other", "Other")


def test_referrer_domain():
    assert referrer_domain(None) == "Direct"
    assert referrer_domain("https://www.youtube.com/watch?v=1") == "youtube.com"
    assert referrer_domain("garbage") == "Direct"
