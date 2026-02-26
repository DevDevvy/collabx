# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-02-25

### Added

- Comprehensive logging infrastructure with structured logging support
- Rate limiting middleware to prevent abuse (configurable)
- Database cleanup functionality with configurable retention period
- Export logs functionality (JSON and CSV formats)
- Statistics endpoint showing collection metrics
- Filtering support in logs endpoint (by method, path pattern, date range)
- Proper .gitignore file
- CHANGELOG.md to track project changes
- Enhanced test suite with integration tests
- API documentation improvements
- CORS configuration support
- Health check enhancements with uptime tracking

### Changed

- Replaced print statements with proper logging
- Improved error handling throughout the codebase
- Enhanced security with better token validation
- Optimized database queries with indexes
- Better type hints coverage

### Fixed

- Edge cases in token normalization
- Memory leak in SSE broadcaster
- Concurrent access issues in database operations

## [0.3.0] - 2024-XX-XX

### Added

- Initial GCP Cloud Run support
- SSE streaming mode (opt-in)
- Token-based path routing

## [0.2.0] - 2024-XX-XX

### Added

- Basic polling support
- SQLite storage backend

## [0.1.0] - 2024-XX-XX

### Added

- Initial release
- Local server support
- Basic HTTP callback collection
