<h3 align="center">Take Action</h3>
<p align="center">Review PR with OpenAI GPT model<p>

## Usage

## Setup

### Example Workflow:

```yaml
# .github/workflows/review.yml

name: Review PR with OpenAI GPT model
on:
  pull_request:
    types: [opened]
  issue_comment:
    types: [created]
jobs:
  run-local-action:
    if: |
        github.event.pull_request ||
        (github.event.issue.pull_request &&
        startsWith(github.event.comment.body, 'openai'))
    name: Review PR
    runs-on: ubuntu-latest
    steps:
      - name: Run checkout
        uses: actions/checkout@v2
      - name: Display working directory files
        run: |
          echo "Working directory files:"
          ls -al
      - name: Run custom action
        uses: ./.github/actions
        with:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}