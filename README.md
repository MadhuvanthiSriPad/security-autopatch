# CodeQL Test Repository

A deliberately vulnerable Python application for testing Devin's CodeQL fix automation.

## Vulnerabilities Included

| # | Type | Location | CodeQL Rule |
|---|------|----------|-------------|
| 1 | Hardcoded Secrets | Lines 15-16 | py/hardcoded-credentials |
| 2 | SQL Injection | Line 27 | py/sql-injection |
| 3 | XSS | Line 35 | py/reflected-xss |
| 4 | Command Injection | Line 43 | py/command-injection |
| 5 | Path Traversal | Line 51 | py/path-injection |
| 6 | Insecure Deserialization | Line 60 | py/unsafe-deserialization |
| 7 | Weak Cryptography | Line 69 | py/weak-cryptographic-algorithm |

## Setup

1. Push this repo to GitHub
2. Go to Settings → Security → Code scanning
3. Enable CodeQL analysis
4. Wait for first scan to complete
5. Check Security tab for detected issues

## Purpose

This repo exists to test automated security fixes using the Devin API.
