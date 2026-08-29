## Purpose

Catches a prompt change that silently degrades the classifier, the
tool-using agent, or the question-rephrasing call, before it reaches a
citizen — the same regression-gate discipline `answer-quality-
evaluation` applies to retrieval and generation, applied to the prompts
themselves.

## ADDED Requirements

### Requirement: The classifier, agent, and rephrasing prompts each have a regression suite
Each of the three prompts (intent classification, the tool-using agent,
question rephrasing) SHALL have its own prompt-regression test suite
covering representative inputs and their expected classification,
tool-selection, or rephrasing behavior.

#### Scenario: All three prompts are covered
- **WHEN** the prompt-regression suite is inspected
- **THEN** it contains test cases for the classifier prompt, the agent
  prompt, and the rephrasing prompt, not just one or two of the three

### Requirement: A prompt regression fails CI
When a prompt's regression suite detects that a change to that prompt
altered its behavior on a previously passing case, CI SHALL fail the
build for that change.

#### Scenario: A degraded classification fails the build
- **WHEN** a prompt change causes the classifier prompt-regression suite
  to fail a previously passing case
- **THEN** the CI run for that change fails
