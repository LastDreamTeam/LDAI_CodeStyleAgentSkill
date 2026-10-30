# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 精选区域历史的本地SQLite工具；不自动抓取会话或判断事实真假。"""
import argparse
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
import sys

DB_NAME = 'history.sqlite3'
DEFAULT_LIMITS = {'USER.md': 4000, 'MEMORY.md': 6000, 'DEBUG.md': 6000}


def canonical(value):
    """OpenAI: 固定JSON序列化，保证跨机记录的内容校验不依赖键顺序。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(text):
    """OpenAI: 对准确UTF-8文本计算SHA256；这不是来源真实性认证。"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@contextmanager
def connect(area, create=False, readonly=False):
    """OpenAI: 只连接显式Agentic路径；只读查询不能意外创建空库。"""
    area = Path(area)
    if area.name != 'Agentic' or area.is_symlink() or not area.is_dir():
        raise ValueError('需要已存在且非符号链接的Agentic目录')
    path = area / DB_NAME
    if path.is_symlink():
        raise ValueError('不跟随数据库符号链接')
    if not create and not path.is_file():
        raise ValueError('历史库不存在；禁止凭空创建或压缩原文')
    mode = 'rwc' if create else ('ro' if readonly else 'rw')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=' + mode, uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def metadata(db):
    """OpenAI: 核schema与责任区元数据，拒绝把别的数据库当本工具历史。"""
    if db.execute('PRAGMA user_version').fetchone()[0] != 2:
        raise ValueError('需要schema 2；旧库不自动改写，请用旧版导出后向新库显式导入')
    row = db.execute('SELECT value FROM metadata WHERE key=?', ('area',)).fetchone()
    if row is None:
        raise ValueError('缺少责任区元数据')
    info = json.loads(row[0])
    if set(info) != {'scope', 'description', 'readme', 'visibility'}:
        raise ValueError('责任区元数据结构错误')
    return info


def initialize(area, readme, scope, description, visibility):
    """OpenAI: 显式建立责任区库，已有库仅允许同scope的幂等初始化。"""
    area = Path(area)
    if not scope.strip() or not description.strip() or visibility not in ('public', 'private'):
        raise ValueError('必须声明scope、边界与目标可见性')
    entry = area / readme
    if Path(readme).is_absolute() or not entry.is_file():
        raise ValueError('必须提供真实README相对入口')
    info = dict(scope=scope, description=description, readme=readme, visibility=visibility)
    with connect(area, create=True) as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
            if metadata(db) != info:
                raise ValueError('现有责任区不匹配')
        else:
            db.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute("CREATE TABLE records(id TEXT PRIMARY KEY,payload TEXT NOT NULL,sha256 TEXT NOT NULL,"
                       "kind TEXT NOT NULL CHECK(kind IN ('user','debug')),occurred_at TEXT)")
            db.execute('CREATE INDEX records_kind_occurred_at_idx ON records(kind,occurred_at,id)')
            db.execute('CREATE INDEX records_occurred_at_idx ON records(occurred_at,id)')
            db.execute('CREATE TABLE snapshots(id TEXT PRIMARY KEY,payload TEXT NOT NULL,sha256 TEXT NOT NULL)')
            db.execute('INSERT INTO metadata VALUES (?,?)', ('area', canonical(info)))
            db.execute('INSERT INTO metadata VALUES (?,?)', ('limits', canonical(DEFAULT_LIMITS)))
            db.execute('PRAGMA user_version=2')
    return info


def occurrence_column(value):
    """OpenAI: 保留来源日期/带时区时间的原写法；未知投影为SQL NULL，绝不用入库时间代填。"""
    if value in ('unknown', '未知', '历史未知'):
        return None
    if not isinstance(value, str):
        raise ValueError('occurred_at须为来源日期、带时区ISO时间或unknown')
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        date.fromisoformat(value)
    elif re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
                      r'(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])', value):
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    else:
        raise ValueError('occurred_at格式无效；不猜日期、不改写来源标识')
    return value


