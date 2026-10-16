"""Build four-page named and anonymous papers, with a separate supplement."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from evaluate import file_digest, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tectonic", help="Compile all exports when an executable is supplied")
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    analysis = arguments.analysis_output
    verification = json.loads((analysis / "verification.json").read_text())
    source_files = {
        "main.tex": "canonical_source_sha256",
        "demo-appendix.tex": "demo_appendix_sha256",
        "supplement-main.tex": "supplement_source_sha256",
        "extended-methods.tex": "extended_methods_sha256",
    }
    for filename, verification_key in source_files.items():
        if file_digest(repository / "paper" / filename) != verification[verification_key]:
            raise ValueError(f"Manuscript source differs from the analysis record: {filename}")
    for manifest_name, verification_key in (
        ("manifest", "original_data_sha256"),
        ("camera-recovery-manifest", "recovery_data_sha256"),
        ("common-throw-manifest", "common_data_sha256"),
        ("later-recovery-manifest", "later_data_sha256"),
    ):
        manifest = json.loads((repository / f"data/{manifest_name}.json").read_text())
        if manifest["sha256"] != verification[verification_key]:
            raise ValueError("Analysis data differ from the recorded scientific archives")
    arguments.output.mkdir(parents=True, exist_ok=False)
    generated = arguments.output / "generated"
    generated.mkdir()
    available_inputs = {
        "simulation-snapshots.png": analysis / "original/generated/simulation-snapshots.png",
        "camera-recovery.png": analysis / "recovery/camera-recovery.png",
        "comparison-plain.tex": analysis / "original/generated/comparison-plain.tex",
        "policy-comparison-table.tex": analysis / "original/generated/policy-comparison-table.tex",
        "common-throw-effects.tex": analysis / "common/control/common-throw-effects.tex",
        "common-throw-table.tex": analysis / "common/control/common-throw-table.tex",
        "recovery-motion-effects.tex": analysis
        / "recovery-sensitivity/recovery-motion-effects.tex",
        "camera-recovery-effects.tex": analysis / "recovery/camera-recovery-effects.tex",
        "camera-recovery-table.tex": analysis / "recovery/camera-recovery-table.tex",
    }
    source = "\n".join((repository / "paper" / filename).read_text() for filename in source_files)
    referenced_inputs = set(
        re.findall(r"\\(?:includegraphics(?:\[[^\]]*\])?|input)\{generated/([^}]+)\}", source)
    )
    if not referenced_inputs or referenced_inputs - available_inputs.keys():
        raise ValueError("Manuscript contains an unknown or missing generated input")
    for name in referenced_inputs:
        shutil.copy2(available_inputs[name], generated / name)
    template_manifest = json.loads((repository / "paper/template-manifest.json").read_text())
    if file_digest(repository / "paper/IEEEtran.cls") != template_manifest["IEEEtran.cls"]:
        raise ValueError("The official conference class has changed")
    for name in (*source_files, "IEEEtran.cls", "references.bib"):
        shutil.copy2(repository / "paper" / name, arguments.output / name)
    wrappers = {
        "paper": "\\input{main.tex}\n",
        "paper-anonymous": "\\def\\AnonymousSubmission{1}\n\\input{main.tex}\n",
        "supplement": "\\input{supplement-main.tex}\n",
    }
    executable = shutil.which(arguments.tectonic) if arguments.tectonic else None
    if arguments.tectonic and executable is None:
        raise FileNotFoundError("Tectonic executable is unavailable")
    for name, wrapper in wrappers.items():
        (arguments.output / f"{name}.tex").write_text(wrapper)
        if executable:
            subprocess.run(
                [executable, "--keep-logs", "--keep-intermediates", f"{name}.tex"],
                cwd=arguments.output,
                check=True,
            )
            log = (arguments.output / f"{name}.log").read_text()
            if "Overfull" in log or re.search(
                r"(?:Citation|Reference).*undefined|There were undefined references", log
            ):
                raise ValueError(f"{name} has unresolved references or overflowing text")
            if name != "supplement":
                auxiliary = (arguments.output / f"{name}.aux").read_text()
                reference_page = re.search(
                    r"\\newlabel\{page:references\}\{\{[^}]*\}\{(\d+)\}", auxiliary
                )
                if reference_page is None or int(reference_page[1]) > 5:
                    raise ValueError(f"{name} exceeds four main-content pages")
    write_json(
        arguments.output / "preparation.json",
        {
            **{
                verification_key: file_digest(repository / "paper" / filename)
                for filename, verification_key in source_files.items()
            },
            "analysis_verification_sha256": file_digest(analysis / "verification.json"),
            "generated_inputs": {
                name: file_digest(available_inputs[name]) for name in sorted(referenced_inputs)
            },
            "exports": {
                name: file_digest(arguments.output / f"{name}.pdf") if executable else None
                for name in wrappers
            },
            "scope": "Named and anonymous main papers share research text and figures, with at most four content pages; supplementary methods and demo description are a separate PDF",
            "status": "Check final page budgets, anonymity and embedded fonts before submission",
        },
    )


if __name__ == "__main__":
    main()
