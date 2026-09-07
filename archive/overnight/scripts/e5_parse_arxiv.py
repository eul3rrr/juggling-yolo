#!/usr/bin/env python3
"""Parse arXiv Atom XML from stdin into compact text lines."""
import sys
import xml.etree.ElementTree as ET

NS = {"a": "http://www.w3.org/2005/Atom"}

root = ET.parse(sys.stdin).getroot()
entries = root.findall("a:entry", NS)
if not entries:
    print("(no results)")
for entry in entries:
    title = " ".join((entry.findtext("a:title", "", NS) or "").split())
    arxiv_id = (entry.findtext("a:id", "", NS) or "").split("/abs/")[-1]
    published = (entry.findtext("a:published", "", NS) or "")[:10]
    authors = ", ".join(
        a.findtext("a:name", "", NS) for a in entry.findall("a:author", NS)[:3]
    )
    summary = " ".join((entry.findtext("a:summary", "", NS) or "").split())[:400]
    cats = ",".join(c.get("term", "") for c in entry.findall("a:category", NS))
    print(f"[{arxiv_id}] {title}")
    print(f"  {published} | {cats} | {authors}")
    print(f"  {summary}")
    print()
