---
name: example
description: "Template skill. Use when the user asks how to write a skill."
---
A skill is a folder with a SKILL.md file. The description in the header is always loaded into the prompt;
the body is loaded only when the agent calls the skills_read tool. Put helper scripts in a `scripts/` folder
and call them as `python3 "{baseDir}/scripts/your_script.py"`.
