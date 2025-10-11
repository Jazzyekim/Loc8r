from __future__ import annotations

import json
from pathlib import Path

from locator_scanner.codegen_pf import generate_for_file


def test_locator_priority_and_generation(tmp_path: Path):
    # Prepare sample JSON similar to masha.json
    sample = [
        {
            "tag": "input",
            "attributes": {
                "placeholder": "Username",
                "type": "text",
                "data-test": "username",
                "id": "user-name",
                "name": "user-name",
            },
            "id": "user-name",
            "name": "Username",
            "xpath": "//*[@id='user-name']",
            "css": "#user-name",
        },
        {
            "tag": "input",
            "attributes": {
                "placeholder": "Password",
                "type": "password",
                "data-test": "password",
                "id": "password",
                "name": "password",
            },
            "id": "password",
            "name": "Password",
            "xpath": "//*[@id='password']",
            "css": "#password",
        },
        {
            "tag": "input",
            "attributes": {
                "type": "submit",
                "data-test": "login-button",
                "id": "login-button",
                "name": "login-button",
                "value": "Login",
            },
            "id": "login-button",
            "name": "Login",
            "xpath": "//input[@data-test='login-button']",
            "css": "input[data-test=\"login-button\"]",
        },
    ]

    json_path = tmp_path / "masha.json"
    json_path.write_text(json.dumps(sample), encoding="utf-8")

    out_root = tmp_path / "out"
    out_file = generate_for_file(
        json_path=json_path,
        package="com.example.pages",
        provided_page_name="Login",
        out_dir=out_root,
        timeout_seconds=5,
        name_annotation_import="com.example.annotations.Name",
    )

    text = out_file.read_text(encoding="utf-8")

    assert "package com.example.pages;" in text
    assert "@Name(\"Login\")" in text
    assert "public class LoginPage" in text

    # Fields
    assert "@FindBy(id = \"user-name\")" in text or "@FindBy(css = \"[data-test='username']\")" in text
    assert "@FindBy(id = \"password\")" in text or "@FindBy(css = \"[data-test='password']\")" in text
    assert "@FindBy(css = \"input[data-test='login-button']\")" in text or "@FindBy(css = \"[data-test='login-button']\")" in text