def validate_record(record, info):
    """OpenAI: 校验精选载荷，不把声明reviewed当事实真实性的机器证明。"""
    required = {'id', 'kind', 'scope', 'title', 'content', 'source', 'occurred_at',
                'related_paths', 'relevance', 'status', 'evidence', 'supersedes', 'redacted'}
    if not isinstance(record, dict) or set(record) != required:
        raise ValueError('记录字段不完整或含未知字段')
    for key in required - {'related_paths', 'evidence', 'supersedes', 'redacted'}:
        if not isinstance(record[key], str) or not record[key].strip():
            raise ValueError('记录需要非空文本：' + key)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', record['id']):
        raise ValueError('记录ID格式错误')
    if record['scope'] != info['scope'] or record['kind'] not in ('user', 'debug'):
        raise ValueError('只允许本scope的user/debug精选记录')
    occurrence_column(record['occurred_at'])
    if record['kind'] == 'user' and record['status'] not in ('confirmed', 'exploration', 'superseded'):
        raise ValueError('用户原话须区分明确要求/探索/已替代')
    if record['kind'] == 'debug' and (record['status'] != 'verified' or not record['evidence']):
        raise ValueError('debug只收有证据的已验证修复或避坑结论')
    for key in ('related_paths', 'evidence'):
        if not isinstance(record[key], list) or any(not isinstance(v, str) or not v.strip() for v in record[key]):
            raise ValueError('记录列表字段错误：' + key)
    if not record['related_paths']:
        raise ValueError('必须声明关联路径')
    for path in record['related_paths']:
        if path.startswith('/') or '\\' in path or ':' in path or '..' in path.split('/'):
            raise ValueError('关联路径必须是责任区内相对路径')
    if record['supersedes'] is not None and (not isinstance(record['supersedes'], str) or record['supersedes'] == record['id']):
        raise ValueError('替代记录ID错误')
    if type(record['redacted']) is not bool or len(canonical(record)) > 200000:
        raise ValueError('脱敏字段或记录大小错误')


def append_record(area, record, reviewed=False):
    """OpenAI: 追加已选录记录；相同ID只能重放同一载荷，修订用新ID。"""
    if not reviewed:
        raise ValueError('须先人工/Agent核原话、scope及脱敏')
    with connect(area) as db:
        db.execute('BEGIN IMMEDIATE')
        info = metadata(db)
        validate_record(record, info)
        if record['supersedes'] and not db.execute('SELECT 1 FROM records WHERE id=?', (record['supersedes'],)).fetchone():
            raise ValueError('被替代原文不存在')
        payload = canonical(record)
        checksum = digest(payload)
        previous = db.execute('SELECT sha256,payload FROM records WHERE id=?', (record['id'],)).fetchone()
        if previous:
            if previous['payload'] != payload or previous['sha256'] != checksum:
                raise ValueError('记录ID冲突；不覆盖历史')
        else:
            db.execute('INSERT INTO records(id,payload,sha256,kind,occurred_at) VALUES (?,?,?,?,?)',
                       (record['id'], payload, checksum, record['kind'], occurrence_column(record['occurred_at'])))
    result = read_record(area, record['id'])
    return {'id': record['id'], 'sha256': result['sha256']}


def checked_record(row, info):
    """OpenAI: 同时校验原文hash和SQL投影，防止列漂移造成检索结果与完整记录矛盾。"""
    if digest(row['payload']) != row['sha256']:
        raise ValueError('记录hash不匹配')
    value = json.loads(row['payload'])
    validate_record(value, info)
    if (row['id'] != value['id'] or row['kind'] != value['kind']
            or row['occurred_at'] != occurrence_column(value['occurred_at'])):
        raise ValueError('日期/类型列与完整记录不一致')
    return value


def read_record(area, record_id):
    """OpenAI: 精确读取并验hash；损坏记录不作为压缩原文依据。"""
    with connect(area, readonly=True) as db:
        info = metadata(db)
        row = db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone()
    if row is None:
        raise ValueError('记录不存在')
    return dict(record=checked_record(row, info), sha256=row['sha256'])


