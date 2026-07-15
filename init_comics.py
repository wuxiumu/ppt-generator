#!/usr/bin/env python3
"""Initialize demo comic projects from comic-inputs/ into comics/ directory."""

import json
import uuid
from pathlib import Path
from datetime import datetime


def init_demo_comics():
    inputs_dir = Path("comic-inputs")
    comics_dir = Path("comics")
    comics_dir.mkdir(exist_ok=True)

    if not inputs_dir.exists():
        print("comic-inputs/ directory not found.")
        return

    count = 0
    for f in sorted(inputs_dir.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)

        cid = uuid.uuid4().hex[:8]
        comic = {
            "topic": data.get("topic", "新故事"),
            "child_name": data.get("child_name", "小朋友"),
            "age": data.get("age", 5),
            "template": data.get("template", "custom"),
            "extra": data.get("extra", ""),
            "pages": [],
            "plan": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        cdir = comics_dir / cid
        cdir.mkdir(parents=True, exist_ok=True)
        with open(cdir / "comic.json", "w", encoding="utf-8") as out:
            json.dump(comic, out, ensure_ascii=False, indent=2)

        print(f"  {cid} — {comic['topic']} ({comic['child_name']}, {comic['age']}岁, {comic['template']})")
        count += 1

    print(f"\nInitialized {count} demo comic projects in comics/")


if __name__ == "__main__":
    init_demo_comics()
