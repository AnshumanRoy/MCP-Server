from mcp_server.safety import mask_row, mask_value


def test_mask_denied_column():
    import mcp_server.config as cfg

    orig = cfg.settings.denied_columns
    cfg.settings.denied_columns = ["email"]
    try:
        assert mask_value("email", "a@example.com") == "a***"
        assert mask_value("name", "Artist One") == "Artist One"
        assert mask_value("email", None) is None
        row = mask_row(["name", "email"], {"name": "A", "email": "a@example.com"})
        assert row == {"name": "A", "email": "a***"}
    finally:
        cfg.settings.denied_columns = orig