def search_records(area, query='', limit=20, offset=0, kind=None, from_date=None, to_date=None):
    """OpenAI: 组合关键词/类型/来源日期筛选；含首尾日、有界分页，只返回索引不注入全文。"""
    if not 1 <= limit <= 50 or offset < 0 or not any((query.strip(), kind, from_date, to_date)):
        raise ValueError('需要关键词或筛选条件、1..50条上限与非负offset')
    if kind is not None and kind not in ('user', 'debug'):
        raise ValueError('kind只允许user或debug')
    for bound in (from_date, to_date):
        if bound is not None:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', bound):
                raise ValueError('日期筛选须为YYYY-MM-DD')
            date.fromisoformat(bound)
    if from_date and to_date and from_date > to_date:
        raise ValueError('日期区间倒置')
    clauses, parameters = [], []
    if kind is not None:
        clauses.append('kind=?')
        parameters.append(kind)
    if from_date or to_date:
        clauses.append('occurred_at IS NOT NULL')
    if from_date:
        clauses.append('occurred_at>=?')
        parameters.append(from_date)
    # OpenAI: 比较原始来源日历日期，而非UTC瞬间；上界用下一天排除边界，包含结束日全部时间。
    if to_date and date.fromisoformat(to_date) < date.max:
        clauses.append('occurred_at<?')
        parameters.append((date.fromisoformat(to_date) + timedelta(days=1)).isoformat())
    with connect(area, readonly=True) as db:
        db.execute('BEGIN')
        info = metadata(db)
        # OpenAI: 精选库先流式核投影；否则被损坏类型/日期筛掉的行会变成静默漏检。
        for row in db.execute('SELECT * FROM records'):
            checked_record(row, info)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        rows = db.execute('SELECT * FROM records' + where + ' ORDER BY id', parameters)
        items, matched = [], 0
        for row in rows:
            value = checked_record(row, info)
            # OpenAI: 只搜索解码后的字段值；不能让JSON转义或字段名影响原文字面检索。
            texts = [part for field in value.values() for part in (field if isinstance(field, list) else [field])
                     if isinstance(part, str)]
            if query.strip() and not any(query in text for text in texts):
                continue
            matched += 1
            if matched <= offset:
                continue
            items.append({key: value[key] for key in ('id', 'kind', 'title', 'source', 'occurred_at')})
            if len(items) > limit:
                break
    return dict(items=items[:limit], has_more=len(items) > limit, next_offset=offset + len(items[:limit]))


