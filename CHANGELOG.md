# Changelog — f2cf1ae

_Updates since 6fc85814783ed9a98f32a3f68205a1a1d8a93117, through f2cf1ae_

# Changelog — f2cf1ae

## Summary
This release adds a full‑stack detail view, dark theme support, and a complete frontend source bundle. On the backend it introduces GitHub release publishing, CHANGELOG.md committing, and rich HTML email notifications.

## Features
- Added API endpoints to publish a GitHub release and commit a `CHANGELOG.md` file for a completed changelog.  
- Implemented helper to load changelog and repository data with validation.  
- Introduced `publish_service` integration for release creation and file commits.  
- Created a new HTML email template (`email_template.py`) for branded changelog notifications.  
- Notification service now generates and sends HTML email bodies alongside plain text.  
- Extended `NotifyProviderInterface` to accept an optional `html_body` argument.  
- Added `create_release` and `get_or_create_file_commit` methods to the GitHub client for release creation and file updates.  
- Updated Slack and SMTP/SendGrid providers to handle the new `html_body` parameter.  
- Frontend enhancements: detail view UI, dark theme styling, and inclusion of the full source code in the build.

## Bug Fixes
- *(none)*

## Other Changes
- Minor refactor of notification service to build HTML content before sending.  
- Updated imports and added logger for better error tracing in publishing endpoints.  

## Full Commit Log
- f2cf1ae — feat: detail view, publish release, dark theme, email HTML, full frontend source
