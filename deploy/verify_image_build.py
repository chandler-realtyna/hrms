"""Verify a Docker plain-progress build against the image actually stored."""

import argparse
import re
import sys


def completed_image(log, image_id, tag):
    digest = re.findall(
        r"^(#\d+)\s+(?:writing image|exporting config|exporting manifest list) (sha256:[a-f0-9]{64})(?: [0-9.]+s)? done$",
        log,
        re.M,
    )
    if not digest:
        return False
    step = digest[-1][0]
    if image_id not in {built_id for export_step, built_id in digest if export_step == step}:
        return False
    name = re.escape(tag)
    named = re.search(rf"^{re.escape(step)}\s+naming to (?:docker\.io/(?:library/)?)?{name}(?: [0-9.]+s)? done$", log, re.M)
    done = re.search(rf"^{re.escape(step)} DONE [0-9.]+s$", log, re.M)
    return bool(named and done) and "ERROR:" not in log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    sys.exit(0 if completed_image(sys.stdin.read(), args.image_id, args.tag) else 1)
