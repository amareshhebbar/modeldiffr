---
title: Modeldiffr
description: Find out what really changed when someone fine tuned, quantized, merged or edited a language model, with a report anyone can check.
template: home.html
hide:
  - navigation
  - toc
---

<div class="mdr-home" markdown>

## What it does { .mdr-section-title }

You have a base model and a model built from it. Modeldiffr gives both the exact same questions, tells you which differences are real and which are luck, shows you where inside the model the change happened, and writes a report anyone can check. New here? Read [How it works](concepts/how_it_works.md).

## One report, five questions { .mdr-section-title }

Each step answers the question the step before it raises. Run as many as you need. Every step writes a file tied to the same weights.

<ol class="mdr-layers">
<li>
<div class="mdr-layers__name">Proof</div>
<div class="mdr-layers__q">Which exact models and settings were compared, and can anyone check it?</div>
<div class="mdr-layers__how"><code>modeldiffr verify</code> <code>modeldiffr sign</code> <a href="concepts/proof/">Fingerprints and proof</a></div>
</li>
<li>
<div class="mdr-layers__name">Behavior</div>
<div class="mdr-layers__q">Did scores change on thirteen benchmarks, and is the change bigger than luck?</div>
<div class="mdr-layers__how"><code>modeldiffr audit</code> <a href="concepts/statistics/">Statistics</a></div>
</li>
<li>
<div class="mdr-layers__name">Representation</div>
<div class="mdr-layers__q">Which layer changed, and which internal features are new, lost or reshaped?</div>
<div class="mdr-layers__how"><code>modeldiffr layers</code> <code>modeldiffr features</code> <a href="concepts/layer_by_layer/">Layer by layer</a> <a href="concepts/representational/">Features</a></div>
</li>
<li>
<div class="mdr-layers__name">Cause</div>
<div class="mdr-layers__q">Do those layers and features actually cause the behavior change?</div>
<div class="mdr-layers__how"><code>modeldiffr causal</code> <a href="concepts/causal/">Causal tests</a></div>
</li>
<li>
<div class="mdr-layers__name">Anomaly</div>
<div class="mdr-layers__q">Is there a strange input where the derivative acts very differently from its base?</div>
<div class="mdr-layers__how"><code>modeldiffr scan</code> <a href="concepts/anomaly/">Anomaly scan</a></div>
</li>
</ol>

## Nobody has to take your word for it { .mdr-section-title }

Every audit gets an id, which is a hash of the models and settings, made before anything runs. Every question and answer is hashed into the report, so editing one number breaks it. You can sign the report with Sigstore and timestamp it on Bitcoin or an L2. Anyone can recheck it from the file, or from the real weights with `--models`.

[Verify a report](guides/verify.md){ .mdr-link } [Sign and verify](guides/signing.md){ .mdr-link }

```text
$ modeldiffr verify report.json --models --key acme.pub
audit id mdr1:71e1c0a4b2d39f10...
PASS  schema                     valid against report schema 0.3
PASS  audit_id                   mdr1:71e1c0a4b2d39f10...
PASS  results_root               sha256:4be1...
PASS  metrics                    17 metrics recomputed from the items
PASS  base_model_files           weights match the report
PASS  derivative_model_files     weights match the report
PASS  signature                  signed with acme.pub

verified
```

## Where to start { .mdr-section-title }

<div class="mdr-starts" markdown>

[**Quickstart**<br><span>Install, run a first audit on a laptop, read the report.</span>](quickstart.md)

[**Gate a checkpoint in CI**<br><span>Fail a pull request when a metric changes, and upload a signed report.</span>](guides/publishing.md#github-action)

[**Audit a quant**<br><span>Compare a GGUF build with its original through llama.cpp.</span>](guides/backends.md#llamacpp-and-gguf)

[**Compare layer by layer**<br><span>Find the layer where the derivative starts to differ, then what changed there.</span>](concepts/layer_by_layer.md)

[**Publish audits**<br><span>Batch many pairs and build a registry that verifies in the browser.</span>](guides/registry.md)

[**Python API**<br><span>Run audits from your own code with any backend.</span>](guides/python_usage.md)

</div>

## Talk to the maintainer { .mdr-section-title }

<div class="mdr-contact" markdown>

[**Report a bug**<br><span>Opens a GitHub issue with the bug form.</span>](https://github.com/amareshhebbar/modeldiffr/issues/new?template=bug_report.yml)

[**Request a feature**<br><span>A metric, suite or backend you need.</span>](https://github.com/amareshhebbar/modeldiffr/issues/new?template=feature_request.yml)

[**Email me**<br><span>hebbar.gvamaresh@gmail.com, for audits of your models or collaboration.</span>](mailto:hebbar.gvamaresh@gmail.com?subject=Modeldiffr)

</div>

<p class="mdr-status">Version 0.9: every feature is built. Version 1.0 comes after the public study and the backdoor test results are published. See the <a href="roadmap/">roadmap</a>. Until then the backdoor scan makes no claim about real models.</p>

</div>