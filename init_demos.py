#!/usr/bin/env python3
"""Initialize 5 demo projects for the admin panel."""

import json
import os
import sys
from pathlib import Path

# Import defaults from app
sys.path.insert(0, ".")
from app import (
    DEFAULT_PLANNER_SYSTEM, DEFAULT_PLANNER_PROMPT,
    DEFAULT_WRITER_SYSTEM, DEFAULT_WRITER_PROMPT,
    PROJECTS_DIR, save_project,
)
from datetime import datetime

DEMOS = [
    {
        "id": "demo1-python",
        "topic": "Python 入门 30 分钟",
        "brief": "帮零基础的人理解什么是变量、循环、函数、列表、字典，并能照着写出几行能跑的代码",
        "audience": "编程零基础",
    },
    {
        "id": "demo2-review",
        "topic": "2025 我的年度复盘",
        "brief": "这一年我做的几件主要的事、踩过的几个坑、明年想试的方向",
        "audience": "朋友圈分享",
    },
    {
        "id": "demo3-coffee",
        "topic": "如何挑选一款适合自己的咖啡豆",
        "brief": "从烘焙度、产地、处理法、风味描述讲起，给一个挑豆决策框架",
        "audience": "咖啡新手",
    },
    {
        "id": "demo4-rust",
        "topic": "给老板讲清楚为什么我们应该用 Rust 重写订单系统",
        "brief": "现在用 Python 写的订单系统在大促时频繁超时，影响下单。希望说服一个非技术背景的 CEO 同意立项",
        "audience": "非技术 CEO",
    },
    {
        "id": "demo5-kyoto",
        "topic": "周末两天玩遍京都",
        "brief": "周六上午到周日晚上，预算人均 3000，希望涵盖经典景点和一两个小众体验",
        "audience": "第一次去日本的游客",
    },
]


def init():
    now = datetime.now().isoformat()
    for demo in DEMOS:
        pid = demo["id"]
        project = {
            "topic": demo["topic"],
            "brief": demo["brief"],
            "audience": demo["audience"],
            "planner_system": DEFAULT_PLANNER_SYSTEM,
            "planner_prompt": DEFAULT_PLANNER_PROMPT,
            "writer_system": DEFAULT_WRITER_SYSTEM,
            "writer_prompt": DEFAULT_WRITER_PROMPT,
            "slides": [],
            "plan": {},
            "created_at": now,
            "updated_at": now,
        }
        save_project(pid, project)
        print(f"  ✅ {pid}: {demo['topic']}")

    print(f"\n🎉 {len(DEMOS)} 个demo项目已初始化到 {PROJECTS_DIR.resolve()}/")


if __name__ == "__main__":
    init()
