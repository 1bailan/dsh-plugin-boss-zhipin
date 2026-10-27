#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""详情页直投兜底（v5.8）

背景 —— BOSS 搜索结果页存在两重淘汰机制：

  ① 卡片被虚拟滚动卸载
     → 卡片仍存在于 BOSS 数据中，只是滚过头被 DOM 卸载
     → 解法：`_restore_search.py <keyword> <目标卡片数>` 加大目标数重跑

  ② 岗位在搜索列表里被彻底剔除，但 `job_detail` 页仍「招聘中」
     → 卡片怎么滚都找不到，`_restore_search.py` 反复报 has:false
     → 已确认案例：深蓝股份 f82f94a55f84f5071Hx439S9FVpY、
                   陆川益权电子科技 168599674245fffa0nZ_3dW8EFFU
     → 解法：本脚本。改用**公司名搜索**让卡片重新出现；
             若仍找不到，直接 navigate 到 job_detail 页原地投递

本脚本走的是最后一条兜底路径：**不复用列表卡片**，直接 navigate 到
`https://www.zhipin.com/job_detail/<jobId>.html`，复用 deliver_engine 的
弹窗处理 / 致命错误检测 / 「留在此页」判定逻辑完成投递。

⚠️ 使用前提（缺一不可）：
  1. 已通过 job_detail 页确认岗位仍是「招聘中」且有「立即沟通」按钮
     （页面显示「职位已关闭 / 已下线 / 不存在」时应放弃，不要投）
  2. 该岗位已经过 AI 决策为 APPROVE（本脚本不重做决策）

用法：
    # 方式 A：按 jd_to_read.json 的 1-based 序号（该条已 APPROVE）
    python scripts/deliver_detail.py --index 4

    # 方式 B：直接给 jobId（自测/补投用）
    python scripts/deliver_detail.py --jobid 168599674245fffa0nZ_3dW8EFFU

    # 只诊断不投递
    python scripts/deliver_detail.py --jobid <jid> --dry-run

