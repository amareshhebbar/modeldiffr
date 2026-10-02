import sys

from modeldiffr import run_audit
from modeldiffr.backend import HFBackend
from modeldiffr.report import write_reports
from modeldiffr.suites import get_suite

base_id = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen2.5-0.5B-Instruct"
derivative_id = sys.argv[2] if len(sys.argv) > 2 else "Qwen/Qwen2.5-0.5B"

base = HFBackend(base_id)
derivative = HFBackend(derivative_id)
result = run_audit(base, derivative, get_suite("quick"), progress=print)
json_path, html_path = write_reports(result, "examples_output")

for metric in result["metrics"]:
    status = "CHANGED" if metric["significant"] else "within noise"
    print(f"{metric['name']}: delta {metric['delta']:+.4f} ({status})")
print(f"open {html_path}")
