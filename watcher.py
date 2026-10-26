"""Read VisaBida's public hourly summary; send observed changes through Bark."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import urllib.request

SOURCE = 'https://visabida.com/trend'
STATE = Path('state.json')


def fetch_snapshot():
    req = urllib.request.Request(SOURCE, headers={'User-Agent': 'WuhanVisaPersonalWatcher/1.0'})
    with urllib.request.urlopen(req, timeout=40) as response:
        document = response.read().decode('utf-8')
    article = re.search(r'<article\b[^>]*data-post="wuhan"[^>]*>(.*?)</article>', document, re.S)
    if not article:
        raise RuntimeError('Public Wuhan summary missing; no availability conclusion can be drawn.')
    card = article.group(1)
    stamp = re.search(r'<time\b[^>]*datetime="([^"]+)"', card)
    if not stamp:
        raise RuntimeError('Wuhan observation timestamp missing.')
    observed = dt.datetime.fromisoformat(stamp.group(1).replace('Z', '+00:00'))
    age = (dt.datetime.now(dt.timezone.utc) - observed).total_seconds()
    if age < -600 or age > 3 * 3600:
        raise RuntimeError('Wuhan summary is stale or has an invalid observation timestamp.')
    date_element = re.search(r'<p\b[^>]*class="summary-date"[^>]*>(.*?)</p>', card, re.S)
    if not date_element:
        raise RuntimeError('Wuhan date field missing.')
    date_text = html.unescape(re.sub('<[^>]+>', '', date_element.group(1))).strip()
    date_match = re.fullmatch(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_text)
    if date_match:
        date = dt.date(*map(int, date_match.groups()))
        if date < dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date():
            raise RuntimeError('Summary contains a past appointment date.')
        earliest = date.isoformat()
    elif date_text == '本次未观测到日期':
        earliest = None
    else:
        raise RuntimeError('Unrecognized Wuhan availability field.')
    count = re.search(r'(\d+)\s*个可约日期', html.unescape(re.sub('<[^>]+>', '', card)))
    if not count:
        raise RuntimeError('Available-date count missing.')
    # Verify the public page still labels this summary as B1/B2 regular interviews.
    before = re.sub('<[^>]+>', ' ', document[:article.start()])
    if not re.search(r'B1/B2\s*·\s*普通面谈\s*·\s*每小时更新', before):
        raise RuntimeError('Cannot verify B1/B2 regular-interview category.')
    return {'earliest': earliest, 'count': int(count.group(1)), 'observed': observed.isoformat()}


def push(title, body):
    endpoint = os.environ['VISA_BARK_ENDPOINT'].strip()
    payload = json.dumps({'title': title, 'body': body, 'group': 'wuhan-b1b2',
                          'url': SOURCE, 'sound': 'default'}, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(endpoint, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get('code') != 200:
        raise RuntimeError('Bark notification was not accepted.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    try:
        current = fetch_snapshot()
    except Exception:
        # Notify once per outage, then stay quiet until the source recovers.
        if not state.get('source_failed'):
            push('武汉 B1/B2 提醒数据暂不可用', '无法读取有效的第三方观测摘要。这不代表没有号源；恢复后会通知。')
        state['source_failed'] = True
        STATE.write_text(json.dumps(state), encoding='utf-8')
        raise
    previous = state.get('snapshot')
    changed = previous is None or any(current[k] != previous[k] for k in ('earliest', 'count'))
    recovered = state.get('source_failed', False)
    observed = dt.datetime.fromisoformat(current['observed']).astimezone(dt.timezone(dt.timedelta(hours=8)))
    summary = (f"最早日期：{current['earliest']}；共 {current['count']} 个日期。" if current['earliest']
               else '最近一次观测未发现日期。')
    body = (summary + f"\n观测时间：{observed:%m-%d %H:%M}（北京时间）"
            + '\n来源：VisaBida 每小时公开摘要，非官方实时空位；请登录官方预约系统确认。')
    if args.status or recovered or (changed and current['earliest']):
        title = '武汉 B1/B2 第三方观测更新' if not args.status else '武汉 B1/B2 云端提醒测试'
        if recovered:
            title = '武汉 B1/B2 提醒数据已恢复'
        push(title, body)
    STATE.write_text(json.dumps({'snapshot': current, 'source_failed': False}), encoding='utf-8')
    print(json.dumps({'status': 'OK', 'source': SOURCE, **current}, ensure_ascii=False))


if __name__ == '__main__':
    main()
