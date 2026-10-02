# Security Policy

## Supported versions

Modeldiffr is in early development. Security fixes are made on the latest released version only.

* 0.1.x: supported
* Older versions: not supported

## Reporting a vulnerability in Modeldiffr

Please **do not** open a public issue for security problems.

Report privately through either channel:

* GitHub private vulnerability reporting: the "Report a vulnerability" button on the repository's Security tab.
* Email: hebbar.gvamaresh@gmail.com with the subject line "Modeldiffr security".

Please include:

* A description of the issue and its impact.
* Steps or a minimal example to reproduce it.
* The Modeldiffr version, Python version, and operating system.

You can expect an acknowledgement within 3 working days and a status update within 10 working days. Once a fix is released, you will be credited in the changelog unless you prefer to stay anonymous.

## Scope

In scope:

* Code execution or file system access caused by Modeldiffr itself, for example through report generation or path handling.
* Injection in the generated HTML report.
* Leaking credentials or tokens into reports or logs.

Out of scope:

* Vulnerabilities in PyTorch, Transformers, or other dependencies. Please report those upstream.
* Risks from loading untrusted models. Modeldiffr loads models through Transformers and does **not** enable remote code unless you pass the trust remote code flag. Only use that flag with models you trust, and prefer models stored in the safetensors format.

## Findings about third party models

Modeldiffr may reveal that a public model has a safety regression or a hidden behavior. That is a finding about the model, not about Modeldiffr. Please consider reporting it privately to the model's publisher and allowing reasonable time to respond before publishing details.
