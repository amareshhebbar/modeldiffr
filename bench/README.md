# Modeldiffr bench

This folder tests Modeldiffr itself. A good audit tool must do three things: find real changes, stay quiet when nothing changed, and refuse reports that someone edited.

## What it runs

* 10 null pairs on Qwen2.5 0.5B Instruct: 5 identical copies and 5 copies with noise at 0.0001 of each tensor's std. The right answer is "no change".
* 10 planted changes on the same model: weight noise, pruning, a zeroed MLP and a scaled MLP. The right answer is "change".
* Real derivatives: the ShortThink SFT, DPO, GRPO and TIES models, ToolSure ORPO, Stretch32K YaRN and SFT, two public instruction tunes, and the BitNarrow edits when they exist.
* A tamper test: every finished report is copied and edited three ways, then `modeldiffr verify` must reject it.

Every audit uses the `lite` suite and the released CLI (`modeldiffr batch`).

## Run

```bash
pip install -e ".[hf,tasks,batch]" -r bench/requirements.txt
SMOKE=1 bash bench/run.sh
bash bench/run.sh
python bench/publish.py
```

Add the BitNarrow pairs after the BitNarrow bench has made its exports:

```bash
BITNARROW_EXPORTS=/path/to/bitnarrow/exports bash bench/run.sh
```

Finished audits are skipped, so this only runs the new pairs.

## Verify (no GPU)

```bash
python -c "from huggingface_hub import snapshot_download as s; s('AmareshHebbar/Modeldiffr_Bench', repo_type='dataset', local_dir='bench/results')"
python bench/verify.py --deep
```
