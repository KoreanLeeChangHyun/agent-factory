# SubAgent Common Pharmaceuticals and Principles

We define the pharmaceutical and principle that applies to all subagents.

## SubAgent Common Pharmaceutical

| Pharmaceutical | Description |
|------|------|
| AskUserQuestion cannot be called | Sub-Action cannot be directly asked to the user (GitHub Issue #12890). If you need a user check, the orchestra is performed |
| Bash output notice | Bash call results inside subagents are not displayed on the user terminal. Step banner, etc. User visibility output is called Ocurator |
| Other sub-agents cannot be called directly | The agent call using Task tool is only available for Orchestra. No direct call between sub-agents |

## Terminal output principle

> **Core: Internal analysis/accounting process does not output to the terminal. outputs only. Hotel

- Code analysis process, implementation method review, judgment based on internal thinking, etc.
- "I'm going to look at", "to implement" does not output the progress of the flow
- Allowed output: return format (standard return value), error message
- Task history/Report file path is completed through the banner of the Ocurator outputs to the terminal (not directly output)
- The tool call (Read, Write, Edit, Bash, etc.) is free to use, and does not attach any unnecessary explanation before the tool call

## Return Principle

>**Registration**: If the return value exceeds the standard (1 line), the Occurator context will be invalid and the system failure will occur.

1. FAQ All job results are returned after recording in `.workflow/` file
2. FAQ Return value only ** status only** included (1 line)
3. FAQs Code, List, Table, Summary, Markdown Header, Path, MetaInfo (N), Prohibition of Absolute Inclusion on Return
4. FAQs System failure when adding one line or other line

## Error processing

| Error | Processing |
|------|------|
| Read / Write failed | Maximum 3 Retry |
| Unclear Requirements | Records of the best judgment after reconfirming the scheme and work history |
|Not judged | Error report to the orchestra |

**Review Policy**: Up to 3 times, 1 second waiting for each attempt
**SILPA CITY**: Reports with detailed error messages to the Orchestra
