# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-12-30

### Added
- New `download_daily_csv()` method for downloading daily event CSV files
- New exception classes: `SubscriptionError`, `NotFoundError`, `ServiceUnavailableError`
- Support for API v0.5 daily CSV download endpoint

## [0.2.0] - 2025-01-23

### Added
- New `event_request_add()` method for submitting async event add requests
- New `event_request_status()` method for checking the status of submitted jobs
- Support for 202 (Accepted) status codes in API responses
- Example scripts for using the new async event request endpoints
- Unit tests for the new endpoints

### Changed
- Improved error handling to support 404 (Not Found) status codes
- Updated README with examples of new async methods

## [0.1.1] - Previous Release

### Changed
- Minor bug fixes and improvements

## [0.1.0] - Initial Release

### Added
- Initial SDK implementation
- `search_events()` method for searching events
- `get_sales_data()` method for retrieving sales data
- `get_listings()` method for getting current listings
- Basic authentication and error handling
- Unit tests and integration tests
- Example scripts