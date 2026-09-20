from nettodeals.ai_editor import api_error_message

class Reply:
    status_code = 403
    text = "error code: 1010 SECRET"
    def json(self):
        raise ValueError("SECRET")

def test_cloudflare_and_no_secret():
    result = api_error_message(Reply())
    assert "Cloudflare 1010" in result
    assert "SECRET" not in result

def test_permission_codes():
    for code, label in [("model_permission_blocked_org", "Organisationsebene"), ("model_permission_blocked_project", "Projektebene")]:
        reply = Reply()
        reply.json = lambda: {"error": {"code": code, "message": "SECRET"}}
        result = api_error_message(reply)
        assert label in result and "SECRET" not in result

def test_unknown_and_malformed():
    for data in [None, [], {"error": "SECRET"}, {"error": {"code": "SECRET", "message": "SECRET"}}]:
        reply = Reply()
        reply.text = "SECRET"
        reply.json = lambda: data
        result = api_error_message(reply)
        assert "nicht eindeutig" in result and "SECRET" not in result

def test_limits():
    for status, label in [(413, "TPM"), (429, "Kontingent"), (401, "Schlüssel")]:
        reply = Reply()
        reply.status_code = status
        assert label in api_error_message(reply)
