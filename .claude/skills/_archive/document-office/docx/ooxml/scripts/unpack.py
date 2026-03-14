#!/usr/bin/env python3
"""Unpack and format XML contents of Office files (.docx, .pptx, .xlsx)"""

import argparse
import random
import defusedxml.minidom
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Unpack and format XML contents of Office files')
    parser.add_argument('input_file', help='Input Office file (.docx, .pptx, .xlsx)')
    parser.add_argument('output_dir', help='Output directory path')
    args = parser.parse_args()

    input_file = args.input_file
    output_path = Path(args.output_dir).resolve()

    # Extract with Zip Slip protection
    output_path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(input_file) as zf:
        for member in zf.namelist():
            member_path = (output_path / member).resolve()
            # Zip Slip prevention: ensure extracted path is within output directory
            if not member_path.is_relative_to(output_path):
                raise ValueError(f"Unsafe path in archive: {member}")
        zf.extractall(output_path)

    # Pretty print all XML files
    xml_files = list(output_path.rglob("*.xml")) + list(output_path.rglob("*.rels"))
    for xml_file in xml_files:
        content = xml_file.read_text(encoding="utf-8")
        dom = defusedxml.minidom.parseString(content)
        xml_file.write_bytes(dom.toprettyxml(indent="  ", encoding="ascii"))

    # For .docx files, suggest an RSID for tracked changes
    if input_file.endswith(".docx"):
        suggested_rsid = "".join(random.choices("0123456789ABCDEF", k=8))
        print(f"Suggested RSID for edit session: {suggested_rsid}")


if __name__ == "__main__":
    main()
