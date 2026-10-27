#!/usr/bin/env python3
"""把 user_profile.example.json 复制到工作目录，首次使用时生成 user_profile.json。"""

import os
import shutil

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK_DIR = os.environ.get("BOSS_WORK_DIR", os.getcwd())

src = os.path.join(SKILL_DIR, "user_profile.example.json")
dst = os.path.join(WORK_DIR, "user_profile.json")


def main() -> int:
    if os.path.exists(dst):
        print(f"[画像] 已存在: {dst}")
        print("[画像] 如需修改，直接编辑该文件后重新运行。")
        return 0
    if not os.path.exists(src):
        print(f"[画像] 找不到模板: {src}")
        return 1
    os.makedirs(WORK_DIR, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"[画像] 已创建: {dst}")
    print("[画像] 请先填写 user_name / target_city / city_code / min_salary_k / daily_target / search_keywords 等字段。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
