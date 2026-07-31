# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability within CyberGuide, please send an email to parthasarathi442004@gmail.com. All security vulnerabilities will be promptly addressed.

**Please do not report security vulnerabilities through public GitHub issues.**

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Security Measures

### Authentication & Authorization

- API key authentication for all endpoints
- JWT token support (optional)
- Role-based access control (planned)

### Data Protection

- Environment variables for sensitive configuration
- Encryption for secrets at rest
- No hardcoded passwords or API keys

### Input Validation

- Pydantic models for request validation
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via input sanitization
- Rate limiting on API endpoints

### Network Security

- CORS configuration for production
- HTTPS enforcement (via reverse proxy)
- Security headers (HSTS, X-Content-Type-Options, etc.)

### Scraping Ethics

- Respect robots.txt where applicable
- Rate limiting on external requests
- User-Agent identification
- Prefer official APIs and RSS feeds

## Configuration Security

### Environment Variables

Never commit sensitive values to version control:

```bash
# Good - use environment variables
DATABASE_URL=postgresql://user:password@localhost/db
SECRET_KEY=your-secret-key

# Bad - never hardcode
DATABASE_URL=postgresql://root:password123@localhost/db
```

### Secrets Management

```python
# Use the SecretManager for sensitive data
from interntrack.utils.encryption import SecretManager

manager = SecretManager(settings.encryption_key)
encrypted = manager.encrypt("sensitive-api-key")
decrypted = manager.decrypt(encrypted)
```

## Best Practices

### For Developers

1. Never commit `.env` files
2. Use environment variables for configuration
3. Validate all user inputs
4. Use parameterized queries
5. Keep dependencies updated
6. Run security scans regularly

### For Deployment

1. Use HTTPS in production
2. Enable rate limiting
3. Set secure CORS origins
4. Use a reverse proxy (nginx, Traefik)
5. Enable logging and monitoring
6. Regular security audits

## Dependency Security

```bash
# Check for known vulnerabilities
pip install safety
safety check -r requirements.txt

# Run bandit security linter
pip install bandit
bandit -r src/
```

## Update Policy

Security updates will be released as soon as possible after a vulnerability is confirmed. Critical vulnerabilities will be patched within 48 hours.

## Contact

- **Security Email**: parthasarathi442004@gmail.com
- **GitHub Issues**: For non-sensitive bugs only
- **Documentation**: See docs/SECURITY-AND-METHODOLOGIES.md

## Acknowledgments

We thank all security researchers who responsibly disclose vulnerabilities.
