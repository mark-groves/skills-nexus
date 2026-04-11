---
name: skill-name
description: "One-line: what this skill does + when Claude should use it"
user-invocable: true
# allowed-tools:
#   - Read
#   - Grep
# model: sonnet
# context: prompt context injected when the skill is invoked
# agent: agent-name
# argument-hint: "<file-path>"
# disable-model-invocation: false
# hooks:
#   PreToolUse:
#     - matcher: "ToolName"
#       hooks:
#         - type: command
#           command: "path/to/script.sh"
---

# Instructions

Describe the skill's behavior here.
Reference bundled scripts, references, and assets with paths relative
to this skill root. Do not probe user-level or project-level install
locations at runtime; the client handles discovery and precedence.
