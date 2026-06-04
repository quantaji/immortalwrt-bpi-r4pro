#!/usr/bin/env python3

from os import getenv, environ
from pathlib import Path
from subprocess import run, PIPE
from sys import argv
import json

if len(argv) != 2:
    print("JSON info files script requires output file as argument")
    exit(1)

output_path = Path(argv[1])

assert getenv("WORK_DIR"), "$WORK_DIR required"

work_dir = Path(getenv("WORK_DIR"))

output = {}


def get_initial_output(image_info):
    # preserve existing profiles.json
    if output_path.is_file():
        profiles = json.loads(output_path.read_text())
        if profiles["version_code"] == image_info["version_code"]:
            return profiles
    return image_info


for json_file in work_dir.glob("*.json"):
    image_info = json.loads(json_file.read_text())

    if not output:
        output = get_initial_output(image_info)

    # get first and only profile in json file
    device_id, profile = next(iter(image_info["profiles"].items()))
    if device_id not in output["profiles"]:
        output["profiles"][device_id] = profile
    else:
        output["profiles"][device_id]["images"].extend(profile["images"])

# make image lists unique by name, keep last/latest
for device_id, profile in output.get("profiles", {}).items():
    profile["images"] = list({e["name"]: e for e in profile["images"]}.values())


if output:
    # Local-only build workaround: do not include this in the future BPI-R4 Pro PR.
    make_env = environ.copy()
    make_env["TOPDIR"] = str(Path().cwd())

    make_output = run(
        [
            "make",
            "--no-print-directory",
            "-C",
            "target/linux/",
            "val.DEFAULT_PACKAGES",
            "val.ARCH_PACKAGES",
            "val.LINUX_VERSION",
            "val.LINUX_RELEASE",
            "val.LINUX_VERMAGIC",
            "V=s",
        ],
        stdout=PIPE,
        check=True,
        env=make_env,
        universal_newlines=True,
    ).stdout.splitlines()

    make_values = [
        line
        for line in make_output
        if line
        and not line.startswith(("make[", "WARNING:", "time:", "Checking "))
    ]

    if len(make_values) < 5:
        raise RuntimeError(
            "target/linux make value query returned fewer than 5 values:\n"
            + "\n".join(make_output)
        )

    (
        default_packages,
        output["arch_packages"],
        linux_version,
        linux_release,
        linux_vermagic,
    ) = make_values[-5:]

    output["default_packages"] = sorted(default_packages.split())
    output["linux_kernel"] = {
        "version": linux_version,
        "release": linux_release,
        "vermagic": linux_vermagic,
    }
    output_path.write_text(json.dumps(output, sort_keys=True, separators=(",", ":")))
else:
    print("JSON info file script could not find any JSON files for target")
