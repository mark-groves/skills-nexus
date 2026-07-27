---
name: release-helper
description: Prepare and publish release notes for repository releases.
---

# Release helper

## Inspect the release

Read the version and recent commit history before drafting notes.

## Draft notes

Group user-visible changes by feature, fix, and compatibility impact.

## Validate

Validate the release tag and drafted notes before any publication.

## Publish

Push the release tag and publish the notes only after the user explicitly asks
for or confirms publication. Otherwise return the reviewable draft without
changing the remote repository.