必须在 BOSS_WORK_DIR 指向的目录下运行（或设置该环境变量），
否则 PROGRESS_FILE / jd_to_read.json 会指错地方。
"""
import sys
import os
import json
import time
import argparse

from scripts.webbridge_client import (
    evaluate, navigate, health_check, handle_popup, ensure_active_tab,
    register_signal_guard, ProgressManager, SESSION,
)
from scripts.deliver_engine import (
    handle_greet_popup, click_stay_on_page, _check_fatal_patterns,
    _get_chat_button_text, check_delivery_target,
)
from scripts.serial_loop import (
    PROGRESS_FILE, DAILY_TARGET, load_jobs,
    load_serial_progress, save_serial_progress, step_finish,
)


def _dbg(s):
    print(f"[直投] {s}", flush=True)


def probe_detail_page(jid):
    """导航到详情页并做体检，返回 dict 或 None"""
    nav = navigate(f"https://www.zhipin.com/job_detail/{jid}.html")
    if not (isinstance(nav, dict) and nav.get('ok')):
        _dbg(f"导航失败: {str(nav)[:120]}")
        return None
    time.sleep(2.5)

    probe = evaluate("""
    (function(){
        var t = document.body.innerText || '';
        var btn = document.querySelector('.op-btn-chat')
               || document.querySelector('.btn-startchat, .job-chat-btn');
        return JSON.stringify({
            closed: (t.indexOf('职位已关闭')>=0 || t.indexOf('职位不存在')>=0
                     || t.indexOf('已下线')>=0 || t.indexOf('已停止招聘')>=0),
            hasBtn: !!btn,
            btnText: btn ? btn.textContent.trim() : '',
            title: document.title,
            company: (document.querySelector('.sider-company .company-info a')||{}).innerText||''
        });
    })()
    """) or "{}"

    try:
        return json.loads(probe)
    except Exception:
        _dbg(f"页面体检失败: {probe[:100]}")
        return None


def deliver_on_detail_page(jid, job=None):
    """在 job_detail 详情页原地投递，返回 (status, detail)"""
    p = probe_detail_page(jid)
    if p is None:
        return 'fail', '详情页加载失败'

    if p.get('closed'):
        return 'skip', '职位已关闭/下线'
    if not p.get('hasBtn'):
        return 'fail', f'详情页无沟通按钮: {p.get("title","")[:40]}'
    if '继续沟通' in p.get('btnText', ''):
        return 'skip', f'已沟通过: {p["btnText"]}'

    _dbg(f"详情页就绪: {p.get('btnText')} | {p.get('title','')[:40]}")

    # scrollIntoView 后点击
    scroll_result = evaluate("""
    (function(){
        var btn = document.querySelector('.op-btn-chat');
        if (!btn) btn = document.querySelector('.btn-startchat, .job-chat-btn');
        if (!btn) return 'not_found';
        btn.scrollIntoView({block: 'center'});
        return 'scrolled:' + btn.textContent.trim();
    })()
    """) or "not_found"

    if scroll_result == 'not_found':
        return 'fail', '沟通按钮未找到'
    time.sleep(0.5)

    click_result = evaluate("""
    (function(){
        var btn = document.querySelector('.op-btn-chat');
        if (!btn) btn = document.querySelector('.btn-startchat, .job-chat-btn');
        if (!btn) return 'not_found';
        btn.click();
        return 'clicked';
    })()
    """) or "not_found"

    if click_result == 'not_found':
        return 'fail', '点击时按钮消失'

    # 等弹窗 → 致命错误检测（必须在处理弹窗前，见 B34）
    time.sleep(2)
    fatal_status, fatal_detail = _check_fatal_patterns()
    if fatal_status:
        return fatal_status, fatal_detail

    popup = handle_greet_popup()
    sent_greeting = (popup != 'no_popup')
    _dbg(f"打招呼弹窗: {popup}")
    if sent_greeting:
        time.sleep(1.5)

    stay_result = click_stay_on_page()
    stayed_on_page = (stay_result == 'clicked:留在此页')
    _dbg(f"留在此页: {stay_result}")

    if stayed_on_page:
        time.sleep(1)
    elif not sent_greeting:
        handle_popup()
        time.sleep(1)

    fatal_status, fatal_detail = _check_fatal_patterns()
    if fatal_status:
        return fatal_status, fatal_detail

    btn_text = _get_chat_button_text()
    _dbg(f"投递后按钮文案: {btn_text[:20]}")

    if '继续沟通' in btn_text:
        return 'success', '投递成功(按钮已变为继续沟通)'
    if sent_greeting and stayed_on_page:
        return 'success', '投递成功(发送招呼+留在此页)'
    if sent_greeting:
        return 'success', '投递成功(已发送招呼)'
    if stayed_on_page:
        return 'success', '投递成功(留在此页已点击,招呼弹窗可能自动发送)'
    return 'unknown', f'未确认成功: popup={popup}, stay={stay_result}, btn={btn_text[:20]}'


def main():
    ap = argparse.ArgumentParser(description="详情页直投兜底（卡片被搜索列表剔除时使用）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--index', type=int, help='jd_to_read.json 中的 1-based 序号')
    g.add_argument('--jobid', type=str, help='直接指定 jobId')
    ap.add_argument('--dry-run', action='store_true', help='只诊断，不投递')
    args = ap.parse_args()

    register_signal_guard()

    if not health_check():
        print("ERROR: WebBridge 不可达，请先运行 env_check.py")
        return 1
    ensure_active_tab()

    job = None
    if args.index is not None:
        jobs = load_jobs()
        if args.index < 1 or args.index > len(jobs):
            print(f"ERROR: 索引超出范围 1~{len(jobs)}")
            return 1
        job = jobs[args.index - 1]
        jid = job.get('jobId', '')
    else:
        jid = args.jobid

    if not jid:
        print("ERROR: 未取到 jobId")
        return 1

    print(f"[直投] SESSION={SESSION}  WORK_DIR={os.environ.get('BOSS_WORK_DIR') or os.getcwd()}")
    if job:
        print(f"[直投] [{args.index}/{len(load_jobs())}] {job.get('title','')} | "
              f"{job.get('company','')} | po={job.get('page_order','?')}")
    print(f"[直投] jobId={jid}")

    tmpl = check_delivery_target(PROGRESS_FILE)
    print(f"[目标] 今日已投递 {tmpl['delivered_count']}/{tmpl['target']}"
          f"（累计 {tmpl['delivered_total']}） (还差 {tmpl['remaining']})")

    if args.dry_run:
        p = probe_detail_page(jid)
        print(f"[直投] 诊断结果: {json.dumps(p, ensure_ascii=False)}")
        return 0

    status, detail = deliver_on_detail_page(jid, job)
    print(f"[直投] 投递结果: {status} - {detail}")

    # 记账
    pm = ProgressManager(PROGRESS_FILE)
    pm.load()
    if status == 'success':
        pm.add_delivered(jid, job or {'jobId': jid})
    else:
        pm.add_failed(jid, job or {'jobId': jid}, f"{status}: {detail}")
    pm.save()

    if args.index is not None:
        progress = load_serial_progress()
        entry = {
            'index': args.index,
            'jobId': jid,
            'title': (job or {}).get('title', ''),
            'decision': 'APPROVE',
            'reason': '详情页直投兜底（卡片被搜索列表剔除）',
            'page_order': (job or {}).get('page_order', '?'),
            'deliver_status': status,
            'deliver_detail': detail,
        }
        if args.index not in progress.get('processed', []):
            progress.setdefault('processed', []).append(args.index)
        progress.setdefault('results', []).append(entry)
        if status == 'fatal_limit':
            progress['fatal_stop'] = True
            progress['fatal_reason'] = detail
        tc = check_delivery_target(PROGRESS_FILE)
        if tc['target_met']:
            progress['target_met'] = True
        save_serial_progress(progress)

    tc = check_delivery_target(PROGRESS_FILE)
    print(f"[目标] 今日已投递 {tc['delivered_count']}/{tc['target']}"
          f"（累计 {tc['delivered_total']}） (还差 {tc['remaining']})")

    if tc['target_met']:
        print("[直投] ★ 投递目标已达成，生成汇总...")
        step_finish()
    return 0


if __name__ == '__main__':
    sys.exit(main())
