# Security Policy

## Supported versions

This project is pre-1.0; security fixes land on the latest released version
(the `blustream` package on PyPI, the Home Assistant integration via HACS, and
the Control4 `.c4z` driver).

## Reporting a vulnerability

Please report security issues **privately** via GitHub Security Advisories
("Report a vulnerability" under the repository's **Security** tab) rather than
opening a public issue. We aim to acknowledge reports within a few days.

## Third-party device findings

This project integrates with Blustream DMP168 hardware over its local network
protocol. Vulnerabilities in the **device firmware itself** are the
manufacturer's to address. Where we document such findings we follow
coordinated disclosure: the vendor is given a reasonable window to respond
before any details are published.
