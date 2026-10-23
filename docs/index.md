---
title: Modeldiffr
description: Audit what changed between a base language model and any fine tune, quant, merge or edit, with intervals, internals and a report anyone can verify.
template: home.html
hide:
  - navigation
  - toc
---

<div class="mdr-home" markdown>

## One report, five questions { .mdr-section-title }

Each layer answers a question the one before it raises. Run as many as the decision needs; every layer writes a file bound to the same weights.

<ol class="mdr-layers">
<li>
<div class="mdr-layers__name">Proof</div>
<div class="mdr-layers__q">Which exact models, items and settings were compared, and can anyone check that?</div>
<div class="mdr-layers__how"><code>modeldiffr verify</code> <code>modeldiffr sign</code> <a href="concepts/proof/">Fingerprints and proof</a></div>
</li>
<li>
<div class="mdr-layers__name">Behavior</div>
<div class="mdr-layers__q">What changed on thirteen benchmarks, and is it larger than noise?</div>
<div class="mdr-layers__how"><code>modeldiffr audit</code> <a href="concepts/statistics/">Statistics</a></div>
</li>
<li>
<div class="mdr-layers__name">Representation</div>
<div class="mdr-layers__q">Which layers moved, and which features are new, lost or reshaped?</div>
<div class="mdr-layers__how"><code>modeldiffr layers</code> <code>modeldiffr features</code> <a href="concepts/representational/">Representational layer</a></div>
</li>
<li>
<div class="mdr-layers__name">Cause</div>
<div class="mdr-layers__q">How much of the behavioral change do those layers and features carry?</div>
<div class="mdr-layers__how"><code>modeldiffr causal</code> <a href="concepts/causal/">Causal layer</a></div>
</li>
<li>
<div class="mdr-layers__name">Anomaly</div>
<div class="mdr-layers__q">Is there an input where the derivative behaves unlike anything in its base?</div>
<div class="mdr-layers__how"><code>modeldiffr scan</code> <a href="concepts/anomaly/">Anomaly scan</a></div>
</li>
</ol>

## Nobody has to take your word for it { .mdr-section-title }

An audit id is the hash of everything that defines the comparison, computed before anything runs. Every item and result is committed to in a Merkle tree, and the report can be signed with Sigstore and timestamped on Bitcoin or an L2. Anyone can recompute it from the file, or from the real weights with `--models`.

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

[**Find changed features**<br><span>Train a crosscoder and read what is new in the derivative.</span>](guides/features.md)

[**Publish audits**<br><span>Batch many pairs and build a registry that verifies in the browser.</span>](guides/registry.md)

[**Python API**<br><span>Run audits from your own code with any backend.</span>](guides/python_usage.md)

</div>

## Talk to the maintainer { .mdr-section-title }

<div class="mdr-contact" markdown>

[**Report a bug**<br><span>Opens a GitHub issue with the bug form.</span>](https://github.com/amareshhebbar/modeldiffr/issues/new?template=bug_report.yml)

[**Request a feature**<br><span>A metric, suite or backend you need.</span>](https://github.com/amareshhebbar/modeldiffr/issues/new?template=feature_request.yml)

[**Email me**<br><span>hebbar.gvamaresh@gmail.com, for audits of your models or collaboration.</span>](mailto:hebbar.gvamaresh@gmail.com?subject=Modeldiffr)

</div>

<p class="mdr-status">Version 0.9: every layer has shipped. Version 1.0 waits for the published study and zoo results described in the <a href="roadmap/">roadmap</a>, and the backdoor scan makes no claim about real models until then.</p>

</div>