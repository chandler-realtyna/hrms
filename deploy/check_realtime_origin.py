"""Guest-only acceptance probe; run over SSH on the production host."""
import json
import urllib.error
import urllib.parse
import urllib.request


HOST = "hr.realtyna.com"
BASE = "http://127.0.0.1:8080/socket.io/?EIO=4&transport=polling"


def check(origin, host=HOST, fetch_site=None):
    headers = {"Host": host, "Cookie": "sid=Guest"}
    if origin is not None:
        headers["Origin"] = origin
    if fetch_site is not None:
        headers["Sec-Fetch-Site"] = fetch_site
    sid = None

    def request(url, data=None):
        req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "text/plain;charset=UTF-8"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode()

    try:
        sid = json.loads(request(BASE)[1:])["sid"]
        url = BASE + "&sid=" + urllib.parse.quote(sid)
        request(url, b"40/frontend,")
        packet = request(url)
        if packet.startswith("40/frontend,"):
            return {"connected": True}
        if packet.startswith("44/frontend,"):
            return {"connected": False, "error": json.loads(packet.split(",", 1)[1])["message"]}
        return {"connected": False, "error": "unexpected handshake packet"}
    except urllib.error.HTTPError as error:
        return {"connected": False, "status": error.code}
    finally:
        if sid:
            try:
                request(BASE + "&sid=" + urllib.parse.quote(sid), b"1")
            except (urllib.error.URLError, TimeoutError):
                pass


if __name__ == "__main__":
    result = {
        "allowed": check("https://hr.realtyna.com"),
        "same_origin_polling": check(None, fetch_site="same-origin"),
        "unrelated": check("https://unrelated.invalid"),
        "missing_origin": check(None),
        "insecure_origin": check("http://hr.realtyna.com"),
        "wrong_host": check("https://hr.realtyna.com", "unrelated.invalid"),
        "cross_site_without_origin": check(None, fetch_site="cross-site"),
    }
    print(json.dumps(result))
    assert result["allowed"]["connected"], "The production HTTPS origin must connect"
    assert result["same_origin_polling"]["connected"], "Same-origin browser polling must connect"
    for key in ("unrelated", "missing_origin", "insecure_origin", "wrong_host", "cross_site_without_origin"):
        assert result[key].get("status") == 403, f"The proxy must reject {key} before authentication"
