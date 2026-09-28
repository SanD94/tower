# Experiment decisions

## Walking CLI — continue

The minimal Python CLI can identify a Git workspace and exact revision from either
the repository root or a nested path, distinguish a dirty working copy, and list
the searchable files selected by `rg`. Its versioned JSON output is sufficient to
identify the evidence source for the next snapshot experiment. Continue to the
inspectable-evidence slice without adding another VCS backend or file-discovery
mechanism.
