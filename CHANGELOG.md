# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

<!-- At a release: rename [Unreleased] to [X.Y.Z] - YYYY-MM-DD, add an empty [Unreleased] above it,
     and point the links below at the release tag (releases/tag/vX.Y.Z) and at compare/vX.Y.Z...HEAD. -->

## [Unreleased]

## [0.1.0] - 2026-10-19

### Added

- `Ceps` with a wrapper returning a pandas DataFrame for each of the 21 methods of the ČEPS web service.
- `Ceps.parameters()` listing the methods and the arguments and values each accepts.
- Checks of methods, aggregations, functions, versions and filter values before a request is sent.
- Dates taken as Czech local time; time series indexed in `Europe/Prague`, unique across DST changes.

[Unreleased]: https://github.com/Frantis3k/ceps-api/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Frantis3k/ceps-api/releases/tag/v0.1.0