def checked_snapshot(row, db, info):
    """OpenAI: 统一校验恢复快照的结构、内容标识和可达来源，不把hash当真实性证明。"""
    if row is None or not isinstance(row['payload'], str):
        raise ValueError('摘要历史缺失或损坏')
    checksum = digest(row['payload'])
    if checksum != row['sha256'] or checksum != row['id']:
        raise ValueError('摘要历史ID/hash不匹配')
    value = json.loads(row['payload'])
    if not isinstance(value, dict) or set(value) != {'file', 'content', 'old_sha256', 'new_sha256', 'records'}:
        raise ValueError('摘要历史字段错误')
    if not isinstance(value['file'], str) or value['file'] not in DEFAULT_LIMITS or not isinstance(value['content'], str):
        raise ValueError('摘要历史文件/原文类型错误')
    for key in ('old_sha256', 'new_sha256'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[0-9a-f]{64}', value[key]):
            raise ValueError('摘要历史hash格式错误')
    if digest(value['content']) != value['old_sha256']:
        raise ValueError('摘要原文hash错误')
    ids = value['records']
    if (not isinstance(ids, list) or any(not isinstance(item, str) or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', item) for item in ids)
            or len(set(ids)) != len(ids) or (not ids and value['file'] != 'MEMORY.md')):
        raise ValueError('摘要历史来源列表错误')
    # OpenAI: 所有读取及交换路径共用此检查，避免verify放行、迁移时才发现坏包。
    for record_id in ids:
        source = db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone()
        if source is None:
            raise ValueError('摘要历史引用的记录缺失')
        checked_record(source, info)
    return value


def verify_database(db):
    """OpenAI: 在调用者同一事务中核结构、载荷与引用，供verify、导入和导出一致复用。"""
    info = metadata(db)
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('SQLite完整性失败')
    limits = db.execute('SELECT value FROM metadata WHERE key=?', ('limits',)).fetchone()
    if limits is None:
        raise ValueError('缺少摘要额度')
    validate_limits(json.loads(limits[0]))
    parents = {}
    for row in db.execute('SELECT * FROM records'):
        value = checked_record(row, info)
        parents[value['id']] = value['supersedes']
    for record_id, parent in parents.items():
        seen = {record_id}
        while parent:
            if parent not in parents or parent in seen:
                raise ValueError('替代链缺失或循环')
            seen.add(parent)
            parent = parents[parent]
    for row in db.execute('SELECT * FROM snapshots'):
        checked_snapshot(row, db, info)
    return dict(scope=info['scope'], records=len(parents), integrity='ok')


def verify_history(area):
    """OpenAI: 在一致的只读事务中核完整历史，不代替事实或语义审查。"""
    with connect(area, readonly=True) as db:
        db.execute('BEGIN')
        return verify_database(db)


def summary_path(area, name):
    """OpenAI: 只允许三份固定摘要，拒绝路径逃逸及符号链接覆盖。"""
    if name not in DEFAULT_LIMITS:
        raise ValueError('只允许USER.md、MEMORY.md、DEBUG.md')
    path = Path(area) / name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('摘要不能是符号链接或目录')
    return path


def read_text_exact(path):
    """OpenAI: 保留CRLF等原始文本，字符计数与原文hash不受平台换行转换影响。"""
    return path.read_bytes().decode('utf-8')


def summary_status(area):
    """OpenAI: 返回包含头部的Unicode字符使用量；缺文件明确显示而非报全部合规。"""
    with connect(area, readonly=True) as db:
        metadata(db)
        limits = json.loads(db.execute('SELECT value FROM metadata WHERE key=?', ('limits',)).fetchone()[0])
    validate_limits(limits)
    files = {}
    for name, cap in limits.items():
        path = summary_path(area, name)
        text = read_text_exact(path) if path.exists() else ''
        files[name] = dict(exists=path.exists(), chars=len(text), sha256=digest(text),
                           over_limit=len(text) > cap, needs_compaction=len(text) >= cap * 0.8)
    return dict(limits=limits, files=files)


def validate_limits(limits):
    """OpenAI: 三份摘要都必须有有限正整数额度，不能用0/无限值绕过。"""
    if not isinstance(limits, dict) or set(limits) != set(DEFAULT_LIMITS):
        raise ValueError('额度须覆盖三份摘要')
    if any(type(value) is not int or not 256 <= value <= 100000 for value in limits.values()):
        raise ValueError('每份额度须为256..100000字符')


def configure_limits(area, limits):
    """OpenAI: 按明确设置更新区域额度，不截断超额旧文；状态回读显示真实缺口。"""
    validate_limits(limits)
    with connect(area) as db:
        metadata(db)
        db.execute('UPDATE metadata SET value=? WHERE key=?', (canonical(limits), 'limits'))
    try:
        return {**summary_status(area), 'committed': True}
    except (OSError, ValueError, sqlite3.Error) as error:
        # OpenAI: DB事务已经提交；把状态读取失败与写入失败分开，避免重复执行。
        return dict(committed=True, limits=limits, status_error=str(error),
                    warning='额度已保存，摘要状态读取失败；先修复文件再status，不要重放写入')


def read_snapshot(area, snapshot_id):
    """OpenAI: 完整读取压缩前的摘要修订，不将其当当前有效指令。"""
    with connect(area, readonly=True) as db:
        db.execute('BEGIN')
        info = metadata(db)
        row = db.execute('SELECT * FROM snapshots WHERE id=?', (snapshot_id,)).fetchone()
        return checked_snapshot(row, db, info)


def replace_summary(area, name, content, expected_sha256, record_ids, reviewed=False):
    """OpenAI: 先提交并读验旧文，再原子替换有限摘要；失败保留原文和恢复证据。"""
    if not reviewed or not content.strip() or len(set(record_ids)) != len(record_ids):
        raise ValueError('需完整来源清单及语义/隐私核验；不允许清空摘要')
    if not record_ids and name != 'MEMORY.md':
        raise ValueError('USER/DEBUG摘要需要完整精选记录来源；一般MEMORY知识可只保全旧修订')
    verify_history(area)
    for record_id in record_ids:
        read_record(area, record_id)
    status = summary_status(area)
    path = summary_path(area, name)
    if len(content) > status['limits'][name]:
        raise ValueError('摘要超额；先整理，不截断或无限增卷')
    # OpenAI: 锁串行化本工具写者；不以删除陈旧锁抢占未知在途写入。
    lock = Path(area) / '.history-summary.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError('摘要写入锁已存在；核原任务，禁止盲重试') from error
    temporary = None
    try:
        os.close(fd)
        old = read_text_exact(path) if path.exists() else ''
        if digest(old) != expected_sha256:
            raise ValueError('旧文已变化；先合并人工/其他任务改动')
        snapshot = dict(file=name, content=old, old_sha256=expected_sha256,
                        new_sha256=digest(content), records=record_ids)
        payload = canonical(snapshot)
        snapshot_id = digest(payload)
        with connect(area) as db:
            db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?)', (snapshot_id, payload, digest(payload)))
        if read_snapshot(area, snapshot_id) != snapshot:
            raise ValueError('旧文归档读回不一致')
        # OpenAI: 同目录临时文件原子替换；在替换前再核外部编辑，DB成功不等于文件成功。
        fd, temporary = tempfile.mkstemp(prefix='.summary-', dir=Path(area))
        with os.fdopen(fd, 'wb') as output:
            output.write(content.encode('utf-8'))
            output.flush()
            os.fsync(output.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        summary_path(area, name)
        latest = read_text_exact(path) if path.exists() else ''
        if digest(latest) != expected_sha256:
            raise ValueError('替换前检测到外部编辑；保持现有文件')
        os.replace(temporary, path)
        temporary = None
        if digest(read_text_exact(path)) != digest(content):
            raise ValueError('写后文件已变化；按snapshot_id恢复核对，不盲重放')
        return dict(snapshot_id=snapshot_id, old_sha256=expected_sha256, new_sha256=digest(content))
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink()


def export_history(area, reviewed=False):
    """OpenAI: 确定性导出完整精选历史供显式共享，不默认公开或读取Bot私有库。"""
    if not reviewed:
        raise ValueError('导出前须核scope、隐私与分享范围')
    with connect(area, readonly=True) as db:
        # OpenAI: 验证与导出共享读事务，不能在两次连接之间混进未经校验的并发变化。
        db.execute('BEGIN')
        verify_database(db)
        result: dict = dict(schema=2, area=metadata(db),
                      limits=json.loads(db.execute("SELECT value FROM metadata WHERE key='limits'").fetchone()[0]))
        for table in ('records', 'snapshots'):
            result[table] = [dict(row) for row in db.execute('SELECT * FROM ' + table + ' ORDER BY id')]
    result['sha256'] = digest(canonical(result))
    return result


def import_history(area, bundle, reviewed=False):
    """OpenAI: 同scope交换包整批校验后事务导入；冲突回滚，不覆盖旧记录或摘要。"""
    if not reviewed or not isinstance(bundle, dict):
        raise ValueError('导入需要核来源与隐私')
    expected = {'schema', 'area', 'limits', 'records', 'snapshots', 'sha256'}
    if set(bundle) != expected or type(bundle['schema']) is not int or bundle['schema'] not in (1, 2):
        raise ValueError('交换包schema错误')
    check = {key: value for key, value in bundle.items() if key != 'sha256'}
    if digest(canonical(check)) != bundle['sha256']:
        raise ValueError('交换包hash不匹配')
    verify_history(area)
    with connect(area) as db:
        db.execute('BEGIN IMMEDIATE')
        info = metadata(db)
        limits = json.loads(db.execute("SELECT value FROM metadata WHERE key='limits'").fetchone()[0])
        if bundle['area'] != info or bundle['limits'] != limits:
            raise ValueError('责任区/隐私边界/额度不匹配；不自动重定向')
        # OpenAI: records先导入、后核替代链，允许按ID排序而非按父子顺序的确定性包。
        for table in ('records', 'snapshots'):
            if not isinstance(bundle[table], list):
                raise ValueError('交换包列表错误')
            ids = set()
            for row in bundle[table]:
                fields = {'id', 'payload', 'sha256'}
                if table == 'records' and bundle['schema'] == 2:
                    fields |= {'kind', 'occurred_at'}
                if (not isinstance(row, dict) or set(row) != fields
                        or not all(isinstance(row[key], str) for key in ('id', 'payload', 'sha256'))
                        or row['id'] in ids):
                    raise ValueError('交换包重复ID或字段错误')
                ids.add(row['id'])
                if digest(row['payload']) != row['sha256']:
                    raise ValueError('交换记录hash不匹配')
                data = json.loads(row['payload'])
                if table == 'records':
                    validate_record(data, info)
                    if row['id'] != data['id']:
                        raise ValueError('记录ID不一致')
                    if bundle['schema'] == 2:
                        checked_record(row, info)
                else:
                    checked_snapshot(row, db, info)
                previous = db.execute('SELECT payload,sha256 FROM ' + table + ' WHERE id=?', (row['id'],)).fetchone()
                if previous and (previous['payload'] != row['payload'] or previous['sha256'] != row['sha256']):
                    raise ValueError('同ID不同内容：停止整批导入')
                if not previous:
                    if table == 'records':
                        # OpenAI: 旧交换包只增投影列；payload和hash逐字保留，不改原话以迎合新schema。
                        db.execute('INSERT INTO records(id,payload,sha256,kind,occurred_at) VALUES (?,?,?,?,?)',
                                   (row['id'], row['payload'], row['sha256'], data['kind'],
                                    occurrence_column(data['occurred_at'])))
                    else:
                        db.execute('INSERT INTO snapshots VALUES (?,?,?)', (row['id'], row['payload'], row['sha256']))
        # OpenAI: 最终不变量在commit之前校验，失败可回滚整个包而不是提交后才报错。
        result = verify_database(db)
    return result


def parser():
    """OpenAI: 提供可发现的命令与显式写入参数，不以默认值扩大动作范围。"""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--area', required=True, help='真实责任区Agentic目录')
    commands = result.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    for field in ('readme', 'scope', 'description', 'visibility'):
        init.add_argument('--' + field, required=True)
    add = commands.add_parser('add')
    add.add_argument('--record', required=True, help='精选记录JSON文件')
    add.add_argument('--reviewed', action='store_true')
    get = commands.add_parser('get')
    get.add_argument('id')
    search = commands.add_parser('search')
    search.add_argument('query', nargs='?', default='')
    search.add_argument('--kind', choices=['user', 'debug'])
    search.add_argument('--from-date', help='来源日期下界YYYY-MM-DD，包含当天')
    search.add_argument('--to-date', help='来源日期上界YYYY-MM-DD，包含当天')
    search.add_argument('--limit', type=int, default=10)
    search.add_argument('--offset', type=int, default=0)
    commands.add_parser('verify')
    commands.add_parser('status')
    limits = commands.add_parser('limits')
    for name in ('user', 'memory', 'debug'):
        limits.add_argument('--' + name, type=int, required=True)
    replace = commands.add_parser('replace')
    replace.add_argument('--file', required=True, choices=list(DEFAULT_LIMITS))
    replace.add_argument('--candidate', required=True)
    replace.add_argument('--expected-sha256', required=True)
    replace.add_argument('--record-id', action='append', default=[])
    replace.add_argument('--reviewed', action='store_true')
    snapshot = commands.add_parser('snapshot')
    snapshot.add_argument('id')
    export = commands.add_parser('export')
    export.add_argument('--output', required=True)
    export.add_argument('--reviewed', action='store_true')
    load = commands.add_parser('import')
    load.add_argument('--input', required=True)
    load.add_argument('--reviewed', action='store_true')
    return result


def main(argv=None):
    """OpenAI: CLI机器输出采用ASCII转义JSON，中文内容不受控制台代码页损坏。"""
    args = parser().parse_args(argv)
    try:
        if args.command == 'init':
            result = initialize(args.area, args.readme, args.scope, args.description, args.visibility)
        elif args.command == 'add':
            result = append_record(args.area, json.loads(read_text_exact(Path(args.record))), args.reviewed)
        elif args.command == 'get':
            result = read_record(args.area, args.id)
        elif args.command == 'search':
            result = search_records(args.area, args.query, args.limit, args.offset,
                                    args.kind, args.from_date, args.to_date)
        elif args.command == 'verify':
            result = verify_history(args.area)
        elif args.command == 'status':
            result = summary_status(args.area)
        elif args.command == 'limits':
            result = configure_limits(args.area, {'USER.md': args.user, 'MEMORY.md': args.memory, 'DEBUG.md': args.debug})
        elif args.command == 'replace':
            result = replace_summary(args.area, args.file, read_text_exact(Path(args.candidate)),
                                     args.expected_sha256, args.record_id, args.reviewed)
        elif args.command == 'snapshot':
            result = read_snapshot(args.area, args.id)
        elif args.command == 'export':
            bundle = export_history(args.area, args.reviewed)
            # OpenAI: 不覆盖已存在的人工导出，也不经符号链接写出；输出位置须由调用者授权。
            with Path(args.output).open('x', encoding='utf-8', newline='\n') as output:
                json.dump(bundle, output, ensure_ascii=False, sort_keys=True, indent=2)
                output.write('\n')
            result = dict(output=args.output, sha256=bundle['sha256'])
        else:
            result = import_history(args.area, json.loads(read_text_exact(Path(args.input))), args.reviewed)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
